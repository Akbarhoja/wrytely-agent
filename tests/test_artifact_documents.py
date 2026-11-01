"""Document provenance is mandatory once declared, including final/cached ready gates."""

from copy import deepcopy
from datetime import UTC, datetime
from uuid import uuid4

import pytest
import test_canvas_evidence as evidence
import test_canvas_sync as sync
from test_artifacts import TEXT, assessment
from test_canvas_documents import save
from test_canvas_reads import collected
from test_canvas_sync import device as device
from test_document_citations import cite
from test_planner import plan
from test_worker import ScriptedModel

from contracts.artifacts import CoursePolicy, DraftArtifact, RubricItem
from contracts.models import SourceObservation
from runtime.document_citations import verify_document_citation_for_task
from runtime.verification import verify_artifact
from runtime.worker import run_once
from shared.config import Settings
from shared.db import LeaseLost, RequestConflict
from shared.document_sections import split_document_text

QUOTE = "Source A reports 10 participants."


def setup(device, *, bound=True, partial=False):
    db = device[0]
    if partial:
        scan = evidence.prepare(device)
        item = evidence.assignment()
        item.update(content=TEXT, coverage="partial", missing=["linked_content_unread"])
        receipt = evidence.upload(device, scan, evidence.body(device, scan, [item]))
        evidence.close(device, scan, receipt, partial=True)
        obj = evidence.rows(device, "canvas_evidence_objects")[0]
    else:
        obj = collected(device, text=TEXT)[0]
    # Synthetic bridge fixture only: use the existing observed version, never a
    # fabricated legacy version. Product activation/consumer wiring remains deferred.
    with db.connection() as conn:
        observed = conn.execute(
            "SELECT version_id FROM wrytely_agent.canvas_evidence_observations WHERE id=%s",
            (obj["latest_observation_id"],),
        ).fetchone()["version_id"]
        conn.execute(
            "UPDATE wrytely_agent.academic_sources SET latest_version_id=%s WHERE id=%s",
            (observed, obj["source_id"]),
        )
    root = save(device, obj, split_document_text(TEXT))
    citation = cite(device, obj, root, quote=QUOTE)
    duty = db.create_responsibility("user_alice", "Compare two sources", "doc-draft")
    source = db.observe_source(
        "user_alice",
        SourceObservation(
            source_key="rubric",
            external_revision="v1",
            title="Assignment",
            reference="synthetic:assignment",
            coverage="snapshot",
            content=TEXT,
            retrieved_at=datetime.now(UTC),
        ),
    )
    db.bind_source("user_alice", duty["id"], source["source_id"])
    if bound:
        db.bind_source("user_alice", duty["id"], obj["source_id"])
    run_once(db, ScriptedModel([plan()]), Settings())
    lease = db.claim()
    draft = DraftArtifact(
        title="Review draft",
        body=QUOTE,
        disclosure="",
        citations=[{"version_id": observed, "claim": QUOTE, "quote": QUOTE}],
    )
    artifact = db.save_draft(lease, draft, "pinned", document_citations=[citation])
    policy = CoursePolicy(
        status="permitted",
        version_id=source["id"],
        quote="AI drafting is permitted with disclosure.",
    )
    rubric = [RubricItem(version_id=source["id"], quote="Compare two sources.")]
    return lease, artifact, policy, rubric, citation, draft


def review(device, prepared, model=None):
    lease, artifact, policy, rubric, *_ = prepared
    return verify_artifact(
        device[0],
        model or ScriptedModel([assessment()]),
        Settings(),
        lease,
        artifact["id"],
        policy=policy,
        rubric=rubric,
    )


def test_pinned_document_is_checked_and_saved_with_exact_proof(device):
    prepared = setup(device)
    report = review(device, prepared)
    assert report["passed"]
    proof = report["document_evidence"][0]
    assert proof["evidence_usable_for_draft"] and proof["citation"] == prepared[4]
    assert device[0].artifact("user_alice", prepared[1]["id"])["state"] == "ready"
    assert device[0].draft_progress(prepared[0], "pinned")[1]["passed"]


def test_document_metadata_replay_cannot_drop_or_replace_provenance(device):
    lease, artifact, _, _, citation, draft = setup(device)
    db = device[0]
    assert (
        db.save_draft(lease, draft, "pinned", document_citations=[citation])["id"] == artifact["id"]
    )
    for refs in ([], [citation | {"segment_id": str(uuid4())}]):
        with pytest.raises(RequestConflict):
            db.save_draft(lease, draft, "pinned", document_citations=refs)


@pytest.mark.parametrize("mutation", ["count", "quote", "offset", "extra", "type"])
def test_malformed_provenance_is_rejected_before_save(device, mutation):
    lease, _, _, _, citation, draft = setup(device)
    refs = [deepcopy(citation)]
    if mutation == "count":
        refs *= 2
    elif mutation == "quote":
        refs[0].update(quote="wrong", end=refs[0]["start"] + 5)
    elif mutation == "offset":
        refs[0]["start"] = True
    elif mutation == "extra":
        refs[0]["identity"] = "user_alice"
    else:
        refs = "not a list"
    with pytest.raises(ValueError):
        device[0].save_draft(lease, draft, "invalid", document_citations=refs)


@pytest.mark.parametrize(
    "change", ["old", "partial", "unbound", "revoke", "scope", "history", "segment", "expiry"]
)
def test_failed_document_check_prevents_model_call(device, change):
    prepared = setup(device, partial=change == "partial", bound=change != "unbound")
    db = device[0]
    if change == "old":
        with db.connection() as conn:
            conn.execute(
                "UPDATE wrytely_agent.canvas_evidence_observations SET "
                "observed_at=clock_timestamp()-interval '7 hours', "
                "received_at=clock_timestamp()-interval '7 hours'"
            )
        # Inspection remains usable; drafting requires the stricter six-hour bound.
        assert verify_document_citation_for_task(db, prepared[0], prepared[4])[
            "evidence_usable_for_inspection"
        ]
    elif change == "revoke":
        db.rotate_or_revoke("user_alice", device[1]["connection_id"])
    elif change == "scope":
        sync.set_scope(device, [], kinds=[])
    elif change == "expiry":
        with db.connection() as conn:
            conn.execute(
                "UPDATE wrytely_agent.source_connections SET "
                "credential_expires_at=clock_timestamp()-interval '1 second'"
            )
    elif change == "history":
        with db.connection() as conn:
            conn.execute("UPDATE wrytely_agent.canvas_evidence_observations SET historical=true")
    elif change == "segment":
        with db.connection() as conn:
            conn.execute(
                "UPDATE wrytely_agent.canvas_document_sections SET "
                "text=repeat('x',end_offset-start_offset)"
            )
    model = ScriptedModel([])
    report = review(device, prepared, model)
    assert not report["passed"] and "document_evidence_missing_or_stale" in report["errors"]
    assert model.histories == []
    assert db.artifact("user_alice", prepared[1]["id"])["state"] == "needs_revision"


def test_connection_change_during_model_review_cannot_commit_ready(device):
    prepared = setup(device)

    class RevokingModel(ScriptedModel):
        def turn(self, *args, **kwargs):
            result = super().turn(*args, **kwargs)
            device[0].rotate_or_revoke("user_alice", device[1]["connection_id"])
            return result

    report = review(device, prepared, RevokingModel([assessment()]))
    assert not report["passed"] and "document_evidence_failed_at_commit" in report["errors"]


def test_cached_passing_report_is_invalidated_when_document_ages(device):
    prepared = setup(device)
    assert review(device, prepared)["passed"]
    with device[0].connection() as conn:
        conn.execute(
            "UPDATE wrytely_agent.canvas_evidence_observations SET "
            "observed_at=clock_timestamp()-interval '7 hours'"
        )
    artifact, report = device[0].draft_progress(prepared[0], "pinned")
    assert not report["passed"] and artifact["state"] == "needs_revision"
    assert "document_evidence_failed_at_commit" in report["errors"]


def test_pause_and_wrong_task_cannot_read_document_proofs(device):
    prepared = setup(device)
    db = device[0]
    with pytest.raises(LookupError):
        db.artifact_document_evidence(prepared[0], uuid4())
    db.set_paused("user_alice", True)
    with pytest.raises(LeaseLost):
        db.artifact_document_evidence(prepared[0], prepared[1]["id"])


def test_refresh_supersedes_running_task_instead_of_reusing_old_proof(device):
    prepared = setup(device)
    scan = evidence.next_scan(device, "actual-change")
    item = evidence.assignment()
    item["content"] = "Changed requirements"
    receipt = evidence.upload(device, scan, evidence.body(device, scan, [item]))
    evidence.close(device, scan, receipt)
    with pytest.raises(LeaseLost):
        review(device, prepared, ScriptedModel([]))
    assert device[0].artifact("user_alice", prepared[1]["id"])["state"] != "ready"


def test_cross_account_artifact_and_document_are_denied(device):
    prepared = setup(device)
    db = device[0]
    db.provision("user_bob")
    duty = db.create_responsibility("user_bob", "Separate student", "bob")
    run_once(db, ScriptedModel([plan()]), Settings())
    bob = db.claim()
    assert bob.user_id == "user_bob"
    with pytest.raises(LookupError):
        db.artifact_document_evidence(bob, prepared[1]["id"])
    artifact = db.save_draft(bob, prepared[5], "bob-draft", document_citations=[prepared[4]])
    with pytest.raises(LookupError):
        db.artifact_document_evidence(bob, artifact["id"])
    assert db.artifact("user_bob", prepared[1]["id"]) is None
    assert duty["agent_id"] == bob.agent_id


def test_final_private_completion_gate_rechecks_documents(device):
    prepared = setup(device)
    db = device[0]
    assert review(device, prepared)["passed"]
    lease, artifact = prepared[:2]
    # Assemble only the existing private-completion relationship in the disposable
    # fixture. This is a gate test, not evidence of document-aware generation.
    with db.connection() as conn:
        conn.execute(
            "INSERT INTO wrytely_agent.private_draft_intents "
            "(responsibility_id,agent_id,memory_revision,max_revisions,drafting_task_id) "
            "VALUES (%s,%s,%s,1,%s)",
            (
                artifact["responsibility_id"],
                lease.agent_id,
                artifact["memory_revision"],
                lease.task_id,
            ),
        )
        conn.execute("UPDATE wrytely_agent.tasks SET status='done' WHERE id=%s", (lease.task_id,))
        assert db._private_draft_ready(conn, lease)
    db.rotate_or_revoke("user_alice", device[1]["connection_id"])
    with db.connection() as conn:
        assert not db._private_draft_ready(conn, lease)


def test_same_quote_in_different_bound_source_cannot_impersonate_document(device):
    prepared = setup(device)
    lease, _, policy, rubric, citation, draft = prepared
    unrelated = draft.model_copy(deep=True)
    unrelated.citations[0].version_id = policy.version_id
    artifact = device[0].save_draft(lease, unrelated, "wrong-origin", document_citations=[citation])
    model = ScriptedModel([])
    report = verify_artifact(
        device[0], model, Settings(), lease, artifact["id"], policy=policy, rubric=rubric
    )
    assert not report["passed"] and "document_evidence_missing_or_stale" in report["errors"]
    assert model.histories == []
