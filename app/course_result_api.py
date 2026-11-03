"""Private file and explicit revision assembly over existing checked artifacts."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import Field

from app.course_supervision_api import SupervisionRoute
from app.private_artifact_api import _queries
from app.source_connections import StrictBody
from contracts.models import Identity
from runtime.artifact_rendering import ArtifactNotReady, render_private_artifact_docx
from shared.db import Store


class RevisionIn(StrictBody):
    instructions: str = Field(min_length=1, max_length=4000)
    request_key: str = Field(min_length=1, max_length=100)


def register_course_results(api, *, identity_dependency, database_dependency):
    User = Annotated[Identity, Depends(identity_dependency)]
    DB = Annotated[Store, Depends(database_dependency)]
    router = APIRouter(prefix="/v2/artifacts", route_class=SupervisionRoute)

    @router.get("/{artifact_id}/file")
    def download(artifact_id: str, request: Request, user: User, db: DB):
        _queries(request, set())
        try:
            rendered = render_private_artifact_docx(db, user.user_id, artifact_id)
        except ArtifactNotReady:
            raise HTTPException(409, "Checked artifact is not ready for export") from None
        return Response(
            rendered.content,
            media_type=rendered.media_type,
            headers={
                "Content-Disposition": f'attachment; filename="{rendered.filename}"',
                "X-Content-Type-Options": "nosniff",
                "X-Artifact-Id": rendered.artifact_id,
                "X-Artifact-Check-Id": rendered.check_id,
                "X-Artifact-SHA256": rendered.sha256,
            },
        )

    @router.post("/{artifact_id}/revisions")
    def revise(artifact_id: str, body: RevisionIn, request: Request, user: User, db: DB):
        _queries(request, set())
        return db.request_private_artifact_revision(
            user.user_id, artifact_id, body.instructions, body.request_key
        )

    api.include_router(router)
