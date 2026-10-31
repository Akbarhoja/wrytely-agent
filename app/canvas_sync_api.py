"""Thin private HTTP assembly for existing Canvas scope/discovery transactions."""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import Field, field_validator, model_validator

from app.source_connections import CanvasRoute, StrictBody
from contracts.canvas_sync import REASONS, Checkpoint, DiscoveryBatch, replay_key
from contracts.models import Identity
from shared.canvas_sync import CanvasSyncConflict
from shared.db import Store
from shared.source_connections import SourceCredentialRejected

CONFLICT_CODES = frozenset(
    {
        "checkpoint_changed",
        "course_not_discovered",
        "course_scope_limit",
        "cursor_cycle",
        "duplicate_course_page",
        "generation_changed",
        "identity_required",
        "incomplete_resource",
        "lease_expired",
        "lease_replaced",
        "pagination_complete_or_limit",
        "reconnect_required",
        "replay_conflict",
        "resource_not_selected",
        "resource_terminal",
        "resources_open",
        "resume_existing_scan",
        "scan_terminal",
        "scope_changed",
        "subject_changed",
    }
)


class DiscoveryBatchRoute(CanvasRoute):
    # Envelope remains limited to1MiB by the Store; allow its control/checkpoint wrapper.
    body_limit = 2 * 1024 * 1024


class MetadataControlRoute(CanvasRoute):
    # Full1000-course selection and JSON-escaped4000-character checkpoints fit.
    body_limit = 64 * 1024


class Control(StrictBody):
    generation: int = Field(ge=1)

    @field_validator("connection_id", "scan_id", "lease_token", check_fields=False)
    @classmethod
    def valid_uuid(cls, value):
        UUID(value)
        return value

    @field_validator("begin_key", "resume_key", "batch_key", "finish_key", check_fields=False)
    @classmethod
    def valid_key(cls, value):
        return replay_key(value)


class ScopeIn(Control):
    connection_id: str = Field(min_length=1, max_length=128)
    mode: Literal["explicit_set", "all_active"]
    course_ids: list[str] = Field(max_length=1000)
    resource_kinds: list[str] = Field(max_length=9)


class BeginIn(Control):
    connection_id: str = Field(min_length=1, max_length=128)
    subject: str = Field(min_length=1, max_length=1024)
    scope_revision: int = Field(ge=0)
    begin_key: str


class ScanIn(Control):
    scan_id: str = Field(min_length=1, max_length=128)


class ResumeIn(ScanIn):
    resume_key: str


class LeasedIn(ScanIn):
    lease_token: str = Field(min_length=1, max_length=128)


class BatchIn(LeasedIn):
    batch_key: str
    expected_checkpoint: Checkpoint
    envelope: DiscoveryBatch


class ResourceIn(LeasedIn):
    resource_key: str = Field(min_length=1, max_length=128)
    finish_key: str
    expected_checkpoint: Checkpoint
    outcome: Literal["complete", "partial", "restricted", "unsupported"]
    reason: str | None = None

    @model_validator(mode="after")
    def discovery_outcome(self):
        if self.outcome == "complete":
            if self.reason is not None or self.resource_key != "courses":
                raise ValueError("Only course metadata completion is supported")
        elif self.reason not in REASONS:
            raise ValueError("Controlled failure reason required")
        return self


class FinishIn(LeasedIn):
    finish_key: str


def register_canvas_sync(api, *, identity_dependency, database_dependency, canvas_origins):
    prefix = "/v1/source-connections/canvas"
    controls = APIRouter(prefix=prefix, route_class=CanvasRoute)
    metadata_controls = APIRouter(prefix=prefix, route_class=MetadataControlRoute)
    batches = APIRouter(prefix=prefix, route_class=DiscoveryBatchRoute)
    User = Annotated[Identity, Depends(identity_dependency)]
    DB = Annotated[Store, Depends(database_dependency)]
    Credential = Annotated[
        HTTPAuthorizationCredentials | None, Depends(HTTPBearer(auto_error=False))
    ]

    def actor(credentials: Credential):
        if credentials is None:
            raise HTTPException(401, "Reconnect Canvas", headers={"WWW-Authenticate": "Bearer"})
        return credentials.credentials

    Actor = Annotated[str, Depends(actor)]

    def dispatch(request, operation):
        if not canvas_origins:
            raise HTTPException(503, "Canvas sync is not configured")
        if request.query_params:
            raise HTTPException(422, "Invalid Canvas request")
        try:
            return operation()
        except SourceCredentialRejected:
            raise HTTPException(
                401, "Reconnect Canvas", headers={"WWW-Authenticate": "Bearer"}
            ) from None
        except CanvasSyncConflict as exc:
            code = exc.code if exc.code in CONFLICT_CODES else "state_changed"
            raise HTTPException(409, {"code": code}) from None
        except LookupError:
            raise HTTPException(404, "Not found") from None
        except ValueError:
            raise HTTPException(422, "Invalid Canvas request") from None

    @metadata_controls.post("/scope")
    def scope(body: ScopeIn, request: Request, user: User, db: DB):
        return dispatch(
            request,
            lambda: db.set_canvas_scope(
                user.user_id,
                body.connection_id,
                body.generation,
                mode=body.mode,
                course_ids=body.course_ids,
                resource_kinds=body.resource_kinds,
            ),
        )

    @controls.post("/discovery/begin")
    def begin(body: BeginIn, request: Request, token: Actor, db: DB):
        return dispatch(
            request,
            lambda: db.begin_sync(
                token,
                body.connection_id,
                body.generation,
                body.subject,
                body.scope_revision,
                body.begin_key,
            ),
        )

    @controls.post("/discovery/resume")
    def resume(body: ResumeIn, request: Request, token: Actor, db: DB):
        return dispatch(
            request, lambda: db.resume_sync(token, body.scan_id, body.generation, body.resume_key)
        )

    @batches.post("/discovery/batch")
    def batch(body: BatchIn, request: Request, token: Actor, db: DB):
        return dispatch(
            request,
            lambda: db.commit_sync_batch(
                token,
                body.scan_id,
                body.generation,
                body.lease_token,
                body.batch_key,
                body.expected_checkpoint.model_dump(),
                body.envelope.model_dump(),
            ),
        )

    @metadata_controls.post("/discovery/resource")
    def resource(body: ResourceIn, request: Request, token: Actor, db: DB):
        return dispatch(
            request,
            lambda: db.finish_resource(
                token,
                body.scan_id,
                body.generation,
                body.lease_token,
                body.resource_key,
                body.finish_key,
                body.expected_checkpoint.model_dump(),
                outcome=body.outcome,
                reason=body.reason,
            ),
        )

    @controls.post("/discovery/finish")
    def finish(body: FinishIn, request: Request, token: Actor, db: DB):
        return dispatch(
            request,
            lambda: db.finish_sync(
                token,
                body.scan_id,
                body.generation,
                body.lease_token,
                body.finish_key,
            ),
        )

    api.include_router(controls)
    api.include_router(metadata_controls)
    api.include_router(batches)
