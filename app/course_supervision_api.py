"""Session-owned assembly for the existing one-course supervision Store."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import Field
from starlette.concurrency import run_in_threadpool

from app.private_artifact_api import _queries
from app.source_connections import CanvasRoute, StrictBody
from contracts.models import Identity
from shared.canvas_reads import SourceRefreshRequired
from shared.db import QueueFull, RequestConflict, Store


class SupervisionRoute(CanvasRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def private(request):
            try:
                response = await handler(request)
            except SourceRefreshRequired:
                response = JSONResponse(
                    {"detail": {"code": "source_refresh_required"}}, status_code=409
                )
            except LookupError:
                response = JSONResponse({"detail": "Not found"}, status_code=404)
            except RequestConflict:
                response = JSONResponse({"detail": "Request conflict"}, status_code=409)
            except ValueError:
                response = JSONResponse({"detail": "Invalid supervision request"}, status_code=400)
            except QueueFull:
                response = JSONResponse({"detail": "Work queue full"}, status_code=409)
            except Exception:
                response = JSONResponse({"detail": "Supervision unavailable"}, status_code=503)
            response.headers["Cache-Control"] = "no-store"
            return response

        return private


class EnableIn(StrictBody):
    connection_id: str = Field(min_length=36, max_length=36)
    course_id: str = Field(min_length=1, max_length=32)
    call_limit: int = Field(default=6, ge=1, le=20)


class DecisionIn(StrictBody):
    accept: bool


class NotificationIn(StrictBody):
    consent: bool


def register_course_supervision(api, *, identity_dependency, database_dependency):
    User = Annotated[Identity, Depends(identity_dependency)]
    DB = Annotated[Store, Depends(database_dependency)]
    router = APIRouter(prefix="/v1/course-supervisions", route_class=SupervisionRoute)

    @router.post("")
    def enable(body: EnableIn, request: Request, user: User, db: DB):
        _queries(request, set())
        row = db.enable_course_supervision(
            user.user_id, body.connection_id, body.course_id, call_limit=body.call_limit
        )
        # The raw enable row includes internal lease/snapshot columns. Only the
        # published student projection may cross HTTP, including on enable replay.
        return db.course_supervision_status(user.user_id, row["id"])

    @router.get("/{supervision_id}")
    def status(supervision_id: str, request: Request, user: User, db: DB):
        _queries(request, set())
        return db.course_supervision_status(user.user_id, supervision_id)

    @router.post("/{supervision_id}/pause")
    async def pause(supervision_id: str, request: Request, user: User, db: DB):
        _queries(request, set())
        if await request.body():
            raise ValueError("Pause has no parameters")
        return await run_in_threadpool(db.pause_course_supervision, user.user_id, supervision_id)

    @router.post("/{supervision_id}/offers/{offer_id}/decision")
    def decide(
        supervision_id: str, offer_id: str, body: DecisionIn, request: Request, user: User, db: DB
    ):
        _queries(request, set())
        result = db.decide_course_offer(user.user_id, supervision_id, offer_id, accept=body.accept)
        if result["draft_request"] is None:
            return {"state": result["state"], "responsibility_id": None}
        # Stable Store-provided request key recovers a crash between these calls.
        duty = db.create_canvas_draft_responsibility(user.user_id, **result["draft_request"])
        return {"state": result["state"], "responsibility_id": duty["id"]}

    @router.post("/{supervision_id}/notifications")
    def notifications(
        supervision_id: str, body: NotificationIn, request: Request, user: User, db: DB
    ):
        _queries(request, set())
        return db.set_course_notification_consent(
            user.user_id, supervision_id, consent=body.consent
        )

    @router.post("/{supervision_id}/offers/{offer_id}/delivery")
    async def enqueue(supervision_id: str, offer_id: str, request: Request, user: User, db: DB):
        _queries(request, set())
        if await request.body():
            raise ValueError("Delivery has no caller payload")
        return await run_in_threadpool(
            db.enqueue_course_offer, user.user_id, supervision_id, offer_id
        )

    api.include_router(router)
