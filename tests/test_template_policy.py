import pytest
from pydantic import ValidationError
from test_delivery_store import ACCOUNT, queued, state

from contracts.templates import ApprovedTemplate, TemplatePayload, TextPayload
from shared.config import Settings


def template(**changes):
    return ApprovedTemplate.model_validate(
        {
            "key": "reply_update",
            "name": "approved_reply_update",
            "language": "en_US",
            **ACCOUNT,
            "provider_approved": True,
            "body_parameters": [{"source": "reply_text", "max_length": 1024}],
        }
        | changes
    )


def expired(store):
    with store.connection() as conn:
        conn.execute(
            "UPDATE wrytely_agent.channel_links SET last_event_at=now()-interval '25 hours'"
        )


def authorize(store, **changes):
    return store.authorize_whatsapp_send(
        store.claim_whatsapp_delivery("worker"),
        **ACCOUNT,
        approved_templates=[template()],
        reply_template_key="reply_update",
        **changes,
    )


def test_old_worker_cannot_accidentally_authorize_a_template(store, alice):
    queued(store, alice)
    expired(store)
    auth = authorize(store)
    assert auth.state == "held"
    assert auth.reason == "approved_template_required"
    assert state(store)["dispatch_at"] is None


def test_capable_worker_gets_typed_full_reply_template_and_audit(store, alice):
    queued(store, alice)
    expired(store)
    auth = authorize(store, supports_templates=True)
    assert auth.state == "permitted"
    assert isinstance(auth.payload, TemplatePayload)
    assert auth.payload.body_parameters == ("Saved answer",)
    assert auth.text is None
    with store.connection() as conn:
        evidence = conn.execute(
            "SELECT data FROM wrytely_agent.episode_events WHERE kind='delivery_authorized'"
        ).fetchone()["data"]
    assert evidence["payload"]["kind"] == "template"
    assert evidence["payload"]["body_parameters"] == ["Saved answer"]


def test_within_window_still_uses_text(store, alice):
    queued(store, alice)
    auth = authorize(store, supports_templates=True)
    assert isinstance(auth.payload, TextPayload)
    assert auth.text == "Saved answer"


@pytest.mark.parametrize(
    "mode,reason",
    [
        ("missing", "approved_template_required"),
        ("wrong-key", "approved_template_required"),
        ("duplicate-key", "approved_template_required"),
        ("account", "template_account_mismatch"),
        ("oversized", "template_parameter_invalid"),
        ("paused", "paused"),
        ("consent", "consent_missing"),
    ],
)
def test_template_cannot_bypass_configuration_or_controls(store, alice, mode, reason):
    queued(store, alice)
    expired(store)
    templates = [template()]
    key = "reply_update"
    if mode == "missing":
        templates = []
    elif mode == "wrong-key":
        key = "not-allowed"
    elif mode == "duplicate-key":
        templates = [template(), template()]
    elif mode == "account":
        templates = [template(business_id="other-business")]
    elif mode == "oversized":
        with store.connection() as conn:
            conn.execute("UPDATE wrytely_agent.whatsapp_outbound SET content=%s", ("x" * 1025,))
    elif mode == "paused":
        store.set_paused("user_alice", True)
    elif mode == "consent":
        store.set_communication_preferences(
            "user_alice", consent=False, timezone="UTC", quiet_start=0, quiet_end=0
        )
    auth = store.authorize_whatsapp_send(
        store.claim_whatsapp_delivery("worker"),
        **ACCOUNT,
        supports_templates=True,
        approved_templates=templates,
        reply_template_key=key,
    )
    assert auth.state == "held"
    assert auth.reason == reason
    assert state(store)["dispatch_at"] is None


@pytest.mark.parametrize(
    "change",
    [
        {"provider_approved": False},
        {"provider_approved": 1},
        {"provider_approved": "true"},
        {"name": "Bad Name"},
        {"language": "???"},
        {"body_parameters": []},
        {"body_parameters": [{"source": "literal", "literal": "Notification only"}]},
        {"body_parameters": [{"source": "reply_text", "max_length": 1025}]},
    ],
)
def test_unapproved_or_invalid_template_configuration_is_rejected(change):
    with pytest.raises(ValidationError):
        template(**change)


def test_no_templates_are_enabled_by_default(monkeypatch):
    monkeypatch.delenv("AGENT_WHATSAPP_APPROVED_TEMPLATES", raising=False)
    monkeypatch.delenv("AGENT_WHATSAPP_REPLY_TEMPLATE_KEY", raising=False)
    config = Settings()
    assert config.whatsapp_approved_templates == []
    assert config.whatsapp_reply_template_key is None
