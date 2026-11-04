"""Official Telegram parsing/IO: no groups, credential leaks or ambiguous retries."""

import json
import logging
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import pytest

from integrations.telegram import TelegramAdapter, parse_update, verify_webhook

TOKEN = "123456789:" + "synthetic_credential_" * 2
NOW = datetime.now(UTC).replace(microsecond=0)


def update(**changes):
    message = dict(
        message_id=7,
        date=int(NOW.timestamp()),
        chat={"id": 991, "type": "private"},
        **{"from": {"id": 991, "is_bot": False}},
        text="Help me plan my study time",
    )
    message.update(changes)
    return {"update_id": 9, "message": message}


def test_parser_preserves_private_text_with_numeric_identity():
    event = parse_update(update(), now=NOW)
    assert (event.update_id, event.chat_id, event.message_id) == (9, 991, 7)
    assert event.text == "Help me plan my study time" and event.event_at == NOW


@pytest.mark.parametrize("kind", ["group", "supergroup", "channel"])
def test_groups_are_never_private_student_messages(kind):
    assert parse_update(update(chat={"id": 991, "type": kind}), now=NOW) is None


@pytest.mark.parametrize("sender", [{"id": 991, "is_bot": True}, {"id": 991}])
def test_bot_or_missing_sender_authority_is_not_accepted(sender):
    assert parse_update(update(**{"from": sender}), now=NOW) is None


@pytest.mark.parametrize("kind", ["edited_message", "callback_query", "channel_post"])
def test_no_hidden_edit_or_callback_execution(kind):
    value = update()
    value[kind] = value.pop("message")
    assert parse_update(value, now=NOW) is None


@pytest.mark.parametrize(
    "change",
    [
        {"message_id": True},
        {"chat": {"id": -1, "type": "private"}},
        {"from": {"id": 992, "is_bot": False}},
        {"date": int((NOW - timedelta(hours=25)).timestamp())},
        {"date": int((NOW + timedelta(minutes=6)).timestamp())},
        {"text": " "},
        {"text": "x" * 12001},
    ],
)
def test_bad_or_old_envelopes_reject_before_storage(change):
    with pytest.raises(ValueError):
        parse_update(update(**change), now=NOW)


@pytest.mark.parametrize("supplied", [None, "wrong", "x" * 257, "é" * 32])
def test_webhook_requires_the_configured_secret(supplied):
    assert not verify_webhook("a" * 43, supplied)
    assert verify_webhook("a" * 43, "a" * 43)
    assert not verify_webhook("", "")


def response(**changes):
    result = dict(
        message_id=777, chat={"id": 991, "type": "private"}, **{"from": {"id": 123456789}}
    )
    result.update(changes)
    return {"ok": True, "result": result}


def test_one_attempt_acceptance_is_not_recipient_delivery_and_token_is_redacted(caplog):
    requests = []
    caplog.set_level(logging.INFO, logger="httpx")

    def handle(request):
        requests.append(request)
        assert request.url.host == "api.telegram.org"
        assert request.url.path.endswith("/sendMessage")
        body = json.loads(request.content)
        assert body["text"] == "<b>literal</b>" and "parse_mode" not in body
        assert body["chat_id"] == 991 and body["protect_content"]
        return httpx.Response(200, json=response())

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        result = TelegramAdapter(TOKEN, client).send(
            recipient="991", text="<b>literal</b>", action_id=uuid4()
        )
    assert result.state == "accepted" and result.provider_ref == "777" and len(requests) == 1
    assert TOKEN not in caplog.text and "bot<redacted>" in caplog.text


def test_long_utf16_text_is_a_complete_inert_file_not_silently_truncated():
    text = "😀" * 2500

    def handle(request):
        assert request.url.path.endswith("/sendDocument")
        assert text.encode() in request.content
        assert b'filename="wrytely-result.txt"' in request.content
        assert b"text/plain" in request.content
        return httpx.Response(200, json=response())

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        assert (
            TelegramAdapter(TOKEN, client).send(recipient="991", text=text, action_id=uuid4()).state
            == "accepted"
        )


@pytest.mark.parametrize(
    "status,state",
    [
        (400, "failed"),
        (401, "failed"),
        (403, "failed"),
        (429, "deferred"),
        (500, "unknown"),
        (302, "unknown"),
    ],
)
def test_provider_rejection_and_uncertainty_are_not_retried(status, state):
    requests = []

    def handle(request):
        requests.append(request)
        return httpx.Response(
            status,
            headers={"location": "https://example.com"},
            json={"ok": False, "error_code": status},
        )

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        result = TelegramAdapter(TOKEN, client).send(
            recipient="991", text="hello", action_id=uuid4()
        )
    assert result.state == state and len(requests) == 1


@pytest.mark.parametrize(
    "body",
    [
        [],
        None,
        {"ok": True, "result": {}},
        response(chat={"id": 992, "type": "private"}),
        response(message_id=True),
        response(**{"from": {"id": 456}}),
    ],
)
def test_malformed_or_wrong_recipient_acceptance_is_unknown(body):
    with httpx.Client(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json=body))
    ) as client:
        assert (
            TelegramAdapter(TOKEN, client)
            .send(recipient="991", text="hello", action_id=uuid4())
            .state
            == "unknown"
        )


def test_timeout_is_unknown_without_exception_url_or_second_request():
    requests = []

    def handle(request):
        requests.append(request)
        raise httpx.ReadTimeout("private credential-bearing failure", request=request)

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        result = TelegramAdapter(TOKEN, client).send(
            recipient="991", text="hello", action_id=uuid4()
        )
    assert result.state == "unknown" and len(requests) == 1
    assert TOKEN not in result.model_dump_json()
