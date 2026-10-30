"""Internal M2 orchestration evidence, not live model or connector acceptance.

Breaks caught: lost previous-step context, dropped mandatory review/revision,
duplicate drafts after recovery, cross-account evidence exposure, and fabricated
quotes becoming ready. Only the external model is scripted; Store/worker/checks
and disposable Postgres are real.
"""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from test_artifacts import assessment
from test_drafting import permitted, structured
from test_planner import plan
from test_worker import ScriptedModel, answer

from contracts.artifacts import CoursePolicy, DraftArtifact, RubricItem
from contracts.models import SourceObservation
from runtime.worker import run_once
from shared.config import Settings
from shared.db import Store


@pytest.fixture
def academic_scenario(store, alice):
    fixture = json.loads(
        (Path(__file__).parent / "fixtures/m2_academic.json").read_text(encoding="utf-8")
    )
    duty = store.create_responsibility(
        "user_alice",
        "Take responsibility for Cedar's comparison section. Read the assignment and both "
        "sources, prepare and check a private draft. Do not share or submit it.",
        "m2-scenario",
    )
    versions = {}
    for source in fixture["sources"]:
        row = store.observe_source(
            "user_alice",
            SourceObservation(
                source_key="m2-demo/" + source["key"],
                external_revision="v1",
                title="Fictional " + source["key"],
                reference="synthetic:m2/" + source["key"],
                coverage="snapshot",
                content=source["content"],
                retrieved_at=datetime.now(UTC),
            ),
        )
        versions[source["key"]] = row["id"]
        store.bind_source("user_alice", duty["id"], row["source_id"])
    policy = CoursePolicy(
        status="disclosure_required",
        version_id=versions["assignment"],
        quote="AI drafting is permitted with disclosure. The student must review all claims.",
    )
    rubric = [
        RubricItem(version_id=versions["assignment"], quote=quote)
        for quote in (
            "Write a 250–300 word draft comparing recall outcomes and one limitation.",
            "Compare both studies using their participant counts and reported recall outcomes.",
            "Explain that these results cannot establish which method works best for everyone.",
            "Include at least one exact quotation from each source with its source label.",
            "End with one practical recommendation that acknowledges uncertainty.",
        )
    ]
    draft = DraftArtifact(
        title="Cedar's fictional study comparison",
        body=fixture["body"],
        disclosure=fixture["disclosure"],
        citations=[
            {
                "version_id": versions[key],
                "claim": claim,
                "quote": quote,
            }
            for key, claim, quote in (
                (
                    "source-a",
                    "Source A included 20 participants.",
                    "Source A included 20 participants.",
                ),
                (
                    "source-b",
                    "Source B included 18 participants.",
                    "Source B included 18 participants.",
                ),
                (
                    "source-a",
                    "mean recall of 75 percent",
                    "Mean recall on the study quiz was 75 percent.",
                ),
                (
                    "source-b",
                    "mean recall of 68 percent",
                    "Mean recall on the study quiz was 68 percent.",
                ),
            )
        ],
    )
    return duty, versions, policy, rubric, draft


def review(**changes):
    return assessment(claim_support=["supported"] * 4, rubric_coverage=["covered"] * 5, **changes)


def prepare_draft_task(store, policy, rubric):
    # Trusted assembly setup, not evidence of automatic student/API delegation.
    assert run_once(
        store, ScriptedModel([plan(key="draft", instruction="Prepare the comparison")]), Settings()
    )
    task = next(t for t in store.tasks("user_alice") if t["status"] == "ready")
    store.configure_drafting_task(
        "user_alice", task["id"], policy=policy, rubric=rubric, max_revisions=1
    )
    return task


def test_scenario_continues_to_checked_revision_with_private_persisted_context(
    store, academic_scenario
):
    duty, _, policy, rubric, draft = academic_scenario
    store.provision("user_bob")
    store.observe_source(
        "user_bob",
        SourceObservation(
            source_key="m2-demo/source-a",
            external_revision="v1",
            title="Other student's source",
            reference="synthetic:maple",
            coverage="snapshot",
            content="MAPLE_PRIVATE_SOURCE",
            retrieved_at=datetime.now(UTC),
        ),
    )
    model = ScriptedModel(
        [
            plan(key="compare", instruction="Compare the supplied evidence and limitations"),
            answer(
                "20 versus 18 participants; 75 versus 68 percent. "
                "Different samples prevent causal inference."
            ),
            plan(key="draft", instruction="Prepare a checked comparison using the saved analysis"),
            permitted(),
            structured("save_review_draft", draft.model_dump(mode="json")),
            assessment(claim_support=["supported"] * 4, rubric_coverage=["missing"] * 5),
            structured(
                "save_review_draft",
                draft.model_copy(update={"title": "Revised comparison"}).model_dump(mode="json"),
            ),
            review(),
            plan(action="done", key="ready-for-student-review", instruction=""),
        ]
    )
    # No source/message updates after this point. Each invocation rebuilds Store.
    for _ in range(3):
        assert run_once(Store(store._url), model, Settings())
    task = next(t for t in store.tasks("user_alice") if t["status"] == "ready")
    store.configure_drafting_task(
        "user_alice", task["id"], policy=policy, rubric=rubric, max_revisions=1
    )
    assert run_once(Store(store._url), model, Settings())
    assert run_once(Store(store._url), model, Settings())
    assert not run_once(Store(store._url), ScriptedModel([]), Settings())
    saved_duty = store.responsibilities("user_alice")[0]
    assert saved_duty["id"] == duty["id"]
    assert (saved_duty["status"], saved_duty["steps_created"]) == ("done", 2)
    with store.connection() as conn:
        rows = conn.execute(
            "SELECT id,state FROM wrytely_agent.artifacts ORDER BY created_at"
        ).fetchall()
        reports = conn.execute(
            "SELECT passed FROM wrytely_agent.artifact_checks ORDER BY created_at"
        ).fetchall()
        assert [r["state"] for r in rows] == ["needs_revision", "ready"]
        assert [r["passed"] for r in reports] == [False, True]
        assert (
            conn.execute("SELECT count(*) AS n FROM wrytely_agent.source_versions").fetchone()["n"]
            == 5
        )
        assert not conn.execute("SELECT 1 FROM wrytely_agent.whatsapp_outbound").fetchall()
    artifact = Store(store._url).artifact("user_alice", rows[-1]["id"])
    assert 250 <= len(artifact["draft"]["body"].split()) <= 300
    assert (
        artifact["draft"]["disclosure"]
        == "Draft prepared with Wrytely AI; student review is required."
    )
    assert store.artifact("user_bob", rows[-1]["id"]) is None
    assert store.task("user_bob", task["id"]) is None
    assert store.messages("user_alice") == []
    assert "MAPLE_PRIVATE_SOURCE" not in str(model.histories)
    assert "20 versus 18" in str(model.histories[2])
    assert "rubric_not_covered" in str(model.histories[6])
    assert "ready_for_review" in str(model.histories[-1])


def test_scenario_resumes_interrupted_review_without_duplicate_draft(store, academic_scenario):
    _, _, policy, rubric, draft = academic_scenario
    task = prepare_draft_task(store, policy, rubric)
    interrupted = ScriptedModel(
        [
            permitted(),
            structured("save_review_draft", draft.model_dump(mode="json")),
            RuntimeError("Synthetic review interruption"),
        ]
    )
    assert run_once(store, interrupted, Settings())
    assert store.task("user_alice", task["id"])["status"] == "ready"
    with store.connection() as conn:
        before = conn.execute("SELECT id,state FROM wrytely_agent.artifacts").fetchone()
        assert before["state"] == "review"
        conn.execute("UPDATE wrytely_agent.tasks SET available_at=now() WHERE id=%s", (task["id"],))
    # Only a review response is available. Repeating preflight/generation fails.
    assert run_once(Store(store._url), ScriptedModel([review()]), Settings())
    assert store.task("user_alice", task["id"])["status"] == "done"
    with store.connection() as conn:
        rows = conn.execute("SELECT id,state FROM wrytely_agent.artifacts").fetchall()
        assert rows == [{"id": before["id"], "state": "ready"}]
        assert (
            conn.execute("SELECT count(*) AS n FROM wrytely_agent.artifact_checks").fetchone()["n"]
            == 1
        )


def test_scenario_fabricated_quote_blocks_readiness_and_continuation(store, academic_scenario):
    _, _, policy, rubric, draft = academic_scenario
    task = prepare_draft_task(store, policy, rubric)
    forged = draft.model_copy(
        update={
            "citations": [
                draft.citations[0].model_copy(
                    update={"quote": "This result is universally proven."}
                )
            ]
        }
    )
    model = ScriptedModel(
        [
            permitted(),
            structured("save_review_draft", forged.model_dump(mode="json")),
            structured("save_review_draft", forged.model_dump(mode="json")),
        ]
    )
    assert run_once(store, model, Settings())
    assert store.task("user_alice", task["id"])["status"] == "blocked"
    assert store.responsibilities("user_alice")[0]["status"] == "blocked"
    assert not run_once(Store(store._url), ScriptedModel([]), Settings())
    with store.connection() as conn:
        assert not conn.execute(
            "SELECT 1 FROM wrytely_agent.artifacts WHERE state='ready'"
        ).fetchall()
        reports = conn.execute("SELECT report FROM wrytely_agent.artifact_checks").fetchall()
        assert len(reports) == 2
        assert all("citation_missing_or_stale" in r["report"]["errors"] for r in reports)


def test_missing_required_separate_disclosure_blocks_readiness(store, academic_scenario):
    _, _, policy, rubric, draft = academic_scenario
    task = prepare_draft_task(store, policy, rubric)
    without_body_disclosure = draft.model_copy(update={"disclosure": ""})
    scripted_draft = structured(
        "save_review_draft", without_body_disclosure.model_dump(mode="json")
    )
    assert run_once(store, ScriptedModel([permitted(), scripted_draft, scripted_draft]), Settings())
    assert store.task("user_alice", task["id"])["status"] == "blocked"
    with store.connection() as conn:
        reports = conn.execute("SELECT report FROM wrytely_agent.artifact_checks").fetchall()
        assert len(reports) == 2
        assert all("disclosure_text_mismatch" in row["report"]["errors"] for row in reports)
