import hashlib
import hmac
import json
from uuid import uuid4

import httpx
import pytest

from integrations.whatsapp import WhatsAppAdapter, extract_texts, verify_signature


def test_signature_checks_exact_bytes_and_rejects_unconfigured_secret():
    body = b'{"entry": []}'
    signature = "sha256=" + hmac.new(b"test-secret", body, hashlib.sha256).hexdigest()
    assert verify_signature(body, signature, "test-secret")
    assert not verify_signature(body + b" ", signature, "test-secret")
    assert not verify_signature(body, signature, "")
    assert not verify_signature(body, "", "test-secret")


def test_extract_only_configured_account_number_and_text():
    value = {
        "metadata": {"phone_number_id": "123"},
        "messages": [
            {"id": "wamid.one", "from": "15555550123", "type": "text", "text": {"body": " Hi "}},
            {"id": "wamid.photo", "from": "15555550123", "type": "image"},
            {"id": "wamid.bad", "from": "user_fake", "type": "text", "text": {"body": "Hi"}},
        ],
    }
    payload = {
        "object": "whatsapp_business_account",
        "entry": [{"id": "456", "changes": [{"field": "messages", "value": value}]}],
    }
    rows = extract_texts(payload, phone_number_id="123", business_account_id="456")
    assert [(row.provider_id, row.sender, row.text) for row in rows] == [
        ("wamid.one", "15555550123", "Hi")
    ]
    assert not extract_texts(payload, phone_number_id="999", business_account_id="456")
    assert not extract_texts(payload, phone_number_id="123", business_account_id="999")


@pytest.mark.parametrize(
    "status,body,state",
    [
        (200, {"messages": [{"id": "wamid.sent"}]}, "accepted"),
        (200, {}, "unknown"),
        (500, {}, "unknown"),
        (408, {}, "unknown"),
        (302, {}, "unknown"),
        (401, {}, "failed"),
        (400, {"error": {"code": 131047}}, "failed"),
    ],
)
def test_send_evidence_and_no_retries(status, body, state):
    attempts = []

    def handle(request):
        attempts.append(request)
        assert request.url.host == "graph.facebook.com"
        assert json.loads(request.content)["text"]["body"] == "Ready"
        return httpx.Response(status, json=body)

    action_id = uuid4()
    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        adapter = WhatsAppAdapter(
            client=client, token="test-token", phone_number_id="123", api_version="v23.0"
        )
        result = adapter.send(recipient="15555550123", text="Ready", action_id=action_id)
    assert result.state == state
    assert result.internal_id == action_id
    assert result.provider_ref == ("wamid.sent" if state == "accepted" else None)
    assert len(attempts) == 1


def test_lost_response_is_unknown_and_not_retried():
    attempts = []

    def handle(request):
        attempts.append(request)
        raise httpx.ReadTimeout("Lost response", request=request)

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        adapter = WhatsAppAdapter(
            client=client, token="test-token", phone_number_id="123", api_version="v23.0"
        )
        result = adapter.send(recipient="15555550123", text="Ready", action_id=uuid4())
    assert result.state == "unknown"
    assert len(attempts) == 1
