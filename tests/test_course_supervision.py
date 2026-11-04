"""Real Store integration: course scope, durable calls, offers and acceptance."""

import json
from uuid import uuid4

import pytest
from test_canvas_object_scope import published
from test_canvas_reads import collected
from test_canvas_sync import device as device

from contracts.course_supervision import CourseDecision
from contracts.models import ModelTurn
from runtime.supervisor import run_course_supervision_once
from shared.canvas_reads import SourceRefreshRequired


def decision(action, obj="", message="", slot=0):
    return CourseDecision(
        action=action,
        reason="Evidence-based next action",
        object_id=str(obj),
        first_slot=slot,
        message=message,
        next_check_seconds=60,
    )


class Model:
    def __init__(self, choice):
        self.choice, self.calls = choice, 0

    def turn(self, history, tools):
        self.calls += 1
        assert tools[0]["name"] == "record_course_decision"
        assert "token" not in json.loads(history[-1]["content"])
        return ModelTurn(
            output=[
                dict(
                    type="function_call",
                    name="record_course_decision",
                    arguments=self.choice.model_dump_json(),
                )
            ],
            text="",
        )


def setup(device, *, limit=6, document=False):
    observed = published(device) if document else collected(device)[0]
    obj = observed["object_id"] if document else observed["id"]
    db = device[0]
    monitor = db.enable_course_supervision(
        "user_alice", device[1]["connection_id"], "101", call_limit=limit
    )
    return db, monitor, obj


def due(db, monitor):
    with db.connection() as conn:
        conn.execute(
            "UPDATE wrytely_agent.course_supervisions SET next_check_at=now() WHERE id=%s",
            (monitor["id"],),
        )


@pytest.mark.parametrize("document", [False, True])
def test_model_investigates_then_offers_without_student_prompt(device, document):
    db, monitor, obj = setup(device, document=document)
    assert (
        run_course_supervision_once(
            db, Model(decision("inspect", obj)), "user_alice", monitor["id"]
        )["state"]
        == "ready"
    )
    result = run_course_supervision_once(
        db, Model(decision("offer", obj, "Prepare a study draft?")), "user_alice", monitor["id"]
    )
    assert result["calls_reserved"] == 2
    status = db.course_supervision_status("user_alice", monitor["id"])
    assert len(status["offers"]) == 1 and status["offers"][0]["state"] == "pending"
    offer = status["offers"][0]
    accepted = db.decide_course_offer("user_alice", monitor["id"], offer["id"], accept=True)
    assert accepted["draft_request"]["object_ids"] == [str(obj)]
    assert db.decide_course_offer("user_alice", monitor["id"], offer["id"], accept=True) == accepted
    with db.connection() as conn:
        assert (
            conn.execute("SELECT count(*) AS n FROM wrytely_agent.responsibilities").fetchone()["n"]
            == 0
        )
    # Explicit delegation uses the EXISTING workflow. Offering alone created none.
    a = db.create_canvas_draft_responsibility("user_alice", **accepted["draft_request"])
    b = db.create_canvas_draft_responsibility("user_alice", **accepted["draft_request"])
    assert a["id"] == b["id"]


def test_restart_duplicate_offer_and_no_refill(device):
    db, monitor, obj = setup(device, limit=3)
    run_course_supervision_once(db, Model(decision("inspect", obj)), "user_alice", monitor["id"])
    for _ in range(2):
        due(db, monitor)
        run_course_supervision_once(
            db, Model(decision("offer", obj, "Need a draft?")), "user_alice", monitor["id"]
        )
    assert len(db.course_supervision_status("user_alice", monitor["id"])["offers"]) == 1
    db.enable_course_supervision("user_alice", device[1]["connection_id"], "101", call_limit=20)
    due(db, monitor)
    model = Model(decision("wait"))
    assert run_course_supervision_once(db, model, "user_alice", monitor["id"]) is None
    assert model.calls == 0
    assert db.course_supervision_status("user_alice", monitor["id"])["reason"] == "call_limit"


def test_cross_account_and_course_rejected(device):
    db, monitor, _ = setup(device)
    db.provision("user_bob")
    with pytest.raises(LookupError):
        db.claim_course_supervision("user_bob", monitor["id"])
    with pytest.raises(SourceRefreshRequired):
        db.enable_course_supervision("user_alice", device[1]["connection_id"], "999")
    with pytest.raises(LookupError):
        db.course_supervision_status("user_bob", monitor["id"])


def test_owned_course_lookup_is_read_only_and_survives_pause_and_disconnect(device):
    db, linked = device
    assert db.find_course_supervision("user_alice", linked["connection_id"], "101") is None
    db, monitor, _ = setup(device)
    run_course_supervision_once(db, Model(decision("wait")), "user_alice", monitor["id"])
    expected = db.course_supervision_status("user_alice", monitor["id"])
    assert db.find_course_supervision("user_alice", linked["connection_id"], "101") == expected
    assert db.find_course_supervision("user_alice", linked["connection_id"], "999") is None
    db.provision("user_bob")
    with pytest.raises(LookupError):
        db.find_course_supervision("user_bob", linked["connection_id"], "101")
    db.pause_course_supervision("user_alice", monitor["id"])
    db.rotate_or_revoke("user_alice", linked["connection_id"])
    recovered = db.find_course_supervision("user_alice", linked["connection_id"], "101")
    assert recovered["state"] == "paused" and recovered["calls_reserved"] == 1
    assert not {"agent_id", "lease_token", "inspections", "snapshot_digest"} & recovered.keys()


def test_pause_fences_inflight_and_remains_possible_after_disconnect(device):
    db, monitor, _ = setup(device)
    claim = db.claim_course_supervision("user_alice", monitor["id"])
    db.pause_course_supervision("user_alice", monitor["id"])
    with pytest.raises(SourceRefreshRequired):
        db.finish_course_supervision("user_alice", claim, decision("wait"))
    db.rotate_or_revoke("user_alice", device[1]["connection_id"])
    assert db.pause_course_supervision("user_alice", monitor["id"])["state"] == "paused"


def test_lost_inference_is_held_without_retry(device):
    db, monitor, _ = setup(device)
    db.claim_course_supervision("user_alice", monitor["id"])
    with db.connection() as conn:
        conn.execute(
            "UPDATE wrytely_agent.course_supervisions SET lease_until=now()-interval '1s' "
            "WHERE id=%s",
            (monitor["id"],),
        )
    model = Model(decision("wait"))
    assert run_course_supervision_once(db, model, "user_alice", monitor["id"]) is None
    status = db.course_supervision_status("user_alice", monitor["id"])
    assert status["calls_reserved"] == 1 and status["reason"] == "inference_outcome_unknown"
    assert model.calls == 0


def test_uninspected_or_foreign_offer_cannot_create_work(device):
    db, monitor, obj = setup(device)
    with pytest.raises(ValueError, match="inspected"):
        run_course_supervision_once(
            db, Model(decision("offer", obj, "Do work")), "user_alice", monitor["id"]
        )
    assert db.course_supervision_status("user_alice", monitor["id"])["offers"] == []


def test_foreign_inspection_cannot_read_other_course(device):
    db, monitor, _ = setup(device)
    with pytest.raises(ValueError, match="outside"):
        run_course_supervision_once(
            db, Model(decision("inspect", uuid4())), "user_alice", monitor["id"]
        )
    assert db.course_supervision_status("user_alice", monitor["id"])["state"] == "blocked"


def test_changed_source_fences_a_model_decision_and_clears_investigation(device):
    import test_canvas_evidence as evidence

    db, monitor, obj = setup(device)
    run_course_supervision_once(db, Model(decision("inspect", obj)), "user_alice", monitor["id"])
    claim = db.claim_course_supervision("user_alice", monitor["id"])
    scan = evidence.next_scan(device, "updated-source")
    item = evidence.assignment()
    item["content"] = "New instructions and deadline."
    receipt = evidence.upload(device, scan, evidence.body(device, scan, [item]))
    evidence.close(device, scan, receipt)
    with pytest.raises(SourceRefreshRequired):
        db.finish_course_supervision("user_alice", claim, decision("offer", obj, "Stale offer"))
    assert db.course_supervision_status("user_alice", monitor["id"])["offers"] == []


def test_restart_restores_due_time_without_a_new_prompt(device):
    from shared.db import Store

    db, monitor, _ = setup(device)
    run_course_supervision_once(db, Model(decision("wait")), "user_alice", monitor["id"])
    restarted = Store(db._url, canvas_origins=tuple(db._canvas_origins))
    assert restarted.due_course_supervisions() == []
    due(db, monitor)
    assert restarted.due_course_supervisions() == [{"id": monitor["id"], "user_id": "user_alice"}]
    assert (
        run_course_supervision_once(
            restarted, Model(decision("wait")), "user_alice", monitor["id"]
        )["calls_reserved"]
        == 2
    )


@pytest.mark.parametrize("document", [False, True])
def test_supervisor_can_inspect_current_partial_originals_without_authorizing_work(
    device, document
):
    import test_canvas_evidence as evidence

    scan = evidence.prepare(device)
    if document:
        from test_canvas_document_publication import page
        from test_canvas_document_uploads import (
            begin,
            begin_body,
            finish,
            finish_body,
            put,
            put_body,
        )

        body = begin_body(device, scan)
        body["metadata"].update(coverage="partial", missing=["html_text_only"])
        upload = begin(device, body)
        put(device, put_body(body, upload["upload_id"]))
        finish(device, finish_body(body, upload["upload_id"]))
        receipt = evidence.upload(device, scan, page(device, scan, body, upload))
        obj = receipt["observations"][0]["object_id"]
    else:
        item = evidence.assignment()
        item.update(coverage="partial", missing=["html_text_only"])
        receipt = evidence.upload(device, scan, evidence.body(device, scan, [item]))
        obj = receipt["observations"][0]["object_id"]
    evidence.close(device, scan, receipt, partial=True)
    db = device[0]
    monitor = db.enable_course_supervision("user_alice", device[1]["connection_id"], "101")

    class PartialModel(Model):
        def turn(self, history, tools):
            source = json.loads(history[-1]["content"])["sources"][0]
            assert source["inspection_ready"] and not source["freshness"]["usable"]
            assert source["coverage"] == "partial" and source["missing"] == ["html_text_only"]
            return super().turn(history, tools)

    result = run_course_supervision_once(
        db, PartialModel(decision("inspect", obj)), "user_alice", monitor["id"]
    )
    assert result["state"] == "ready"
    with db.connection() as conn:
        saved = conn.execute(
            "SELECT inspections FROM wrytely_agent.course_supervisions"
        ).fetchone()["inspections"]
    assert str(obj) in saved and saved[str(obj)]["coverage"] == "partial"
    assert not saved[str(obj)]["freshness"]["usable"]
    with pytest.raises(ValueError, match="Complete current evidence"):
        run_course_supervision_once(
            db, Model(decision("offer", obj, "Unsafe work offer")), "user_alice", monitor["id"]
        )
    assert db.course_supervision_status("user_alice", monitor["id"])["offers"] == []
    assert db.course_supervision_status("user_alice", monitor["id"])["state"] == "blocked"
    with db.connection() as conn:
        assert (
            conn.execute("SELECT count(*) AS n FROM wrytely_agent.responsibilities").fetchone()["n"]
            == 0
        )


@pytest.mark.parametrize("mode", ["old", "restricted", "missing", "future"])
def test_partial_inspection_does_not_bypass_source_age_or_restrictions(device, mode):
    db, monitor, _ = setup(device)
    with db.connection() as conn:
        if mode == "old":
            conn.execute(
                "UPDATE wrytely_agent.canvas_evidence_observations "
                "SET observed_at=now()-interval '25h',received_at=now()-interval '25h'"
            )
        elif mode == "future":
            conn.execute(
                "UPDATE wrytely_agent.canvas_evidence_observations "
                "SET observed_at=now()+interval '6 minutes'"
            )
        elif mode == "missing":
            conn.execute(
                "UPDATE wrytely_agent.canvas_evidence_objects SET missing_pending_confirmation=true"
            )
        else:
            conn.execute("UPDATE wrytely_agent.canvas_resources SET coverage='restricted'")
    claim = db.claim_course_supervision("user_alice", monitor["id"])
    assert claim is not None and claim["sources"][0]["inspection_ready"] is False


def test_new_source_wakes_a_future_check_and_known_race_replans_within_same_allowance(device):
    import test_canvas_evidence as evidence

    db, monitor, _ = setup(device)
    run_course_supervision_once(db, Model(decision("wait")), "user_alice", monitor["id"])
    assert db.due_course_supervisions() == []
    scan = evidence.next_scan(device, "deadline-updated")
    item = evidence.assignment()
    item["content"] = "New source evidence"
    receipt = evidence.upload(device, scan, evidence.body(device, scan, [item]))
    evidence.close(device, scan, receipt)
    assert db.due_course_supervisions() == [{"id": monitor["id"], "user_id": "user_alice"}]
    claim = db.claim_course_supervision("user_alice", monitor["id"])
    assert claim is not None  # next_check_at is still in the future
    assert db.reschedule_course_source_change("user_alice", claim)
    resumed = db.claim_course_supervision("user_alice", monitor["id"])
    assert resumed["token"] != claim["token"]
    db.pause_course_supervision("user_alice", monitor["id"])
    assert not db.reschedule_course_source_change("user_alice", resumed)
