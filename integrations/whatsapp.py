"""WhatsApp Cloud API boundary; account linking and durable delivery live above this layer."""

import hashlib
import hmac
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

import httpx

from contracts.models import DeliveryResult


@dataclass(frozen=True)
class WhatsAppText:
    provider_id: str
    sender: str
    text: str


@dataclass(frozen=True)
class WhatsAppStatus:
    """Transport evidence only; recipient does not identify an application account."""

    provider_id: str
    recipient: str
    status: str
    provider_timestamp: int
    event_at: datetime
    business_account_id: str
    phone_number_id: str


def extract_statuses(
    payload: object, *, phone_number_id: str, business_account_id: str, now: datetime
) -> list[WhatsAppStatus]:
    """Parse provider evidence only after exact raw-body signature authentication.

    Ignore unsupported/malformed rows without losing valid batch members. Keep
    sent, delivered, read and failed distinct; the durable store owns transitions,
    replay handling and exact action correlation. Upstream must bound body size.
    """
    if not phone_number_id or not business_account_id or now.utcoffset() is None:
        raise ValueError("Configured account, phone and timezone-aware clock are required")
    now = now.astimezone(UTC)
    if not isinstance(payload, dict) or payload.get("object") != "whatsapp_business_account":
        return []

    def objects(value):
        return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []

    result = []
    for entry in objects(payload.get("entry")):
        if entry.get("id") != business_account_id:
            continue
        for change in objects(entry.get("changes")):
            value = change.get("value")
            if change.get("field") != "messages" or not isinstance(value, dict):
                continue
            metadata = value.get("metadata")
            if not isinstance(metadata, dict) or metadata.get("phone_number_id") != phone_number_id:
                continue
            for row in objects(value.get("statuses")):
                provider_id, recipient = row.get("id"), row.get("recipient_id")
                status, timestamp = row.get("status"), row.get("timestamp")
                if (
                    not isinstance(provider_id, str)
                    or not 0 < len(provider_id) <= 512
                    or not isinstance(recipient, str)
                    or not re.fullmatch(r"[0-9]{7,15}", recipient)
                    or status not in ("sent", "delivered", "read", "failed")
                    or not isinstance(timestamp, str)
                    or not re.fullmatch(r"[0-9]{1,12}", timestamp)
                ):
                    continue
                epoch = int(timestamp)
                try:
                    event_at = datetime.fromtimestamp(epoch, UTC)
                except (OverflowError, OSError, ValueError):
                    continue
                if event_at > now + timedelta(minutes=5):
                    continue
                result.append(
                    WhatsAppStatus(
                        provider_id=provider_id,
                        recipient=recipient,
                        status=status,
                        provider_timestamp=epoch,
                        event_at=min(event_at, now),
                        business_account_id=business_account_id,
                        phone_number_id=phone_number_id,
                    )
                )
    return result


def verify_signature(body: bytes, signature: str, app_secret: str) -> bool:
    """Validate the exact raw request bytes before decoding or trusting any payload."""
    if not app_secret or not re.fullmatch(r"sha256=[0-9a-f]{64}", signature):
        return False
    expected = "sha256=" + hmac.new(app_secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def extract_texts(
    payload: dict, *, phone_number_id: str, business_account_id: str
) -> list[WhatsAppText]:
    """Extract only text for our configured business and number. No identity inference.

    The caller must authenticate raw bytes first and persist provider IDs uniquely.
    Media and delivery-status events are deliberately not converted into text jobs.
    """
    if not phone_number_id or not business_account_id:
        raise ValueError("WhatsApp account and phone number IDs are required")
    result = []
    if payload.get("object") != "whatsapp_business_account":
        return result
    for entry in payload.get("entry", []):
        if entry.get("id") != business_account_id:
            continue
        for change in entry.get("changes", []):
            value = change.get("value", {})
            if change.get("field") != "messages":
                continue
            if value.get("metadata", {}).get("phone_number_id") != phone_number_id:
                continue
            for message in value.get("messages", []):
                if message.get("type") != "text":
                    continue
                sender, provider_id = message.get("from"), message.get("id")
                text = message.get("text", {}).get("body")
                if (
                    isinstance(sender, str)
                    and re.fullmatch(r"[0-9]{7,15}", sender)
                    and isinstance(provider_id, str)
                    and 0 < len(provider_id) <= 512
                    and isinstance(text, str)
                    and 0 < len(text.strip()) <= 12000
                ):
                    result.append(WhatsAppText(provider_id, sender, text.strip()))
    return result


class WhatsAppAdapter:
    """One send attempt, never an automatic retry or a claim of recipient delivery.

    The delivery service must enforce verified ownership, consent, quiet hours and
    the conversation window. Template callers must select an approved template
    and validate its configured parameter schema before calling this transport.
    action_id identifies our ledger record, not a provider idempotency guarantee.
    The caller owns and closes the injected HTTP client; use a zero-retry transport.
    """

    def __init__(self, *, client: httpx.Client, token: str, phone_number_id: str, api_version: str):
        if not token or not re.fullmatch(r"[0-9]+", phone_number_id):
            raise ValueError("WhatsApp credentials and numeric phone number ID are required")
        if not re.fullmatch(r"v[0-9]+\.0", api_version):
            raise ValueError("Configure a supported Graph API version explicitly")
        self.client = client
        self.token = token
        self.url = f"https://graph.facebook.com/{api_version}/{phone_number_id}/messages"

    def send(self, *, recipient: str, text: str, action_id: UUID) -> DeliveryResult:
        if not re.fullmatch(r"[0-9]{7,15}", recipient) or not 0 < len(text.strip()) <= 4096:
            raise ValueError("Invalid recipient or text length")
        return self._send_payload(
            {
                "messaging_product": "whatsapp",
                "to": recipient,
                "type": "text",
                "text": {"body": text, "preview_url": False},
            },
            action_id,
        )

    def send_template(
        self,
        *,
        recipient: str,
        name: str,
        language: str,
        body_parameters: tuple[str, ...],
        action_id: UUID,
    ) -> DeliveryResult:
        """Send one configured template; this method does not establish permission.

        Supports static templates and positional body text parameters only. The
        1,024-character per-parameter ceiling is a conservative application limit.
        Approval, matching parameter count, timing and consent belong to the caller.
        """
        if (
            not isinstance(recipient, str)
            or not re.fullmatch(r"[0-9]{7,15}", recipient)
            or not isinstance(name, str)
            or not re.fullmatch(r"[a-z0-9_]{1,512}", name)
            or not isinstance(language, str)
            or not re.fullmatch(r"[a-z]{2,3}(?:_[A-Z]{2})?", language)
            or not isinstance(body_parameters, tuple)
            or any(
                not isinstance(value, str) or not value.strip() or len(value) > 1024
                for value in body_parameters
            )
        ):
            raise ValueError("Invalid template recipient, identifier or body parameters")
        template = {"name": name, "language": {"code": language}}
        if body_parameters:
            template["components"] = [
                {
                    "type": "body",
                    "parameters": [{"type": "text", "text": value} for value in body_parameters],
                }
            ]
        return self._send_payload(
            {
                "messaging_product": "whatsapp",
                "to": recipient,
                "type": "template",
                "template": template,
            },
            action_id,
        )

    def _send_payload(self, payload: dict, action_id: UUID) -> DeliveryResult:
        receipt = {"internal_id": action_id}
        try:
            response = self.client.post(
                self.url,
                headers={"Authorization": f"Bearer {self.token}"},
                json=payload,
                timeout=15,
                follow_redirects=False,
            )
        except httpx.TransportError:
            return DeliveryResult(state="unknown", **receipt)
        if 400 <= response.status_code < 500 and response.status_code != 408:
            return DeliveryResult(state="failed", **receipt)
        if response.status_code == 200:
            try:
                provider_ref = response.json()["messages"][0]["id"]
                if isinstance(provider_ref, str) and provider_ref:
                    return DeliveryResult(state="accepted", provider_ref=provider_ref, **receipt)
            except (ValueError, KeyError, IndexError, TypeError):
                pass
        # An upstream failure or malformed success may conceal an accepted send.
        return DeliveryResult(state="unknown", **receipt)
