"""Private DOCX rendering of a current checked artifact; no external storage/send.

Body text is preserved literally as paragraphs. This is not Markdown, equation,
image or table layout conversion; complex math markup is rejected explicitly.
"""

import hashlib
import json
from dataclasses import dataclass

from contracts.document_artifacts import DraftArtifactV2
from shared.artifact_document import MIME
from shared.artifact_document import render_docx as _docx
from shared.canvas_reads import SourceRefreshRequired


class ArtifactNotReady(ValueError):
    pass


@dataclass(frozen=True)
class RenderedArtifact:
    artifact_id: str
    check_id: str
    filename: str
    media_type: str
    sha256: str
    content: bytes


def _checked_identity(detail):
    artifact = detail["artifact"]
    check = detail.get("latest_check")
    if (
        detail.get("schema_version") != 2
        or artifact["saved_state"] != "ready"
        or artifact["memory_stale"]
        or not check
        or check["report"]["passed"] is not True
        or detail["evidence_status"]["state"] != "current"
        or detail["controls"]["agent_paused"]
        or detail["controls"]["responsibility_status"] not in ("active", "done")
    ):
        raise ArtifactNotReady("Current checked result required")
    return json.dumps(
        [artifact["id"], artifact["memory_revision"], artifact["draft"], check["id"]],
        sort_keys=True,
    )


def render_private_artifact_docx(store, verified_user, artifact_id):
    """M's authenticated HTTP assembler consumes bytes, never a public file URL.

    Re-read ownership, evidence and controls after rendering. Assembly must still
    recheck delivery consent at dispatch; this function grants none.
    """
    before = store.read_private_artifact_v2(verified_user, artifact_id)
    identity = _checked_identity(before)
    draft = DraftArtifactV2.model_validate(before["artifact"]["draft"])
    content = _docx(draft)
    after = store.read_private_artifact_v2(verified_user, artifact_id)
    if _checked_identity(after) != identity:
        raise SourceRefreshRequired()
    return RenderedArtifact(
        artifact_id=str(before["artifact"]["id"]),
        check_id=str(before["latest_check"]["id"]),
        filename=f"wrytely-{before['artifact']['id']}.docx",
        media_type=MIME,
        sha256=hashlib.sha256(content).hexdigest(),
        content=content,
    )
