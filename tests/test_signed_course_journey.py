"""Reuse A's journey with real signed HTTP ingress; all providers stay simulated."""

import hashlib
import hmac
import json

from fastapi.testclient import TestClient
from test_canvas_sync import device as device
from test_one_course_journey import (
    test_one_course_offer_accept_checked_file_revision_and_new_deadline as existing_journey,
)
from test_source_connection_api import SessionVerifier

from app.main import create_app
from shared.config import Settings

SECRET = b"synthetic-connected-rehearsal-secret"


class SignedIngressProof:
    """Test-only ingress facade: every Store/action still uses the same real DB.

    A's unchanged scaffold calls command/receipt methods. Route those two calls
    through the public signed webhook and capture the actual handler result;
    all other attributes delegate unchanged. No authorization or result is faked.
    """

    def __init__(self, raw, patch):
        self.raw, self.patch = raw, patch
        self.commands = self.statuses = 0

    def __getattr__(self, name):
        return getattr(self.raw, name)

    def signed(self, field, event, config, method, value):
        settings = Settings(
            _env_file=None,
            whatsapp_app_secret=SECRET.decode(),
            whatsapp_verify_token="synthetic-rehearsal",
            whatsapp_business_account_id=config["business_id"],
            whatsapp_phone_number_id=config["phone_number_id"],
        )
        payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": config["business_id"],
                    "changes": [
                        {
                            "field": "messages",
                            "value": {
                                "metadata": {"phone_number_id": config["phone_number_id"]},
                                field: [event],
                            },
                        }
                    ],
                }
            ],
        }
        body = json.dumps(payload).encode()
        signature = "sha256=" + hmac.new(SECRET, body, hashlib.sha256).hexdigest()
        original = getattr(self.raw, method)
        observed = []

        def capture(*args, **kwargs):
            result = original(*args, **kwargs)
            observed.append(result)
            return result

        with self.patch.context() as patch:
            patch.setattr(self.raw, method, capture)
            with TestClient(
                create_app(settings, store=self.raw, verifier=SessionVerifier())
            ) as api:
                response = api.post(
                    "/webhooks/whatsapp", content=body, headers={"x-hub-signature-256": signature}
                )
        assert response.status_code == 200, response.text
        assert len(observed) == 1, f"Signed {field} must reach exactly one real Store call"
        return observed[0]

    def execute_whatsapp_command(self, envelope, **config):
        command = envelope.command
        verbs = {
            "accept_offer": "/accept",
            "decline_offer": "/decline",
            "send_artifact": "/file",
            "revise_artifact": "/revise",
        }
        text = verbs[command.kind]
        if command.target_id is not None:
            text += " " + str(command.target_id)
        if command.instructions:
            text += " " + command.instructions
        event = {
            "id": envelope.provider_id,
            "from": envelope.sender,
            "type": "text",
            "timestamp": str(int(envelope.event_at.timestamp())),
            "text": {"body": text},
        }
        if envelope.reply_to_provider_ref:
            event["context"] = {"id": envelope.reply_to_provider_ref}
        result = self.signed("messages", event, config, "execute_whatsapp_command", envelope)
        self.commands += 1
        return result

    def record_whatsapp_status(self, event, **config):
        status = {
            "id": event.provider_ref,
            "recipient_id": event.recipient,
            "status": event.status,
            "timestamp": str(int(event.event_at.timestamp())),
        }
        result = self.signed("statuses", status, config, "record_whatsapp_status", event)
        self.statuses += 1
        return result


def test_signed_http_course_journey_reuses_original_runtime_files_and_replanning(
    device, monkeypatch
):
    proof = SignedIngressProof(device[0], monkeypatch)
    existing_journey((proof, device[1]), command_channel=True)
    # Acceptance, explicit file and revision each replay through real ingress.
    assert proof.commands == 6
    assert proof.statuses == 2
