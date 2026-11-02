"""Default-off private HTTP assembly for existing document staging transactions."""

import base64
import unicodedata
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Request, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.canvas_sync_api import CONFLICT_CODES
from app.source_connections import CanvasRoute
from contracts.canvas_document_publication import DocumentResource
from contracts.canvas_sync import course_id, replay_key
from integrations.canvas.html_extract import extract_html
from integrations.canvas.pdf_extract import extract_pdf
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
        except HTTPException:
            raise
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

    @router.post("/extract")
    def extract(
        request: Request, credentials: Credential, db: DB, body: Annotated[dict, Body(strict=True)]
    ):
        def convert(token):
            # Trusted implementation identifier; provider text never chooses a parser.
            if "canvas.html.v1" not in extractor_versions:
                raise HTTPException(503, "Canvas HTML extraction is not configured")
            if (
                body.keys()
                != {
                    "schema_version",
                    "operation",
                    "origin",
                    "connection_id",
                    "generation",
                    "scope_revision",
                    "resource",
                    "items",
                }
                or type(body["schema_version"]) is not int
                or body["schema_version"] != 2
            ):
                raise ValueError()
            resource = body["resource"]
            if (
                type(resource) is not dict
                or resource.keys() != {"course_id", "kind"}
                or type(resource["kind"]) is not str
                or resource["kind"]
                not in {
                    "assignments",
                    "syllabus",
                    "pages",
                    "announcements",
                    "discussions",
                    "submissions",
                }
            ):
                raise ValueError()
            course_id(resource["course_id"])
            items = body["items"]
            if type(items) is not list or not 1 <= len(items) <= 4:
                raise ValueError()
            seen = set()
            for item in items:
                if (
                    type(item) is not dict
                    or item.keys() != {"provider_id", "html"}
                    or item["html"] is not None
                    and type(item["html"]) is not str
                ):
                    raise ValueError()
                course_id(item["provider_id"])
                if item["provider_id"] in seen:
                    raise ValueError()
                seen.add(item["provider_id"])

            def context():
                current = db.canvas_connection_context(token, body["origin"])
                if current["connection_id"] != body["connection_id"]:
                    raise SourceCredentialRejected()
                if (
                    type(body["generation"]) is not int
                    or current["generation"] != body["generation"]
                ):
                    raise CanvasSyncConflict("generation_changed")
                if (
                    type(body["scope_revision"]) is not int
                    or current["scope_revision"] != body["scope_revision"]
                ):
                    raise CanvasSyncConflict("scope_changed")
                if current["state"] != "connected":
                    raise CanvasSyncConflict("identity_required")
                if (
                    resource["course_id"] not in current["course_ids"]
                    or resource["kind"] not in current["resource_kinds"]
                ):
                    raise CanvasSyncConflict("resource_not_selected")

            context()
            converted = []
            for item in items:
                result = (
                    extract_html(item["html"].encode("utf-8")) if item["html"] is not None else None
                )
                converted.append(
                    {
                        "provider_id": item["provider_id"],
                        "text": result.text if result else "",
                        "coverage": "partial",
                        "missing": list(result.reasons) if result else ["description_not_observed"],
                    }
                )
            context()
            return {
                "schema_version": 2,
                "extractor_version": "canvas.html.v1",
                "resource": resource,
                "items": converted,
            }

        return dispatch(request, credentials, body, "extract_document", convert)

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

    @router.post("/resource")
    def document_resource(
        request: Request, credentials: Credential, db: DB, body: Annotated[dict, Body(strict=True)]
    ):
        def finish(token):
            if body.keys() != {
                "scan_id",
                "generation",
                "lease_token",
                "resource_key",
                "finish_key",
                "expected_checkpoint",
                "outcome",
                "reason",
            }:
                raise ValueError()
            if (
                type(body["generation"]) is not int
                or body["generation"] < 1
                or type(body["resource_key"]) is not str
            ):
                raise ValueError()
            course, separator, kind = body["resource_key"].partition("/")
            if not separator:
                raise ValueError()
            DocumentResource(course_id=course, kind=kind)
            for key in ["scan_id", "lease_token"]:
                if type(body[key]) is not str or str(UUID(body[key])) != body[key]:
                    raise ValueError()
            replay_key(body["finish_key"])
            return db.finish_resource(
                token,
                body["scan_id"],
                body["generation"],
                body["lease_token"],
                body["resource_key"],
                body["finish_key"],
                body["expected_checkpoint"],
                outcome=body["outcome"],
                reason=body["reason"],
            )

        return dispatch(request, credentials, body, None, finish)

    class FileRoute(DocumentRoute):
        body_limit = 8 * 1024 * 1024

    files = APIRouter(prefix="/v1/source-connections/canvas/documents", route_class=FileRoute)

    @files.post("/file-extract")
    def file_extract(
        request: Request, credentials: Credential, db: DB, body: Annotated[dict, Body(strict=True)]
    ):
        def convert(token):
            if (
                body.keys()
                != {
                    "operation",
                    "schema_version",
                    "origin",
                    "connection_id",
                    "generation",
                    "scope_revision",
                    "course_id",
                    "file_id",
                    "content_type",
                    "data",
                }
                or type(body["schema_version"]) is not int
                or body["schema_version"] != 2
            ):
                raise ValueError()
            course_id(body["course_id"])
            course_id(body["file_id"])
            if (
                type(body["content_type"]) is not str
                or body["content_type"] not in {"application/pdf", "text/plain", "text/html"}
                or type(body["data"]) is not str
            ):
                raise ValueError()
            version = {
                "application/pdf": "canvas.pdf.v1",
                "text/plain": "canvas.text.v1",
                "text/html": "canvas.html.v1",
            }[body["content_type"]]
            if version not in extractor_versions:
                raise HTTPException(503, "Canvas file extraction is not configured")

            def context():
                current = db.canvas_connection_context(token, body["origin"])
                if current["connection_id"] != body["connection_id"]:
                    raise SourceCredentialRejected()
                if (
                    type(body["generation"]) is not int
                    or current["generation"] != body["generation"]
                ):
                    raise CanvasSyncConflict("generation_changed")
                if (
                    type(body["scope_revision"]) is not int
                    or current["scope_revision"] != body["scope_revision"]
                ):
                    raise CanvasSyncConflict("scope_changed")
                if (
                    current["state"] != "connected"
                    or body["course_id"] not in current["course_ids"]
                    or "files" not in current["resource_kinds"]
                ):
                    raise CanvasSyncConflict("resource_not_selected")

            context()
            try:
                content = base64.b64decode(body["data"], validate=True)
            except Exception:
                raise ValueError() from None
            if len(content) > 5 * 1024 * 1024:
                raise HTTPException(413, "Canvas file exceeds limit")
            if body["content_type"] == "application/pdf":
                result = extract_pdf(content)
                source = {"pages": result["pages"]} if result["pages"] else {"text": ""}
                missing = result["missing"]
                if not result["pages"]:
                    version = "canvas.text.v1"
                    if version not in extractor_versions:
                        raise HTTPException(503, "Canvas text extraction is not configured")
            elif body["content_type"] == "text/html":
                result = extract_html(content)
                source, missing = {"text": result.text}, list(result.reasons)
            else:
                text = (
                    content.decode("utf-8-sig", errors="strict")
                    .replace("\r\n", "\n")
                    .replace("\r", "\n")
                )
                text = unicodedata.normalize("NFC", text)
                if len(text) > 200000 or "\x00" in text:
                    raise ValueError()
                source, missing = {"text": text}, (["empty_file"] if not text.strip() else [])
            context()
            return {
                "schema_version": 2,
                "extractor_version": version,
                "source": source,
                "coverage": "partial" if missing else "complete",
                "missing": missing,
            }

        return dispatch(request, credentials, body, "extract_file", convert)

    api.include_router(files)
    api.include_router(router)
