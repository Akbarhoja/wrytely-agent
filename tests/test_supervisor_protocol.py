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
