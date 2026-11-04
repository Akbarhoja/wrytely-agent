"""Provider protocol failures cannot turn model text into arbitrary actions."""

import json
from uuid import uuid4

import pytest

from contracts.models import ModelTurn
from runtime.supervisor import run_course_supervision_once


class Boundary:
    def __init__(self):
        self.held, self.finished = False, False
        self.claim = {"id": uuid4(), "token": uuid4(), "sources": [], "inspections": {}}

    def claim_course_supervision(self, *args):
        return self.claim

    def hold_course_supervision(self, *args):
        self.held = True

    def finish_course_supervision(self, *args):
        self.finished = True
        return {"state": "ready"}


class Provider:
    def __init__(self, output):
        self.output, self.calls = output, 0

    def turn(self, *args):
        self.calls += 1
        return ModelTurn(output=self.output, text="Pretend everything is completed")


def call(name="record_course_decision", **changes):
    value = dict(
        action="wait",
        reason="No fresh work",
        object_id="",
        first_slot=0,
        message="",
        next_check_seconds=600,
    )
    value.update(changes)
    return dict(type="function_call", name=name, arguments=json.dumps(value))


@pytest.mark.parametrize(
    "output",
    [
        [],
        [call("send_whatsapp")],
        [call(), call()],
        [call(next_check_seconds=0)],
        [call(action="offer", object_id=str(uuid4()), message="Do it")],
    ],
)
def test_invalid_or_unauthorized_action_is_held(output):
    store = Boundary()
    with pytest.raises(ValueError):
        run_course_supervision_once(store, Provider(output), "trusted-user", store.claim["id"])
    assert store.held and not store.finished


def test_not_due_never_calls_provider():
    store, model = Boundary(), Provider([call()])
    store.claim = None
    assert run_course_supervision_once(store, model, "trusted-user", uuid4()) is None
    assert model.calls == 0 and not store.finished


def test_valid_wait_is_persisted_not_claimed_as_external_completion():
    store = Boundary()
    assert run_course_supervision_once(
        store, Provider([call()]), "trusted-user", store.claim["id"]
    ) == {"state": "ready"}
    assert store.finished and not store.held


@pytest.mark.parametrize(
    ("change", "code"),
    [
        (
            {"action": "inspect", "object_id": str(uuid4()), "message": "PRIVATE_SOURCE"},
            "inspection_has_message",
        ),
        ({"message": "PRIVATE_SOURCE"}, "wait_has_target"),
        ({"next_check_seconds": 0}, "greater_than_equal"),
        ({"PRIVATE_FIELD": "PRIVATE_SOURCE"}, "extra_forbidden"),
    ],
)
def test_rejected_decision_reports_safe_issue_without_source_text(change, code, caplog):
    from runtime.supervisor import CourseDecisionRejected

    store = Boundary()
    provider = Provider([call(**change)])
    with pytest.raises(CourseDecisionRejected) as rejected:
        run_course_supervision_once(store, provider, "trusted-user", store.claim["id"])
    evidence = rejected.value.evidence()
    assert evidence["code"] == "course_decision_rejected"
    assert any(item["code"] == code for item in evidence["issues"])
    assert "PRIVATE" not in json.dumps(evidence) + str(rejected.value)
    assert "PRIVATE" not in caplog.text
    assert "course_decision_rejected" in caplog.text
    assert provider.calls == 1 and store.held and not store.finished
    evidence["issues"][0]["code"] = "changed"
    assert rejected.value.evidence()["issues"][0]["code"] != "changed"


@pytest.mark.parametrize("arguments", ["PRIVATE_SOURCE", None, "[]"])
def test_invalid_json_or_shape_is_safely_rejected(arguments):
    from runtime.supervisor import CourseDecisionRejected

    store = Boundary()
    output = call()
    output["arguments"] = arguments
    with pytest.raises(CourseDecisionRejected) as rejected:
        run_course_supervision_once(store, Provider([output]), "trusted-user", store.claim["id"])
    assert "PRIVATE" not in json.dumps(rejected.value.evidence()) + str(rejected.value)
    assert store.held and not store.finished


def test_schema_explains_action_specific_fields_without_relaxing_validation():
    from contracts.course_supervision import CourseDecision
    from runtime.supervisor import INSTRUCTIONS, TOOL

    fields = TOOL["parameters"]["properties"]
    assert "never a Canvas ID" in fields["object_id"]["description"]
    assert "Empty string for inspect/wait" in fields["message"]["description"]
    assert "For inspect, message must be empty" in INSTRUCTIONS
    assert set(TOOL["parameters"]["required"]) == set(CourseDecision.model_fields)
    assert fields["next_check_seconds"]["minimum"] == 60
    assert TOOL["parameters"]["additionalProperties"] is False
