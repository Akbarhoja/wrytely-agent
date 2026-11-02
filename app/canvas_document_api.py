"""Default-off private HTTP assembly for existing document staging transactions."""

import unicodedata
from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, Request, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.canvas_sync_api import CONFLICT_CODES
from app.source_connections import CanvasRoute
from shared.canvas_document_uploads import CanvasDocumentUploadLimited
from shared.canvas_sync import CanvasSyncConflict
from shared.db import Store
from shared.source_connections import SourceCredentialRejected

DOCUMENT_CONFLICTS = CONFLICT_CODES | {
    "document_conflict",
    "document_expired",
    "document_not_ready",
    "resource_format_conflict",
}
QUOTAS = {"document_upload_limit", "document_bytes_limit"}


class DocumentRoute(CanvasRoute):
    body_limit = 1024 * 1024

    def get_route_handler(self):
        handler = super().get_route_handler()

        async def bounded(request):
            response = await handler(request)
            # Document schema2's agreed status; schema1 routes keep their422.
            if response.status_code == 422:
                response.status_code = 400
            return response

        return bounded


def register_canvas_documents(api, *, database_dependency, canvas_origins, extractor_versions):
    valid = type(extractor_versions) is tuple
    try:
        valid = valid and all(
            type(version) is str
            and 1 <= len(version) <= 64
            and version.strip()
            and unicodedata.normalize("NFC", version.replace("\r\n", "\n").replace("\r", "\n"))
            == version
            and version.encode("utf-8")
            for version in extractor_versions
        )
    except UnicodeError:
        valid = False
    if not valid:
        raise ValueError("Invalid Canvas document extractor configuration")

    router = APIRouter(prefix="/v1/source-connections/canvas/documents", route_class=DocumentRoute)
    DB = Annotated[Store, Depends(database_dependency)]
    Credential = Annotated[
        HTTPAuthorizationCredentials | None, Depends(HTTPBearer(auto_error=False))
    ]

    def dispatch(request, credentials, body, operation, call):
        if not canvas_origins or not extractor_versions:
            raise HTTPException(503, "Canvas documents are not configured")
        if request.query_params or (operation is not None and body.get("operation") != operation):
            raise HTTPException(400, "Invalid Canvas request")
        try:
            if credentials is None:
                raise SourceCredentialRejected()
            return call(credentials.credentials)
        except SourceCredentialRejected:
            raise HTTPException(
                401, "Reconnect Canvas", headers={"WWW-Authenticate": "Bearer"}
            ) from None
        except CanvasSyncConflict as exc:
            code = exc.code if exc.code in DOCUMENT_CONFLICTS else "state_changed"
            raise HTTPException(409, {"code": code}) from None
        except CanvasDocumentUploadLimited as exc:
            code = str(exc) if str(exc) in QUOTAS else "state_changed"
            raise HTTPException(429, {"code": code}, headers={"Retry-After": "30"}) from None
        except LookupError as exc:
            if type(exc) is LookupError:
                return Response(status_code=404)
            raise HTTPException(500, {"code": "document_operation_failed"}) from None
        except ValueError:
            raise HTTPException(400, "Invalid Canvas request") from None
        except Exception:
            # A commit may have succeeded: preserve uncertainty, never retry here.
            raise HTTPException(500, {"code": "document_operation_failed"}) from None

    @router.post("/begin")
    def begin(
        request: Request, credentials: Credential, db: DB, body: Annotated[dict, Body(strict=True)]
    ):
        return dispatch(
            request,
            credentials,
            body,
            "begin_document",
            lambda token: db.begin_document_upload(
                token, body, extractor_versions=extractor_versions
            ),
        )

    @router.post("/parts")
    def parts(
        request: Request, credentials: Credential, db: DB, body: Annotated[dict, Body(strict=True)]
    ):
        return dispatch(
            request,
            credentials,
            body,
            "put_document_parts",
            lambda token: db.put_document_parts(token, body),
        )

    @router.post("/finish")
    def finish(
        request: Request, credentials: Credential, db: DB, body: Annotated[dict, Body(strict=True)]
    ):
        return dispatch(
            request,
            credentials,
            body,
            "finish_document",
            lambda token: db.finish_document_upload(
                token, body, extractor_versions=extractor_versions
            ),
        )

    @router.post("/batch")
    def publish(
        request: Request, credentials: Credential, db: DB, body: Annotated[dict, Body(strict=True)]
    ):
        # Separate versioned document publication; schema1 academic routes stay unchanged.
        def commit(token):
            if body.keys() != {
                "scan_id",
                "generation",
                "lease_token",
                "batch_key",
                "expected_checkpoint",
                "envelope",
            }:
                raise ValueError("Invalid document publication request")
            if type(body["envelope"]) is not dict or (
                type(body["envelope"].get("schema_version")) is not int
                or body["envelope"]["schema_version"] != 2
                or body["envelope"].get("batch_type") != "canvas_documents"
            ):
                raise ValueError("Invalid document publication schema")
            return db.commit_sync_batch(
                token,
                body["scan_id"],
                body["generation"],
                body["lease_token"],
                body["batch_key"],
                body["expected_checkpoint"],
                body["envelope"],
            )

        return dispatch(request, credentials, body, None, commit)

    api.include_router(router)
