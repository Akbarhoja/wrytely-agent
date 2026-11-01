"""Real scoped document publications through the existing scripted draft workflow."""

from dataclasses import asdict

import pytest
import test_canvas_evidence as evidence
import test_canvas_sync as sync
from test_artifacts import TEXT, assessment
from test_canvas_document_publication import page
from test_canvas_document_uploads import begin, begin_body, finish, finish_body, put, put_body
from test_canvas_sync import device as device
from test_drafting import permitted, structured
from test_planner import plan
from test_worker import ScriptedModel

from contracts.document_artifacts import CoursePolicyV2, DraftArtifactV2, RubricItemV2
from runtime.worker import run_once
from shared.config import Settings
from shared.document_sections import split_document_text

POLICY = "AI drafting is permitted with disclosure."
RUBRIC = "Compare two sources."
CLAIM = "Source A reports 10 participants."
OTHER = "Source B reports 12 participants."
DISCLOSURE = "Draft prepared with AI; review required."


def publish(device, *, text=TEXT, partial=False, mixed=False, scan=None, due=None):
    if scan is None:
        scan = evidence.prepare(device, kinds=["announcements", "assignments"] if mixed else None)
    inline = None
    if mixed:
        item = dict(
            kind="announcement",
            provider_id="71",
            provider_updated_at=None,
            title="Synthetic evidence",
            reference=sync.ORIGIN + "/courses/101/discussion_topics/71",
            content=OTHER,
            coverage="complete",
            missing=[],
            fields={"author_role": "instructor", "posted_at": None, "announcement_id": "71"},
        )
        receipt = evidence.upload(
            device, scan, evidence.body(device, scan, [item], kind="announcements")
        )
        scan["checkpoint"] = receipt["checkpoint"]
        sync.finish_resource(device, scan, key="101/announcements", finish_key="end-announcements")
        inline = {
            **receipt["observations"][0],
            "object_id": str(evidence.rows(device, "canvas_evidence_objects")[0]["id"]),
        }
    document = split_document_text(text)
    body = begin_body(device, scan)
    if due is not None:
        body["object_fields"]["due_at"] = due
    body["metadata"].update(
        total_characters=len(text),
        total_pages=None,
        coverage="partial" if partial else "complete",
        missing=["linked_content_unread"] if partial else [],
    )
    body["manifest"] = [
        {k: v for k, v in asdict(s).items() if k != "text"} for s in document.sections
    ]
    upload = begin(device, body)
    put(
        device,
        put_body(
            body,
            upload["upload_id"],
            parts=[{"slot": s.slot, "text": s.text} for s in document.sections],
        ),
    )
    finish(device, finish_body(body, upload["upload_id"]))
    receipt = evidence.upload(device, scan, page(device, scan, body, upload))
    evidence.close(device, scan, receipt, partial=partial)
    return receipt["observations"][0], inline


def ref(device, observed, quote):
    from runtime.document_quote_search import find_document_quotes

    result = find_document_quotes(
        device[0],
        "user_alice",
        observed["object_id"],
        observation_id=observed["observation_id"],
        document_version_id=observed["document_version_id"],
        quote=quote,
        max_pages=8,
        max_matches=1,
    )
    return {"kind": "canvas_document", **result["matches"][0]["citation"]}


def prepared(device, *, rubric_quote=RUBRIC, **kwargs):
    doc, inline = publish(device, **kwargs)
    db = device[0]
    duty = db.create_canvas_draft_responsibility(
        "user_alice",
        "Prepare a private comparison draft",
        "typed-duty",
        object_ids=[doc["object_id"]] + ([inline["object_id"]] if inline else []),
    )
    policy = dict(status="disclosure_required", evidence=ref(device, doc, POLICY))
    rubric = [dict(evidence=ref(device, doc, rubric_quote))]
    citations = [dict(claim=CLAIM, evidence=ref(device, doc, CLAIM))]
    body = CLAIM
    if inline:
        citations.append(
            dict(
                claim=OTHER,
                evidence=dict(kind="legacy", version_id=inline["version_id"], quote=OTHER),
            )
        )
        body += " " + OTHER
    draft = dict(
        schema_version=2,
        title="Private review",
        body=body + "\n" + DISCLOSURE,
        citations=citations,
        disclosure=DISCLOSURE,
    )
    return duty, policy, rubric, draft, doc, inline


def requirements(policy, rubric):
    return structured(
        "assess_draft_requirements",
        dict(
            policy=policy,
            rubric=rubric,
            reason="Explicit permission and complete quoted requirements.",
        ),
    )


def planner_stage(device, data):
    duty, policy, rubric, *_ = data
    model = ScriptedModel(
        [
            requirements(policy, rubric),
            plan("draft", "comparison", "Prepare a private checked draft"),
        ]
    )
    assert run_once(device[0], model, Settings())
    assert len(model.histories) == 2
    return duty


def test_document_only_workflow_saves_checked_v2_without_fake_legacy_versions(device):
    data = prepared(device)
    db = device[0]
    duty = planner_stage(device, data)
    draft = data[3]
    model = ScriptedModel([permitted(), structured("save_review_draft", draft), assessment()])
    assert run_once(db, model, Settings())
    assert len(model.histories) == 3
    with db.connection() as conn:
        artifact = conn.execute("SELECT * FROM wrytely_agent.artifacts").fetchone()
        checks = conn.execute("SELECT report FROM wrytely_agent.artifact_checks").fetchone()[
            "report"
        ]
        assert (
            conn.execute("SELECT count(*) AS n FROM wrytely_agent.source_versions").fetchone()["n"]
            == 0
        )
    assert artifact["evidence_schema"] == 2 and artifact["state"] == "ready"
    assert (
        DraftArtifactV2.model_validate(artifact["draft"]).citations[0].evidence.kind
        == "canvas_document"
    )
    assert checks["passed"] and checks["evidence_schema"] == 2
    assert db.artifact("user_alice", artifact["id"]) is None
    assert db.artifact_review("user_alice", artifact["id"]) is None
    assert db.responsibility_artifacts("user_alice", duty["id"]) == []
    assert run_once(db, ScriptedModel([plan("done", "review-ready", "")]), Settings())
    with db.connection() as conn:
        assert (
            conn.execute(
                "SELECT status FROM wrytely_agent.responsibilities WHERE id=%s", (duty["id"],)
            ).fetchone()["status"]
            == "done"
        )


def test_mixed_document_and_actual_inline_version_evidence_stays_typed(device):
    data = prepared(device, mixed=True)
    planner_stage(device, data)
    model = ScriptedModel(
        [
            permitted(),
            structured("save_review_draft", data[3]),
            assessment(claim_support=["supported", "supported"]),
        ]
    )
    assert run_once(device[0], model, Settings())
    with device[0].connection() as conn:
        artifact = conn.execute("SELECT * FROM wrytely_agent.artifacts").fetchone()
        versions = conn.execute("SELECT * FROM wrytely_agent.source_versions").fetchall()
        assert len(versions) == 1
        assert (
            conn.execute("SELECT latest_version_id FROM wrytely_agent.academic_sources").fetchone()[
                "latest_version_id"
            ]
            is None
        )
    assert artifact["state"] == "ready"
    assert {c["evidence"]["kind"] for c in artifact["draft"]["citations"]} == {
        "legacy",
        "canvas_document",
    }


def test_partial_original_context_blocks_before_any_model_call(device):
    data = prepared(device, partial=True)
    model = ScriptedModel([])
    assert run_once(device[0], model, Settings())
    assert model.histories == []
    assert device[0].draft_responsibility_status("user_alice", data[0]["id"])["status"] == "blocked"


def academic_lease(device, data):
    planner_stage(device, data)
    lease = device[0].claim()
    assert lease
    return lease


def generate(device, data, lease, model, **kwargs):
    from runtime.drafting import generate_checked_draft

    return generate_checked_draft(
        device[0],
        model,
        Settings(),
        lease,
        workflow_key="typed-work",
        policy=CoursePolicyV2.model_validate(data[1]),
        rubric=[RubricItemV2.model_validate(r) for r in data[2]],
        **kwargs,
    )


def test_saved_v2_draft_resumes_without_repeated_calls_and_cached_pass_rechecks_age(device):
    data = prepared(device)
    lease = academic_lease(device, data)
    db = device[0]
    model = ScriptedModel([permitted(), structured("save_review_draft", data[3]), assessment()])
    result = generate(device, data, lease, model)
    assert result["state"] == "ready"
    resumed = ScriptedModel([])
    assert generate(device, data, lease, resumed)["artifact_id"] == result["artifact_id"]
    assert resumed.histories == []
    with db.connection() as conn:
        conn.execute(
            "UPDATE wrytely_agent.canvas_evidence_observations SET "
            "observed_at=clock_timestamp()-interval '7 hours'"
        )
    assert generate(device, data, lease, resumed)["state"] == "blocked"
    artifact, report = db.draft_progress(lease, "typed-work:0")
    assert artifact["state"] == "needs_revision" and not report["passed"]
    assert "typed_evidence_failed_at_commit" in report["errors"]
    assert resumed.histories == []


def test_generation_interruption_recovers_saved_typed_draft_before_assessment(device):
    data = prepared(device)
    lease = academic_lease(device, data)
    model = ScriptedModel(
        [permitted(), structured("save_review_draft", data[3]), RuntimeError("Interrupted")]
    )
    with pytest.raises(RuntimeError, match="Interrupted"):
        generate(device, data, lease, model)
    resumed = ScriptedModel([assessment()])
    result = generate(device, data, lease, resumed)
    assert result["state"] == "ready" and len(resumed.histories) == 1


def test_bad_quote_never_reaches_semantic_assessment_or_readiness(device):
    from copy import deepcopy

    data = prepared(device)
    lease = academic_lease(device, data)
    bad = deepcopy(data[3])
    bad["citations"][0]["evidence"]["start"] += 1
    bad["citations"][0]["evidence"]["end"] += 1
    model = ScriptedModel([permitted(), structured("save_review_draft", bad)])
    result = generate(device, data, lease, model, max_revisions=0)
    assert result["state"] == "needs_revision"
    assert "citation_missing_or_stale" in result["report"]["errors"]
    assert len(model.histories) == 2


def test_review_does_not_override_denied_policy_preflight(device):
    data = prepared(device)
    lease = academic_lease(device, data)
    model = ScriptedModel(
        [structured("assess_drafting_permission", {"allowed": False, "reason": "Policy unclear."})]
    )
    assert generate(device, data, lease, model)["state"] == "blocked"
    with device[0].connection() as conn:
        assert (
            conn.execute("SELECT count(*) AS n FROM wrytely_agent.artifacts").fetchone()["n"] == 0
        )
    assert len(model.histories) == 1


def test_complete_evidence_above_context_budget_requires_investigation_without_inference(device):
    data = prepared(device, text=TEXT + "x" * 85000)
    model = ScriptedModel([])
    assert run_once(device[0], model, Settings())
    assert model.histories == []
    with device[0].connection() as conn:
        row = conn.execute(
            "SELECT status,status_reason FROM wrytely_agent.responsibilities WHERE id=%s",
            (data[0]["id"],),
        ).fetchone()
    assert row["status"] == "blocked"
    assert row["status_reason"] == "evidence_context_requires_paged_investigation"


@pytest.mark.parametrize("change", ["revoke", "expiry", "pause"])
def test_control_changes_during_review_fence_late_typed_results(device, change):
    from shared.db import LeaseLost

    data = prepared(device)
    lease = academic_lease(device, data)
    db = device[0]

    class ControlledModel(ScriptedModel):
        def turn(self, *args, **kwargs):
            result = super().turn(*args, **kwargs)
            if len(self.histories) == 3:
                if change == "revoke":
                    db.rotate_or_revoke("user_alice", device[1]["connection_id"])
                elif change == "pause":
                    db.set_paused("user_alice", True)
                else:
                    with db.connection() as conn:
                        conn.execute(
                            "UPDATE wrytely_agent.source_connections SET "
                            "credential_expires_at=clock_timestamp()-interval '1 second'"
                        )
            return result

    model = ControlledModel([permitted(), structured("save_review_draft", data[3]), assessment()])
    with pytest.raises(LeaseLost):
        generate(device, data, lease, model)
    with db.connection() as conn:
        assert (
            conn.execute("SELECT state FROM wrytely_agent.artifacts").fetchone()["state"] != "ready"
        )


def test_evidence_aging_during_review_fails_atomic_ready_commit(device):
    data = prepared(device)
    lease = academic_lease(device, data)
    db = device[0]

    class AgingModel(ScriptedModel):
        def turn(self, *args, **kwargs):
            result = super().turn(*args, **kwargs)
            if len(self.histories) == 3:
                with db.connection() as conn:
                    conn.execute(
                        "UPDATE wrytely_agent.canvas_evidence_observations SET "
                        "observed_at=clock_timestamp()-interval '7 hours'"
                    )
            return result

    model = AgingModel([permitted(), structured("save_review_draft", data[3]), assessment()])
    result = generate(device, data, lease, model)
    assert result["state"] == "blocked"
    assert "typed_evidence_failed_at_commit" in result["report"]["errors"]
    assert len(model.histories) == 3


def test_review_receives_original_structured_rubric_and_can_reject_incomplete_rubric(device):
    import json

    data = prepared(device)
    lease = academic_lease(device, data)
    model = ScriptedModel(
        [permitted(), structured("save_review_draft", data[3]), assessment(rubric_complete=False)]
    )
    result = generate(device, data, lease, model, max_revisions=0)
    assert result["state"] == "needs_revision"
    payload = json.loads(model.histories[-1][-1]["content"])
    source = payload["sources"][0]
    assert "rubric" in source["fields"] and source["fields"]["rubric"]
    assert "rubric_incomplete" in result["report"]["errors"]


def test_checked_v2_revision_reuses_workflow_and_preserves_original_artifact(device):
    from copy import deepcopy

    data = prepared(device)
    lease = academic_lease(device, data)
    revised = deepcopy(data[3])
    revised["title"] = "Revised private review"
    model = ScriptedModel(
        [
            permitted(),
            structured("save_review_draft", data[3]),
            assessment(rubric_coverage=["missing"]),
            structured("save_review_draft", revised),
            assessment(),
        ]
    )
    result = generate(device, data, lease, model)
    assert result["state"] == "ready" and len(model.histories) == 5
    with device[0].connection() as conn:
        rows = conn.execute(
            "SELECT draft,state FROM wrytely_agent.artifacts ORDER BY created_at"
        ).fetchall()
    assert len(rows) == 2 and rows[0]["state"] == "needs_revision" and rows[1]["state"] == "ready"
    assert rows[0]["draft"] == data[3] and rows[1]["draft"] == revised


def test_unknown_policy_blocks_requirement_stage_without_generating_an_artifact(device):
    data = prepared(device)
    policy = data[1] | {"status": "unknown"}
    model = ScriptedModel([requirements(policy, data[2])])
    assert run_once(device[0], model, Settings())
    assert len(model.histories) == 1
    with device[0].connection() as conn:
        assert (
            conn.execute("SELECT count(*) AS n FROM wrytely_agent.artifacts").fetchone()["n"] == 0
        )


def test_unbound_opaque_document_ids_cannot_be_used_as_policy_evidence(device):
    from uuid import uuid4

    data = prepared(device)
    lease = academic_lease(device, data)
    data[1]["evidence"]["object_id"] = str(uuid4())
    model = ScriptedModel([])
    assert generate(device, data, lease, model)["state"] == "blocked"
    assert model.histories == []


def test_typed_workflow_spec_and_artifact_request_keys_cannot_change_on_replay(device):
    from shared.db import RequestConflict

    data = prepared(device)
    lease = academic_lease(device, data)
    model = ScriptedModel([permitted(), structured("save_review_draft", data[3]), assessment()])
    assert generate(device, data, lease, model)["state"] == "ready"
    with pytest.raises(RequestConflict):
        generate(device, data, lease, ScriptedModel([]), max_revisions=1)
    draft = DraftArtifactV2.model_validate(data[3])
    same = device[0].save_draft(lease, draft, "typed-work:0")
    assert same["evidence_schema"] == 2
    draft.title = "Different draft"
    with pytest.raises(RequestConflict):
        device[0].save_draft(lease, draft, "typed-work:0")
    with pytest.raises(ValueError, match="Typed artifacts"):
        device[0].artifact_document_evidence(lease, same["id"])


def test_partial_context_cannot_be_forged_as_a_passed_v2_commit(device):
    data = prepared(device)
    lease = academic_lease(device, data)
    db = device[0]
    model = ScriptedModel([permitted(), structured("save_review_draft", data[3]), assessment()])
    result = generate(device, data, lease, model)
    with db.connection() as conn:
        conn.execute(
            "UPDATE wrytely_agent.canvas_resources SET coverage='partial' "
            "WHERE resource_key='101/assignments'"
        )
    row, _ = db.artifact_verification_input(lease, result["artifact_id"])
    committed = db._commit_artifact_check(
        lease, row["id"], row["memory_revision"], result["report"]
    )
    assert not committed["passed"]
    assert "typed_evidence_failed_at_commit" in committed["errors"]


def test_stale_source_after_requirement_model_call_blocks_assessment_commit(device):
    data = prepared(device)

    class AgingRequirements(ScriptedModel):
        def turn(self, *args, **kwargs):
            result = super().turn(*args, **kwargs)
            with device[0].connection() as conn:
                conn.execute(
                    "UPDATE wrytely_agent.canvas_evidence_observations SET "
                    "observed_at=clock_timestamp()-interval '7 hours'"
                )
            return result

    model = AgingRequirements([requirements(data[1], data[2])])
    assert run_once(device[0], model, Settings())
    assert len(model.histories) == 1
    with device[0].connection() as conn:
        assert (
            conn.execute("SELECT assessment FROM wrytely_agent.private_draft_intents").fetchone()[
                "assessment"
            ]
            is None
        )
        assert (
            conn.execute("SELECT count(*) AS n FROM wrytely_agent.drafting_requests").fetchone()[
                "n"
            ]
            == 0
        )


def test_changed_requirement_metadata_during_review_revokes_typed_draft_lease(device):
    from shared.db import LeaseLost

    data = prepared(device)
    lease = academic_lease(device, data)

    class ChangingRequirements(ScriptedModel):
        def turn(self, *args, **kwargs):
            result = super().turn(*args, **kwargs)
            if len(self.histories) == 3:
                scan = evidence.next_scan(device, "changed-while-reviewing")
                newer, _ = publish(device, scan=scan, due="2026-01-04T00:00:00Z")
                assert newer["document_version_id"] != data[4]["document_version_id"]
            return result

    model = ChangingRequirements(
        [permitted(), structured("save_review_draft", data[3]), assessment()]
    )
    with pytest.raises(LeaseLost):
        generate(device, data, lease, model)
    with device[0].connection() as conn:
        assert (
            conn.execute("SELECT state FROM wrytely_agent.artifacts").fetchone()["state"] != "ready"
        )


def test_typed_word_count_checks_keep_document_provenance_in_format_report(device):
    words = "Write 10–20 words."
    data = prepared(device, text=TEXT.replace(RUBRIC, words), rubric_quote=words)
    lease = academic_lease(device, data)
    model = ScriptedModel([permitted(), structured("save_review_draft", data[3]), assessment()])
    result = generate(device, data, lease, model)
    assert result["state"] == "ready"
    rule = result["report"]["deterministic_checks"]["word_ranges"][0]
    assert rule["evidence"]["kind"] == "canvas_document"
    assert "version_id" not in rule and rule["minimum"] == 10 and rule["maximum"] == 20


def test_final_private_completion_cannot_reuse_an_aged_typed_draft(device):
    data = prepared(device)
    planner_stage(device, data)
    assert run_once(
        device[0],
        ScriptedModel([permitted(), structured("save_review_draft", data[3]), assessment()]),
        Settings(),
    )

    class AgingCompletion(ScriptedModel):
        def turn(self, *args, **kwargs):
            result = super().turn(*args, **kwargs)
            with device[0].connection() as conn:
                conn.execute(
                    "UPDATE wrytely_agent.canvas_evidence_observations SET "
                    "observed_at=clock_timestamp()-interval '7 hours'"
                )
            return result

    model = AgingCompletion([plan("done", "review-ready", "")])
    assert run_once(device[0], model, Settings())
    assert len(model.histories) == 1
    assert device[0].draft_responsibility_status("user_alice", data[0]["id"])["status"] == "blocked"


def test_context_read_checks_task_clock_after_loading_original_sections(device, monkeypatch):
    from shared.db import LeaseLost

    prepared(device)
    db = device[0]
    lease = db.claim()
    original = db._load_canvas_document

    def expire(conn, *args, **kwargs):
        result = original(conn, *args, **kwargs)
        conn.execute(
            "UPDATE wrytely_agent.tasks SET lease_until=clock_timestamp()-interval '1 second' "
            "WHERE id=%s",
            (lease.task_id,),
        )
        return result

    monkeypatch.setattr(db, "_load_canvas_document", expire)
    with pytest.raises(LeaseLost):
        db.draft_intent_sources(lease)


def test_original_document_beyond_legacy_text_limit_uses_later_exact_section(device):
    import json

    text = POLICY + " " + RUBRIC + "\n" + "x" * 30000 + "\n" + CLAIM
    data = prepared(device, text=text)
    lease = academic_lease(device, data)
    model = ScriptedModel([permitted(), structured("save_review_draft", data[3]), assessment()])
    result = generate(device, data, lease, model)
    assert result["state"] == "ready"
    claim = next(p for p in result["report"]["typed_evidence"] if p["evidence"]["quote"] == CLAIM)
    assert claim["evidence"]["slot"] == 1 and claim["evidence"]["start"] > 30000
    source = json.loads(model.histories[0][-1]["content"])["sources"][0]
    assert len(source["sections"]) == 2
    assert "".join(s["text"] for s in source["sections"]) == text


def test_document_root_uuid_is_never_accepted_as_a_legacy_source_version(device):
    data = prepared(device)
    lease = academic_lease(device, data)
    data[1]["evidence"] = dict(
        kind="legacy", version_id=data[4]["document_version_id"], quote=POLICY
    )
    model = ScriptedModel([])
    assert generate(device, data, lease, model)["state"] == "blocked"
    assert model.histories == []
    with device[0].connection() as conn:
        assert (
            conn.execute("SELECT count(*) AS n FROM wrytely_agent.source_versions").fetchone()["n"]
            == 0
        )
