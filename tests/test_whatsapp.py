import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import pytest

from integrations.whatsapp import WhatsAppAdapter, extract_texts, verify_signature


def status_payload(statuses):
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "456",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "metadata": {"phone_number_id": "123"},
                            "statuses": statuses,
                        },
                    }
                ],
            }
        ],
    }


def test_statuses_preserve_provider_identity_and_delayed_event_time():
    from integrations.whatsapp import extract_statuses

    now = datetime(2026, 10, 28, 12, tzinfo=UTC)
    rows = extract_statuses(
        status_payload(
            [
                {
                    "id": "wamid.sent",
                    "recipient_id": "15555550123",
                    "status": "delivered",
                    "timestamp": "1793188800",
                }
            ]
        ),
        phone_number_id="123",
        business_account_id="456",
        now=now,
    )
    assert len(rows) == 1
    row = rows[0]
    assert (row.provider_id, row.recipient, row.status) == (
        "wamid.sent",
        "15555550123",
        "delivered",
    )
    assert row.business_account_id == "456"
    assert row.phone_number_id == "123"
    assert row.provider_timestamp == 1793188800
    assert row.event_at == datetime(2026, 10, 28, 12, tzinfo=UTC)


@pytest.mark.parametrize("status", ["sent", "delivered", "read", "failed"])
def test_status_parser_supports_evidence_without_aggregating(status):
    from integrations.whatsapp import extract_statuses

    now = datetime(2026, 10, 28, 12, tzinfo=UTC)
    rows = extract_statuses(
        status_payload(
            [
                {
                    "id": "wamid.sent",
                    "recipient_id": "15555550123",
                    "status": status,
                    "timestamp": str(int(now.timestamp()) - 86400),
                }
            ]
        ),
        phone_number_id="123",
        business_account_id="456",
        now=now,
    )
    assert rows[0].status == status
    assert rows[0].event_at == now - timedelta(days=1)


@pytest.mark.parametrize("phone,business", [("999", "456"), ("123", "999")])
def test_status_parser_drops_other_configured_accounts(phone, business):
    from integrations.whatsapp import extract_statuses

    now = datetime(2026, 10, 28, 12, tzinfo=UTC)
    assert (
        extract_statuses(
            status_payload(
                [
                    {
                        "id": "wamid.sent",
                        "recipient_id": "15555550123",
                        "status": "delivered",
                        "timestamp": str(int(now.timestamp())),
                    }
                ]
            ),
            phone_number_id=phone,
            business_account_id=business,
            now=now,
        )
        == []
    )


@pytest.mark.parametrize(
    "bad",
    [
        None,
        [],
        "text",
        {},
        {"entry": None},
        {"object": "whatsapp_business_account", "entry": [None, {"id": "456", "changes": None}]},
        {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "456",
                    "changes": [
                        None,
                        {"field": "messages", "value": None},
                        {"field": "messages", "value": {"metadata": None}},
                        {
                            "field": "messages",
                            "value": {
                                "metadata": {"phone_number_id": "123"},
                                "statuses": {"id": "fake"},
                            },
                        },
                    ],
                }
            ],
        },
    ],
)
def test_status_parser_ignores_malformed_envelopes(bad):
    from integrations.whatsapp import extract_statuses

    assert (
        extract_statuses(
            bad,
            phone_number_id="123",
            business_account_id="456",
            now=datetime(2026, 10, 28, tzinfo=UTC),
        )
        == []
    )


@pytest.mark.parametrize(
    "patch",
    [
        {"timestamp": None},
        {"timestamp": True},
        {"timestamp": "-1"},
        {"timestamp": "x"},
        {"timestamp": "9" * 50},
        {"timestamp": "1793189101"},
        {"id": ""},
        {"id": "x" * 513},
        {"recipient_id": "other-user"},
        {"status": "queued"},
        {"status": []},
    ],
)
def test_status_parser_drops_bad_records_without_losing_valid_batch_member(patch):
    from integrations.whatsapp import extract_statuses

    valid = {
        "id": "wamid.sent",
        "recipient_id": "15555550123",
        "status": "delivered",
        "timestamp": "1793188800",
    }
    rows = extract_statuses(
        status_payload([None, {**valid, **patch}, valid]),
        phone_number_id="123",
        business_account_id="456",
        now=datetime(2026, 10, 28, 12, tzinfo=UTC),
    )
    assert [row.provider_id for row in rows] == ["wamid.sent"]


def test_status_parser_caps_small_future_skew_but_preserves_original_timestamp():
    from integrations.whatsapp import extract_statuses

    now = datetime(2026, 10, 28, 12, tzinfo=UTC)
    rows = extract_statuses(
        status_payload(
            [
                {
                    "id": "wamid.sent",
                    "recipient_id": "15555550123",
                    "status": "delivered",
                    "timestamp": "1793189100",
                }
            ]
        ),
        phone_number_id="123",
        business_account_id="456",
        now=now,
    )
    assert rows[0].event_at == now
    assert rows[0].provider_timestamp == 1793189100


def test_status_parser_requires_configured_account_and_aware_clock():
    from integrations.whatsapp import extract_statuses

    for phone, business, now in [
        ("", "456", datetime.now(UTC)),
        ("123", "", datetime.now(UTC)),
        ("123", "456", datetime(2026, 10, 28)),
    ]:
        with pytest.raises(ValueError):
            extract_statuses({}, phone_number_id=phone, business_account_id=business, now=now)


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


@pytest.mark.parametrize("parameters", [(), ("Project draft",)])
def test_template_sends_body_parameters_and_preserves_acceptance_evidence(parameters):
    requests = []

    def handle(request):
        requests.append(request)
        return httpx.Response(200, json={"messages": [{"id": "wamid.template"}]})

    action_id = uuid4()
    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        adapter = WhatsAppAdapter(
            client=client, token="test-token", phone_number_id="123", api_version="v23.0"
        )
        result = adapter.send_template(
            recipient="15555550123",
            name="result_ready",
            language="en_US",
            body_parameters=parameters,
            action_id=action_id,
        )
    assert len(requests) == 1
    payload = json.loads(requests[0].content)
    assert payload["messaging_product"] == "whatsapp"
    assert payload["to"] == "15555550123"
    assert payload["type"] == "template"
    expected = {"name": "result_ready", "language": {"code": "en_US"}}
    if parameters:
        expected["components"] = [
            {"type": "body", "parameters": [{"type": "text", "text": "Project draft"}]}
        ]
    assert payload["template"] == expected
    assert requests[0].headers["authorization"] == "Bearer test-token"
    assert result.state == "accepted"
    assert result.provider_ref == "wamid.template"
    assert result.internal_id == action_id


@pytest.mark.parametrize(
    "overrides",
    [
        {"recipient": "other-user"},
        {"name": ""},
        {"name": "Not Approved!"},
        {"language": ""},
        {"language": "en/US"},
        {"body_parameters": (" ",)},
        {"body_parameters": ("x" * 1025,)},
        {"body_parameters": (None,)},
    ],
)
def test_invalid_template_input_never_reaches_transport(overrides):
    requests = []

    def handle(request):
        requests.append(request)
        return httpx.Response(200, json={"messages": [{"id": "must-not-send"}]})

    arguments = dict(
        recipient="15555550123",
        name="result_ready",
        language="en_US",
        body_parameters=(),
        action_id=uuid4(),
    )
    arguments.update(overrides)
    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        adapter = WhatsAppAdapter(
            client=client, token="test-token", phone_number_id="123", api_version="v23.0"
        )
        with pytest.raises(ValueError):
            adapter.send_template(**arguments)
    assert requests == []


@pytest.mark.parametrize(
    "status,body,state", [(400, {}, "failed"), (500, {}, "unknown"), (200, {}, "unknown")]
)
def test_template_provider_failure_evidence_is_not_delivery(status, body, state):
    requests = []

    def handle(request):
        requests.append(request)
        return httpx.Response(status, json=body)

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        adapter = WhatsAppAdapter(
            client=client, token="test-token", phone_number_id="123", api_version="v23.0"
        )
        result = adapter.send_template(
            recipient="15555550123",
            name="result_ready",
            language="en_US",
            body_parameters=(),
            action_id=uuid4(),
        )
    assert result.state == state
    assert result.provider_ref is None
    assert len(requests) == 1


def test_template_lost_response_is_unknown_without_retry():
    requests = []

    def handle(request):
        requests.append(request)
        raise httpx.ReadTimeout("Lost template response", request=request)

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        adapter = WhatsAppAdapter(
            client=client, token="test-token", phone_number_id="123", api_version="v23.0"
        )
        result = adapter.send_template(
            recipient="15555550123",
            name="result_ready",
            language="en_US",
            body_parameters=(),
            action_id=uuid4(),
        )
    assert result.state == "unknown"
    assert len(requests) == 1
