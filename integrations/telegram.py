"""Official Bot API, private text updates and one-attempt outbound IO only."""

import hashlib
import hmac
import logging
import re
from datetime import UTC, datetime, timedelta
from uuid import UUID

import httpx

from contracts.delivery import ArtifactDeliveryFile
from contracts.models import DeliveryResult
from contracts.telegram import TelegramText, positive_id


class _RedactBotPath(logging.Filter):
    def filter(self, record):
        record.msg = re.sub(
            r"bot[1-9][0-9]{4,15}:[A-Za-z0-9_-]{30,100}", "bot<redacted>", record.getMessage()
        )
        record.args = ()
        return True


def verify_webhook(secret, supplied):
    return bool(
        isinstance(secret, str)
        and re.fullmatch(r"[A-Za-z0-9_-]{32,256}", secret)
        and isinstance(supplied, str)
        and len(supplied) <= 256
        and hmac.compare_digest(secret.encode(), supplied.encode())
    )


def parse_update(payload, *, now=None):
    """Called only after transport-secret authentication; no groups or edited text."""
    now = now or datetime.now(UTC)
    if not isinstance(payload, dict):
        raise ValueError("Invalid Telegram update")
    update_id = payload.get("update_id")
    if type(update_id) is not int or not 0 <= update_id < 2**63:
        raise ValueError("Invalid Telegram update")
    if set(payload) - {"update_id", "message"} or "message" not in payload:
        return None
    message = payload["message"]
    if not isinstance(message, dict):
        raise ValueError("Invalid Telegram message")
    chat, sender = message.get("chat"), message.get("from")
    if not isinstance(chat, dict) or not isinstance(sender, dict):
        raise ValueError("Invalid Telegram message")
    if chat.get("type") != "private" or sender.get("is_bot") is not False:
        return None
    chat_id = positive_id(chat.get("id"))
    if chat_id != positive_id(sender.get("id")):
        raise ValueError("Private sender mismatch")
    text, timestamp = message.get("text"), message.get("date")
    if text is None:
        return None
    if not isinstance(text, str) or not text.strip() or len(text) > 12000:
        raise ValueError("Invalid Telegram text")
    if type(timestamp) is not int or not 0 <= timestamp <= 2**32:
        raise ValueError("Invalid Telegram date")
    at = datetime.fromtimestamp(timestamp, UTC)
    if at > now + timedelta(minutes=5) or at < now - timedelta(hours=24):
        raise ValueError("Telegram update outside accepted age")
    return TelegramText(update_id, positive_id(message.get("message_id")), chat_id, text, at)


def bot_id_for_token(token):
    if not isinstance(token, str) or not re.fullmatch(
        r"[1-9][0-9]{4,15}:[A-Za-z0-9_-]{30,100}", token
    ):
        raise ValueError("Invalid Telegram credential")
    return positive_id(int(token.split(":", 1)[0]))


class TelegramAdapter:
    def __init__(self, token, client):
        self.bot_id = bot_id_for_token(token)
        self._url = "https://api.telegram.org/bot" + token
        self._client = client
        for name in ("httpx", "httpcore.http11", "httpcore.http2"):
            logger = logging.getLogger(name)
            if not any(isinstance(f, _RedactBotPath) for f in logger.filters):
                logger.addFilter(_RedactBotPath())

    def send(self, *, recipient: str, text: str, action_id: UUID):
        if not isinstance(recipient, str) or not re.fullmatch(r"[1-9][0-9]{0,15}", recipient):
            raise ValueError("Private numeric recipient required")
        chat_id = positive_id(int(recipient))
        if not isinstance(text, str) or not text.strip() or len(text) > 24000:
            raise ValueError("Invalid Telegram output")
        # Never truncate a result or split an ambiguous send into independently
        # retried fragments. Long replies/checklists are inert UTF-8 attachments.
        as_file = len(text.encode("utf-16-le")) // 2 > 4096
        try:
            if as_file:
                response = self._client.post(
                    self._url + "/sendDocument",
                    data={"chat_id": str(chat_id), "protect_content": "true"},
                    files={"document": ("wrytely-result.txt", text.encode(), "text/plain")},
                    follow_redirects=False,
                    timeout=20,
                )
            else:
                response = self._client.post(
                    self._url + "/sendMessage",
                    json={
                        "chat_id": chat_id,
                        "text": text,
                        "protect_content": True,
                        "link_preview_options": {"is_disabled": True},
                    },
                    follow_redirects=False,
                    timeout=20,
                )
            return self._receipt(response, chat_id, action_id)
        except (httpx.HTTPError, ValueError, TypeError, AttributeError):
            # Exceptions can contain the credential-bearing request URL. Never
            # expose or log them, and never resend an uncertain transmission.
            return DeliveryResult(state="unknown", internal_id=action_id)

    def send_document(self, *, recipient: str, file: ArtifactDeliveryFile, action_id: UUID):
        if not isinstance(recipient, str) or not re.fullmatch(r"[1-9][0-9]{0,15}", recipient):
            raise ValueError("Private numeric recipient required")
        chat_id = positive_id(int(recipient))
        if not isinstance(file, ArtifactDeliveryFile):
            raise ValueError("Checked artifact bytes required")
        d = file.descriptor
        if (
            not isinstance(file.content, bytes)
            or not 0 < len(file.content) <= 10485760
            or len(file.content) != d.byte_length
            or hashlib.sha256(file.content).hexdigest() != d.sha256
            or d.filename != f"wrytely-{d.artifact_id}.docx"
            or d.media_type
            != "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ):
            raise ValueError("Checked artifact descriptor mismatch")
        try:
            response = self._client.post(
                self._url + "/sendDocument",
                data={"chat_id": str(chat_id), "protect_content": "true"},
                files={"document": (d.filename, file.content, d.media_type)},
                follow_redirects=False,
                timeout=20,
            )
            return self._receipt(response, chat_id, action_id)
        except (httpx.HTTPError, ValueError, TypeError, AttributeError):
            return DeliveryResult(state="unknown", internal_id=action_id)

    def _receipt(self, response, chat_id, action_id):
        if response.status_code in (400, 401, 403, 404):
            return DeliveryResult(state="failed", internal_id=action_id)
        if response.status_code == 429:
            # Store may defer an explicit provider rejection; no adapter retry.
            body = response.json() if len(response.content) <= 200000 else None
            rejected = (
                isinstance(body, dict) and body.get("ok") is False and body.get("error_code") == 429
            )
            retry_after = body.get("parameters", {}).get("retry_after", 60) if rejected else None
            if type(retry_after) is not int or not 1 <= retry_after <= 86400:
                rejected = False
            return DeliveryResult(
                state="deferred" if rejected else "unknown",
                internal_id=action_id,
                retry_at=(datetime.now(UTC) + timedelta(seconds=max(60, retry_after))).isoformat()
                if rejected
                else None,
            )
        if response.status_code != 200 or len(response.content) > 200000:
            return DeliveryResult(state="unknown", internal_id=action_id)
        body = response.json()
        result = body.get("result") if isinstance(body, dict) else None
        if (
            body.get("ok") is not True
            or not isinstance(result, dict)
            or result.get("chat", {}).get("type") != "private"
            or positive_id(result.get("chat", {}).get("id")) != chat_id
            or positive_id(result.get("from", {}).get("id")) != self.bot_id
        ):
            return DeliveryResult(state="unknown", internal_id=action_id)
        message_id = positive_id(result.get("message_id"))
        return DeliveryResult(state="accepted", internal_id=action_id, provider_ref=str(message_id))
