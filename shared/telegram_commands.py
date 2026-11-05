"""Compose existing scoped academic work inside the original inbound transaction."""

from shared.academic_reads import student_json
from shared.canvas_reads import SourceRefreshRequired


def apply_academic_command(store, conn, owner, command, *, bot_id, update_id):
    """Private ingest helper: caller holds verified owner's agent/link/replay locks.

    No transport IO, model call, alternate Store or WhatsApp authority is involved.
    Expected rejection rolls back command work but preserves its inbound receipt;
    unexpected persistence failure rolls back the entire original ingestion.
    """
    from shared.db import QueueFull, RequestConflict

    try:
        with conn.transaction():
            if command.kind in {"accept_offer", "decline_offer"}:
                offer = conn.execute(
                    "SELECT supervision_id FROM wrytely_agent.course_offers "
                    "WHERE agent_id=%s AND id=%s",
                    (owner["id"], command.target_id),
                ).fetchone()
                if not offer:
                    raise LookupError("Not found")
                result = store.decide_course_offer(
                    owner["user_id"],
                    offer["supervision_id"],
                    command.target_id,
                    accept=command.kind == "accept_offer",
                )
                if result["draft_request"] is not None:
                    duty = store.create_canvas_draft_responsibility(
                        owner["user_id"], **result["draft_request"]
                    )
                    result = {"state": "accepted", "responsibility_id": str(duty["id"])}
                else:
                    result = {"state": "declined"}
            elif command.kind == "revise_artifact":
                result = store.request_private_artifact_revision(
                    owner["user_id"],
                    command.target_id,
                    command.instructions,
                    f"telegram:{bot_id}:{update_id}",
                )
            else:
                raise ValueError("Unsupported command")
    except SourceRefreshRequired:
        return {"state": "rejected", "reason": "source_refresh_required"}
    except (LookupError, ValueError, QueueFull, RequestConflict):
        return {"state": "rejected", "reason": "command_unavailable"}
    return student_json(
        {
            "state": "applied",
            "kind": command.kind,
            "target_id": str(command.target_id),
            "result": result,
        }
    )
