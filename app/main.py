import hmac
import json
import logging
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from psycopg import Error as DatabaseError
from pydantic import BaseModel, ConfigDict, Field, field_validator
from starlette.concurrency import run_in_threadpool

from app.source_connections import register_source_connections
from contracts.delivery import WhatsAppStatusEvent
from contracts.models import AgentControl, Identity, MessageIn, SessionVerifier, SourceObservation
from integrations.whatsapp import extract_statuses, extract_texts, verify_signature
from shared.auth import AuthenticationError, ClerkSessionVerifier
from shared.config import Settings
from shared.db import QueueFull, RequestConflict, Store

log = logging.getLogger(__name__)


class CommunicationPreferences(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    consent: bool
    timezone: str = Field(min_length=1, max_length=100)
    quiet_start: int = Field(ge=0, le=23)
    quiet_end: int = Field(ge=0, le=23)

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError("Use a valid IANA timezone") from None
        return value


class SnapshotIn(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    title: str = Field(min_length=1, max_length=300)
    content: str = Field(min_length=1, max_length=24000)

    @field_validator("title", "content")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Must contain text")
        return value


class PrivateDraftIn(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    objective: str = Field(min_length=1, max_length=12000)
    source_ids: list[str] = Field(min_length=1, max_length=8)
    confirm_private_draft: bool

    @field_validator("objective")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Must contain text")
        return value.strip()

    @field_validator("source_ids")
    @classmethod
    def unique_sources(cls, values: list[str]) -> list[str]:
        canonical = [str(UUID(value)) for value in values]
        if len(set(canonical)) != len(canonical):
            raise ValueError("Choose distinct sources")
        return sorted(canonical)

    @field_validator("confirm_private_draft")
    @classmethod
    def confirmed(cls, value: bool) -> bool:
        if not value:
            raise ValueError("Explicit private-draft confirmation required")
        return value


def create_app(
    settings: Settings | None = None,
    *,
    store: Store | None = None,
    verifier: SessionVerifier | None = None,
) -> FastAPI:
    settings = settings or Settings()
    api = FastAPI(title="Wrytely Academic Agent", version="0.1.0")
    bearer = HTTPBearer(auto_error=False)
    verifier = verifier or ClerkSessionVerifier(settings)
    if store is None and settings.database_url:
        store = Store(
            settings.database_url.get_secret_value(), canvas_origins=settings.canvas_origins
        )
    if settings.authorized_parties:
        api.add_middleware(
            CORSMiddleware,
            allow_origins=settings.authorized_parties,
            allow_methods=["GET", "POST"],
            allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
            allow_credentials=False,
        )

    def identity(
        credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    ) -> Identity:
        if not credentials:
            raise HTTPException(401, "Sign in to Wrytely", headers={"WWW-Authenticate": "Bearer"})
        try:
            return verifier.verify(credentials.credentials)
        except AuthenticationError:
            raise HTTPException(401, "Invalid or expired session") from None

    def database() -> Store:
        if store is None:
            raise HTTPException(503, "Agent database is not configured")
        return store

    User = Annotated[Identity, Depends(identity)]
    DB = Annotated[Store, Depends(database)]

    register_source_connections(
        api,
        identity_dependency=identity,
        database_dependency=database,
        canvas_origins=settings.canvas_origins,
    )

    @api.exception_handler(DatabaseError)
    async def database_error(request, exc):
        log.error("database_unavailable path=%s", request.url.path)
        return JSONResponse(
            status_code=503,
            content={"detail": "Agent storage unavailable"},
            headers={"Cache-Control": "no-store"},
        )

    @api.get("/healthz")
    def health():
        return {"status": "ok", "milestone": "foundation"}

    @api.get("/readyz")
    def readiness():
        configured = settings.readiness()
        return JSONResponse(
            status_code=200 if all(configured.values()) else 503,
            content={"configured": configured, "live_connections_verified": False},
        )

    @api.post("/v1/bootstrap")
    def bootstrap(user: User, db: DB):
        return db.provision(user.user_id)

    @api.get("/v1/me")
    def me(user: User, db: DB):
        agent = db.agent(user.user_id)
        if not agent:
            raise HTTPException(404, "Complete agent setup first")
        return agent

    @api.post("/v1/agent/control")
    def control(body: AgentControl, user: User, db: DB):
        agent = db.set_paused(user.user_id, body.paused)
        if not agent:
            raise HTTPException(404, "Agent not found")
        return agent

    @api.post("/v1/messages", status_code=202)
    def send(
        body: MessageIn,
        user: User,
        db: DB,
        idempotency_key: Annotated[str, Header(min_length=1, max_length=128)],
    ):
        try:
            return db.enqueue(
                user.user_id, body.content, idempotency_key, settings.pending_task_limit
            )
        except RequestConflict:
            raise HTTPException(409, "Use a new idempotency key for a new message") from None
        except QueueFull:
            raise HTTPException(429, "Too many pending messages. Try again shortly.") from None
        except LookupError:
            raise HTTPException(409, "Complete agent setup first") from None

    @api.get("/v1/messages")
    def messages(user: User, db: DB):
        return {"messages": db.messages(user.user_id)}

    @api.get("/v1/tasks")
    def tasks(user: User, db: DB):
        return {"tasks": db.tasks(user.user_id)}

    @api.get("/v1/tasks/{task_id}")
    def task(task_id: UUID, user: User, db: DB):
        row = db.task(user.user_id, task_id)
        if not row:
            raise HTTPException(404, "Task not found")
        return row

    @api.get("/v1/sources")
    def sources(user: User, db: DB, response: Response):
        response.headers["Cache-Control"] = "no-store"
        return {"sources": db.source_snapshots(user.user_id), "limit": 50}

    @api.get("/v1/sources/{source_id}")
    def source_snapshot(source_id: UUID, user: User, db: DB, response: Response):
        response.headers["Cache-Control"] = "no-store"
        row = db.source_snapshot(user.user_id, source_id)
        if row is None:
            raise HTTPException(404, "Source not found", headers={"Cache-Control": "no-store"})
        return row

    @api.post("/v1/sources", status_code=201)
    async def save_snapshot(
        body: SnapshotIn,
        request: Request,
        user: User,
        db: DB,
        response: Response,
        idempotency_key: Annotated[UUID, Header()],
    ):
        if len(await request.body()) > 65536:
            raise HTTPException(413, "Snapshot is too large")
        # A request key identifies one immutable manual snapshot. It is scoped by
        # verified identity in Store, never a browser-provided owner/source ID.
        observation = SourceObservation(
            source_key=f"snapshot:{idempotency_key}",
            external_revision="1",
            title=body.title,
            reference=f"snapshot:{idempotency_key}",
            coverage="snapshot",
            content=body.content,
            retrieved_at=datetime.now(UTC),
        )
        try:
            row = await run_in_threadpool(db.observe_source, user.user_id, observation)
        except RequestConflict:
            raise HTTPException(
                409, "Snapshot request changed. Save new text separately."
            ) from None
        except LookupError:
            raise HTTPException(409, "Complete agent setup first") from None
        response.headers["Cache-Control"] = "no-store"
        # Return the saved version, including its original retrieval time on replay.
        return {
            "source_id": row["source_id"],
            "version_id": row["id"],
            **{
                name: row[name]
                for name in (
                    "title",
                    "reference",
                    "coverage",
                    "retrieved_at",
                    "external_revision",
                    "content",
                )
            },
        }

    @api.post("/v1/responsibilities", status_code=201)
    async def delegate_private_draft(
        body: PrivateDraftIn,
        request: Request,
        user: User,
        db: DB,
        response: Response,
        idempotency_key: Annotated[UUID, Header()],
    ):
        response.headers["Cache-Control"] = "no-store"
        private_headers = {"Cache-Control": "no-store"}
        if len(await request.body()) > 65536:
            raise HTTPException(413, "Request is too large", headers=private_headers)
        try:
            # Consent authorizes one bounded private intent only. Source policy,
            # readiness, task routing and budgets remain trusted server decisions.
            row = await run_in_threadpool(
                db.create_draft_responsibility,
                user.user_id,
                body.objective,
                str(idempotency_key),
                source_ids=body.source_ids,
                max_steps=6,
                max_revisions=2,
                pending_limit=settings.pending_task_limit,
            )
        except RequestConflict:
            raise HTTPException(
                409, "Request changed. Review and confirm again.", headers=private_headers
            ) from None
        except QueueFull:
            raise HTTPException(
                429, "Too much pending work. Try again shortly.", headers=private_headers
            ) from None
        except LookupError:
            raise HTTPException(
                404, "Sources or agent setup unavailable", headers=private_headers
            ) from None
        return {"responsibility_id": str(row["id"]), "requested_mode": "private_draft"}

    @api.get("/v1/responsibilities/{responsibility_id}/status")
    def private_draft_status(responsibility_id: UUID, user: User, db: DB, response: Response):
        response.headers["Cache-Control"] = "no-store"
        result = db.draft_responsibility_status(user.user_id, responsibility_id)
        if result is None:
            raise HTTPException(404, "Work not found", headers={"Cache-Control": "no-store"})
        return result

    @api.get("/v1/responsibilities")
    def responsibilities(user: User, db: DB, response: Response):
        response.headers["Cache-Control"] = "no-store"
        fields = ("id", "objective", "status", "steps_created", "max_steps", "created_at")
        return {
            "responsibilities": [
                {name: row[name] for name in fields} for row in db.responsibilities(user.user_id)
            ],
            "limit": 50,
        }

    @api.get("/v1/responsibilities/{responsibility_id}/artifacts")
    def responsibility_artifacts(responsibility_id: UUID, user: User, db: DB, response: Response):
        response.headers["Cache-Control"] = "no-store"
        rows = db.responsibility_artifacts(user.user_id, responsibility_id)
        if rows is None:
            raise HTTPException(404, "Work not found", headers={"Cache-Control": "no-store"})
        return {"artifacts": rows, "limit": 50}

    @api.get("/v1/artifacts/{artifact_id}")
    def artifact_review(artifact_id: UUID, user: User, db: DB, response: Response):
        response.headers["Cache-Control"] = "no-store"
        result = db.artifact_review(user.user_id, artifact_id)
        if result is None:
            raise HTTPException(404, "Draft not found", headers={"Cache-Control": "no-store"})
        return result

    def whatsapp_ready():
        return all(
            (
                settings.whatsapp_app_secret,
                settings.whatsapp_verify_token,
                settings.whatsapp_phone_number_id,
                settings.whatsapp_business_account_id,
            )
        )

    def whatsapp_configured():
        if not whatsapp_ready():
            raise HTTPException(503, "WhatsApp is not configured")

    @api.get("/v1/whatsapp")
    def whatsapp_connection(user: User, db: DB, response: Response):
        state = db.whatsapp_connection(user.user_id)
        if state is None:
            raise HTTPException(404, "Complete agent setup first")
        response.headers["Cache-Control"] = "no-store"
        return {
            **state,
            "destination": settings.whatsapp_business_number,
            "configured": bool(whatsapp_ready() and settings.whatsapp_business_number),
        }

    @api.post("/v1/whatsapp/link")
    def whatsapp_link(user: User, db: DB):
        whatsapp_configured()
        try:
            return db.create_whatsapp_challenge(user.user_id)
        except LookupError:
            raise HTTPException(409, "Complete agent setup first") from None
        except ValueError:
            raise HTTPException(409, "Unlink existing WhatsApp first") from None

    @api.post("/v1/whatsapp/unlink")
    def whatsapp_unlink(user: User, db: DB):
        db.unlink_whatsapp(user.user_id)
        return {"unlinked": True}

    @api.post("/v1/whatsapp/preferences")
    def whatsapp_preferences(body: CommunicationPreferences, user: User, db: DB):
        try:
            db.set_communication_preferences(user.user_id, **body.model_dump())
        except LookupError:
            raise HTTPException(409, "Complete agent setup first") from None
        return {"saved": True}

    @api.get("/webhooks/whatsapp")
    def whatsapp_verify(request: Request):
        whatsapp_configured()
        query = request.query_params
        supplied = query.get("hub.verify_token", "")
        if query.get("hub.mode") != "subscribe" or not hmac.compare_digest(
            supplied.encode(), settings.whatsapp_verify_token.get_secret_value().encode()
        ):
            raise HTTPException(403, "Invalid verification")
        challenge = query.get("hub.challenge", "")
        if not challenge.isascii() or not challenge.isdigit() or len(challenge) > 128:
            raise HTTPException(400, "Invalid challenge")
        return PlainTextResponse(challenge)

    @api.post("/webhooks/whatsapp")
    async def whatsapp_receive(request: Request, db: DB):
        whatsapp_configured()
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > 262144:
                raise HTTPException(413, "Webhook too large")
        if not verify_signature(
            bytes(body),
            request.headers.get("x-hub-signature-256", ""),
            settings.whatsapp_app_secret.get_secret_value(),
        ):
            raise HTTPException(403, "Invalid signature")
        try:
            payload = json.loads(body)
            messages = extract_texts(
                payload,
                phone_number_id=settings.whatsapp_phone_number_id,
                business_account_id=settings.whatsapp_business_account_id,
            )
            statuses = extract_statuses(
                payload,
                phone_number_id=settings.whatsapp_phone_number_id,
                business_account_id=settings.whatsapp_business_account_id,
                now=datetime.now(UTC),
            )
        except (ValueError, TypeError, AttributeError):
            raise HTTPException(400, "Invalid webhook payload") from None
        try:
            for message in messages:
                await run_in_threadpool(
                    db.ingest_whatsapp, message, limit=settings.pending_task_limit
                )
                if message.event_at is not None:
                    await run_in_threadpool(
                        db.record_whatsapp_inbound_time,
                        message.provider_id,
                        message.sender,
                        message.event_at,
                    )
            for status in statuses:
                event = WhatsAppStatusEvent(
                    business_id=status.business_account_id,
                    phone_number_id=status.phone_number_id,
                    provider_ref=status.provider_id,
                    recipient=status.recipient,
                    status=status.status,
                    event_at=datetime.fromtimestamp(status.provider_timestamp, UTC),
                )
                await run_in_threadpool(
                    db.record_whatsapp_status,
                    event,
                    business_id=settings.whatsapp_business_account_id,
                    phone_number_id=settings.whatsapp_phone_number_id,
                )
        except QueueFull:
            # Do not acknowledge work we did not durably accept; provider may retry.
            raise HTTPException(503, "Agent queue is full") from None
        except ValueError:
            # Capacity/persistence policy may reject a callback. Never acknowledge
            # evidence that was not retained; provider replay remains safe.
            raise HTTPException(503, "Delivery evidence could not be stored") from None
        return {"received": True}

    return api


app = create_app()
