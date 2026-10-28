"""WhatsApp Cloud API boundary; account linking and durable delivery live above this layer."""

import hashlib
import hmac
import re
from dataclasses import dataclass
from uuid import UUID

import httpx

from contracts.models import DeliveryResult


@dataclass(frozen=True)
class WhatsAppText:
    provider_id: str
    sender: str
    text: str


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
    the conversation window. This text-only adapter cannot send approved templates.
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
        receipt = {"internal_id": action_id}
        try:
            response = self.client.post(
                self.url,
                headers={"Authorization": f"Bearer {self.token}"},
                json={
                    "messaging_product": "whatsapp",
                    "to": recipient,
                    "type": "text",
                    "text": {"body": text, "preview_url": False},
                },
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
