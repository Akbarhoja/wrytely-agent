"""Preparation is grounded in inspected originals, with no draft/offer authority."""

from copy import deepcopy
from uuid import uuid4

import pytest

from contracts.course_supervision import CourseDecision
from shared.canvas_reads import SourceRefreshRequired
from shared.course_preparation import preparation_projection, preparation_record

TEXT = "Build and test the circuit yourself. Show actual results to the TA."


def source(kind="assignment", **changes):
    value = dict(
        object_id=str(uuid4()),
        latest_observation_id=str(uuid4()),
        latest_version_id=None,
        document_version_id=None,
        inspection_ready=True,
        kind=kind,
        provider_id="17",
        title="Synthetic hardware exercise",
        fields={"submission_types": ["online_upload"]},
        coverage="partial",
        resource_coverage="partial",
        missing=["linked_content_unread"],
    )
    return {**value, **changes}


def inspected(s, text=TEXT):
    return dict(
        object_id=s["object_id"],
        observation_id=s["latest_observation_id"],
        section={"text": text, "next_offset": None},
    )


def prepare(target, excerpts=None, **changes):
    value = dict(
        action="prepare",
        reason="Help the student prepare with the available originals",
        object_id=target["object_id"],
        message="",
        first_slot=0,
        next_check_seconds=600,
        preparation=dict(
            excerpts=excerpts
            or [dict(object_id=target["object_id"], quote=TEXT, kind="student_action")],
            questions=["Have you collected your actual measurements?"],
        ),
    )
    return CourseDecision.model_validate({**value, **changes})


def test_partial_readable_original_yields_a_limited_quote_checklist_without_promotion():
    s = source()
    before = deepcopy(s)
    result = preparation_record(prepare(s), [s], {s["object_id"]: inspected(s)})
    assert s == before
    assert result["kind"] == "preparation_checklist"
    assert result["excerpts"][0]["quote"] == TEXT
    assert result["evidence"][0]["missing"] == ["linked_content_unread"]
    assert "not a completed or checked assignment" in result["notice"]
    assert not {"draft_request", "body", "ready", "passed", "policy"} & result.keys()


@pytest.mark.parametrize("action", ["inspect", "wait", "offer"])
def test_preparation_cannot_be_smuggled_through_another_action(action):
    with pytest.raises(ValueError, match="only to prepare"):
        prepare(source(), action=action)


@pytest.mark.parametrize(
    "changes",
    [{"message": "Send now"}, {"first_slot": 1}, {"preparation": None}],
)
def test_preparation_cannot_send_or_misrepresent_an_inspection(changes):
    with pytest.raises(ValueError):
        prepare(source(), **changes)


@pytest.mark.parametrize("missing", [True, False])
def test_preparation_needs_a_prior_current_inspection(missing):
    s = source()
    inspection = {} if missing else {s["object_id"]: inspected(s)}
    if not missing:
        inspection[s["object_id"]]["observation_id"] = str(uuid4())
    with pytest.raises((ValueError, SourceRefreshRequired)):
        preparation_record(prepare(s), [s], inspection)


def test_fabricated_quote_cannot_become_a_checklist_step():
    s = source()
    with pytest.raises(ValueError, match="quote must match"):
        preparation_record(prepare(s), [s], {s["object_id"]: inspected(s, "Other content")})


def test_available_syllabus_must_be_inspected_and_retains_its_policy_gaps():
    s, policy = source(), source("syllabus", missing=["policy_not_fully_read"])
    inspections = {s["object_id"]: inspected(s)}
    with pytest.raises(ValueError, match="inspected originals"):
        preparation_record(prepare(s), [s, policy], inspections)
    inspections[policy["object_id"]] = inspected(policy)
    result = preparation_record(prepare(s), [s, policy], inspections)
    assert any(p["missing"] == ["policy_not_fully_read"] for p in result["evidence"])


@pytest.mark.parametrize("linked", [True, False])
def test_only_files_bound_to_this_assignment_can_supply_quotes(linked):
    s = source()
    file = source("file", fields={"linked_from": ["assignment:17" if linked else "assignment:18"]})
    excerpts = [dict(object_id=file["object_id"], quote=TEXT, kind="review")]
    inspections = {x["object_id"]: inspected(x) for x in [s, file]}
    if linked:
        result = preparation_record(prepare(s, excerpts), [s, file], inspections)
        assert len(result["evidence"]) == 2
    else:
        with pytest.raises(ValueError, match="belong to the target"):
            preparation_record(prepare(s, excerpts), [s, file], inspections)


def test_document_quote_cannot_span_unseen_sections_and_unread_pages_remain_visible():
    s = source(document_version_id=str(uuid4()))
    inspection = dict(
        observation_id=s["latest_observation_id"],
        document_version_id=s["document_version_id"],
        sections=[{"text": TEXT}],
        next_slot=2,
    )
    result = preparation_record(prepare(s), [s], {s["object_id"]: inspection})
    assert result["evidence"][0]["unread_continuation"]
    inspection["document_version_id"] = str(uuid4())
    with pytest.raises(SourceRefreshRequired):
        preparation_record(prepare(s), [s], {s["object_id"]: inspection})


@pytest.mark.parametrize("types", [[], None, ["online_quiz"], ["external_tool"], ["unknown"]])
def test_no_quiz_external_tool_or_unknown_assignment_path(types):
    s = source(fields={"submission_types": types})
    with pytest.raises(ValueError, match="ordinary assignment"):
        preparation_record(prepare(s), [s], {s["object_id"]: inspected(s)})


@pytest.mark.parametrize("mode", ["paused", "not_readable", "new_observation", "new_document"])
def test_saved_checklist_is_historical_after_control_or_source_changes(mode):
    s = source()
    record = preparation_record(prepare(s), [s], {s["object_id"]: inspected(s)})
    assert preparation_projection([record], [s], active=True)[0]["current"]
    if mode == "not_readable":
        s["inspection_ready"] = False
    if mode == "new_observation":
        s["latest_observation_id"] = str(uuid4())
    if mode == "new_document":
        s["document_version_id"] = str(uuid4())
    projected = preparation_projection([record], [s], active=mode != "paused")
    assert not projected[0]["current"]
    assert projected[0]["excerpts"] == record["excerpts"]


def test_same_evidence_has_stable_key_and_changed_partial_observation_does_not():
    s = source()
    original = preparation_record(prepare(s), [s], {s["object_id"]: inspected(s)})
    assert preparation_record(prepare(s), [s], {s["object_id"]: inspected(s)}) == original
    s["latest_observation_id"] = str(uuid4())
    changed = preparation_record(prepare(s), [s], {s["object_id"]: inspected(s)})
    assert changed["key"] != original["key"]


def test_no_arbitrary_generated_body_or_policy_override():
    s = source()
    value = prepare(s).model_dump()
    value["preparation"]["body"] = "Pretend this is the completed lab"
    with pytest.raises(ValueError):
        CourseDecision.model_validate(value)
