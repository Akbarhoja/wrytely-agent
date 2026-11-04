"""Student revisions retain v1 and reuse the original checked drafting worker."""

from copy import deepcopy

import pytest
from test_artifacts import assessment
from test_canvas_sync import device as device
from test_drafting import permitted, structured
from test_private_artifact_reads import ready
from test_worker import ScriptedModel

from runtime.worker import run_once
from shared.canvas_reads import SourceRefreshRequired
from shared.config import Settings
from shared.db import QueueFull, RequestConflict


def test_student_revision_produces_checked_v2_without_overwriting_parent(device):
    data, parent = ready(device)
    db = device[0]
    requested = db.request_private_artifact_revision(
        "user_alice", parent["id"], "Use a clearer title", "r1"
    )
    assert (
        db.request_private_artifact_revision(
            "user_alice", parent["id"], "Use a clearer title", "r1"
        )
        == requested
    )
    with pytest.raises(RequestConflict):
        db.request_private_artifact_revision("user_alice", parent["id"], "Different change", "r1")
    revised = deepcopy(data[3])
    revised["title"] = "Revised study draft"
    model = ScriptedModel([permitted(), structured("save_review_draft", revised), assessment()])
    assert run_once(db, model, Settings())
    with db.connection() as conn:
        rows = conn.execute("SELECT * FROM wrytely_agent.artifacts ORDER BY created_at").fetchall()
    assert len(rows) == 2 and rows[0]["draft"] == parent["draft"]
    assert rows[1]["id"] != parent["id"] and rows[1]["draft"]["title"] == "Revised study draft"
    assert rows[1]["state"] == "ready" and rows[1]["task_id"] == requested["task_id"]
    assert not run_once(db, model, Settings())  # no obsolete planner restarts


def test_revision_is_private_paused_and_step_bounded(device):
    _, parent = ready(device)
    db = device[0]
    db.provision("user_bob")
    with pytest.raises(LookupError):
        db.request_private_artifact_revision("user_bob", parent["id"], "Edit title", "r")
    db.set_paused("user_alice", True)
    with pytest.raises(SourceRefreshRequired):
        db.request_private_artifact_revision("user_alice", parent["id"], "Edit title", "r")
    db.set_paused("user_alice", False)
    with db.connection() as conn:
        conn.execute("UPDATE wrytely_agent.responsibilities SET steps_created=max_steps")
    with pytest.raises(QueueFull):
        db.request_private_artifact_revision("user_alice", parent["id"], "Edit title", "r")


def test_unknown_model_failure_does_not_invalidate_a_superseded_planner_as_a_new_failure(device):
    _, parent = ready(device)
    db = device[0]
    db.request_private_artifact_revision("user_alice", parent["id"], "Edit title", "r")
    with db.connection() as conn:
        db._block_failed_responsibilities(conn, parent["agent_id"])
        duty = conn.execute(
            "SELECT status FROM wrytely_agent.responsibilities WHERE id=%s",
            (parent["responsibility_id"],),
        ).fetchone()
    assert duty["status"] == "active"
