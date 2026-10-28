import hmac
import json
import logging
from typing import Annotated
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from psycopg import Error as DatabaseError
from starlette.concurrency import run_in_threadpool

from contracts.models import AgentControl, Identity, MessageIn, SessionVerifier
from integrations.whatsapp import extract_texts, verify_signature
from shared.auth import AuthenticationError, ClerkSessionVerifier
from shared.config import Settings
from shared.db import QueueFull, RequestConflict, Store

log = logging.getLogger(__name__)


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
        store = Store(settings.database_url.get_secret_value())
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

    @api.exception_handler(DatabaseError)
    async def database_error(request, exc):
        log.error("database_unavailable path=%s", request.url.path)
        return JSONResponse(status_code=503, content={"detail": "Agent storage unavailable"})

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

    def whatsapp_configured():
        if not all(
            (
                settings.whatsapp_app_secret,
                settings.whatsapp_verify_token,
                settings.whatsapp_phone_number_id,
                settings.whatsapp_business_account_id,
            )
        ):
            raise HTTPException(503, "WhatsApp is not configured")

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
        except (ValueError, TypeError, AttributeError):
            raise HTTPException(400, "Invalid webhook payload") from None
        try:
            for message in messages:
                await run_in_threadpool(
                    db.ingest_whatsapp, message, limit=settings.pending_task_limit
                )
        except QueueFull:
            # Do not acknowledge work we did not durably accept; provider may retry.
            raise HTTPException(503, "Agent queue is full") from None
        return {"received": True}

    return api


app = create_app()
