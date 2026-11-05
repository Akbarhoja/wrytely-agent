import pytest
from pydantic import ValidationError

from contracts.models import DraftPlannerDecision, PlannerDecision


@pytest.mark.parametrize("decision_type", [PlannerDecision, DraftPlannerDecision])
@pytest.mark.parametrize("field", ["reason", "step_key"])
def test_both_planner_modes_reject_blank_decision_fields(decision_type, field):
    payload = {
        "action": "work",
        "reason": "Useful analysis",
        "step_key": "analysis",
        "instruction": "Read",
    }
    payload[field] = " \t\n "
    with pytest.raises(ValidationError):
        decision_type.model_validate(payload)


@pytest.mark.parametrize("decision_type", [PlannerDecision, DraftPlannerDecision])
def test_both_modes_normalize_step_identity_before_duplicate_check(decision_type):
    decision = decision_type(
        action="work", reason=" Explain ", step_key=" compare ", instruction="Read"
    )
    assert decision.reason == "Explain"
    assert decision.step_key == "compare"


def test_draft_action_remains_unavailable_to_analysis_mode():
    payload = {
        "action": "draft",
        "reason": "Delegated",
        "step_key": "draft",
        "instruction": "Prepare",
    }
    with pytest.raises(ValidationError):
        PlannerDecision.model_validate(payload)
    assert DraftPlannerDecision.model_validate(payload).action == "draft"
