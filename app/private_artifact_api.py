"""Read-only session-authorized HTTP assembly for document-backed saved work."""

import base64
import json
import re
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from starlette.exceptions import HTTPException as StarletteHTTPException

from contracts.models import Identity
from shared.canvas_reads import SourceRefreshRequired
from shared.db import Store
from shared.private_artifact_projection import PrivateArtifactReadLimit


class PrivateResultRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def private(request):
            try:
                response = await handler(request)
            except RequestValidationError:
                response = JSONResponse({"detail": "Invalid result request"}, status_code=400)
            except StarletteHTTPException as exc:
                response = JSONResponse(
                    {"detail": exc.detail}, status_code=exc.status_code, headers=exc.headers
                )
            except PrivateArtifactReadLimit:
                response = JSONResponse({"detail": "Result exceeds read limit"}, status_code=413)
            except SourceRefreshRequired:
                response = JSONResponse(
                    {"detail": {"code": "source_refresh_required"}}, status_code=409
                )
            except LookupError as exc:
                response = JSONResponse(
                    {
                        "detail": "Result not found"
                        if type(exc) is LookupError
                        else "Result unavailable"
                    },
                    status_code=404 if type(exc) is LookupError else 503,
                )
            except ValueError:
                response = JSONResponse({"detail": "Invalid result request"}, status_code=400)
            except Exception:
                response = JSONResponse({"detail": "Result unavailable"}, status_code=503)
            response.headers["Cache-Control"] = "no-store"
            return response

        return private


def _queries(request, allowed):
    items = list(request.query_params.multi_items())
    if len(items) != len(dict(items)) or any(k not in allowed for k, _ in items):
        raise ValueError("Invalid query")
    return dict(items)


def _integer(value, default):
    if value is None:
        return default
    if not re.fullmatch(r"0|[1-9][0-9]{0,5}", value):
        raise ValueError("Invalid integer")
    return int(value)


def _encode_cursor(value):
    return (
        base64.urlsafe_b64encode(
            json.dumps(value, separators=(",", ":"), sort_keys=True).encode("utf-8")
        )
        .decode("ascii")
        .rstrip("=")
    )


def _decode_cursor(value):
    if value is None:
        return None
    if len(value) > 512 or not re.fullmatch(r"[A-Za-z0-9_-]+", value):
        raise ValueError("Invalid cursor")
    try:
        parsed = json.loads(base64.urlsafe_b64decode(value + "=" * (-len(value) % 4)))
        if (
            type(parsed) is not dict
            or parsed.keys() != {"created_at", "id"}
            or _encode_cursor(parsed) != value
        ):
            raise ValueError("Invalid cursor")
        return parsed
    except (UnicodeError, ValueError) as exc:
        raise ValueError("Invalid cursor") from exc


def register_private_artifacts(api, *, identity_dependency, database_dependency):
    router = APIRouter(prefix="/v2", route_class=PrivateResultRoute)
    User = Annotated[Identity, Depends(identity_dependency)]
    DB = Annotated[Store, Depends(database_dependency)]

    @router.get("/responsibilities/{responsibility_id}/artifacts")
    def listing(responsibility_id: UUID, request: Request, user: User, db: DB):
        query = _queries(request, {"limit", "before"})
        result = db.list_private_artifacts_v2(
            user.user_id,
            responsibility_id,
            limit=_integer(query.get("limit"), 20),
            before=_decode_cursor(query.get("before")),
        )
        return {**result, "next": _encode_cursor(result["next"]) if result["next"] else None}

    @router.get("/artifacts/{artifact_id}")
    def detail(artifact_id: UUID, request: Request, user: User, db: DB):
        _queries(request, set())
        return db.read_private_artifact_v2(user.user_id, artifact_id)

    @router.get("/artifacts/{artifact_id}/evidence/{group}/{index}")
    def original(artifact_id: UUID, group: str, index: str, request: Request, user: User, db: DB):
        query = _queries(request, {"check_id", "first_slot", "limit"})
        return db.read_private_artifact_evidence_v2(
            user.user_id,
            artifact_id,
            group=group,
            index=_integer(index, None),
            check_id=query.get("check_id"),
            first_slot=_integer(query.get("first_slot"), 0),
            limit=_integer(query.get("limit"), 1),
        )

    api.include_router(router)
