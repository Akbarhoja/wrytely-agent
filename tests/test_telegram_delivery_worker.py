"""Document-capable M worker composition against A's original Store fences."""

from dataclasses import replace

import pytest
from test_canvas_sync import device as device
from test_telegram_academic_delivery import file_claim
from test_telegram_store import BOT
from test_telegram_worker import Adapter

from app.telegram_worker import run_once
from contracts.models import DeliveryResult


class Recovery:
    def __init__(self, db, claim):
        self.db, self.claim = db, claim

    def __getattr__(self, name):
        return getattr(self.db, name)

    def claim_telegram_delivery(self, bot):
        if self.claim is not None:
            claim, self.claim = self.claim, None
            return claim
        return self.db.claim_telegram_delivery(bot)


class Documents(Adapter):
    def __init__(self, *, timeout=False):
        self.documents = []
        self.timeout = timeout

    def send_document(self, *, recipient, file, action_id):
        self.documents.append((recipient, file, action_id))
        if self.timeout:
            raise TimeoutError("PRIVATE URL must not be logged")
        return DeliveryResult(state="accepted", internal_id=action_id, provider_ref="73")


@pytest.mark.parametrize("timeout,expected", [(False, "accepted"), (True, "unknown")])
def test_document_permit_reads_exact_file_once_and_restart_never_repeats(device, timeout, expected):
    db, artifact, claim = file_claim(device)
    adapter = Documents(timeout=timeout)
    recovery = Recovery(db, claim)
    assert run_once(recovery, adapter, BOT) == expected
    recipient, file, sent_id = adapter.documents[0]
    assert recipient == str(claim.chat_id) and sent_id == claim.action_id
    assert file.descriptor.artifact_id == str(artifact["id"])
    assert file.content.startswith(b"PK")
    # A command acknowledgment may still be sent; it cannot become another file.
    run_once(recovery, adapter, BOT)
    run_once(recovery, adapter, BOT)
    assert len(adapter.documents) == 1
    with db.connection() as conn:
        row = conn.execute(
            "SELECT state FROM wrytely_agent.telegram_outbound WHERE id=%s", (claim.action_id,)
        ).fetchone()
    assert row["state"] == expected


@pytest.mark.parametrize("change", ["descriptor", "pause_after_permit"])
def test_changed_descriptor_or_controls_cannot_reach_document_adapter(device, change):
    db, _, claim = file_claim(device)

    class Changed(Recovery):
        def authorize_telegram_dispatch(self, current, *, supports_documents):
            assert supports_documents is True
            permit = db.authorize_telegram_dispatch(current, supports_documents=True)
            if change == "pause_after_permit":
                db.set_paused("user_alice", True)
            return permit

        def read_telegram_artifact_delivery(self, current):
            file = db.read_telegram_artifact_delivery(current)
            if change == "descriptor":
                return replace(
                    file, descriptor=file.descriptor.model_copy(update={"filename": "changed.docx"})
                )
            return file

    adapter = Documents()
    assert run_once(Changed(db, claim), adapter, BOT) == "unknown"
    assert adapter.documents == [] and adapter.calls == 0
