"""Synthetic authenticated envelopes; real Store atomicity, not live signature proof."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError
from test_artifact_delivery import prepared_file
from test_canvas_sync import device as device
from test_course_offer_delivery import prepared, queue
from test_delivery_store import ACCOUNT, PHONE

from contracts.models import DeliveryResult
from contracts.whatsapp_commands import WhatsAppCommandEnvelope
from integrations.whatsapp import WhatsAppText
from shared.db import QueueFull, Store
from shared.whatsapp_commands import WhatsAppCommandRejected


def envelope(target, *, kind="accept_offer", provider_id="command-one", **changes):
    data = {
        "provider_id": provider_id,
        "sender": PHONE,
        "event_at": datetime.now(UTC),
        **ACCOUNT,
        "command": {"kind": kind, "target_id": str(target) if target else None},
        **changes,
    }
    if kind == "revise_artifact":
        data["command"]["instructions"] = "Use a clearer title."
    return WhatsAppCommandEnvelope.model_validate(data)


def execute(db, message):
    return db.execute_whatsapp_command(message, **ACCOUNT)


def counts(db):
    with db.connection() as conn:
        return {
            table: conn.execute(f"SELECT count(*) AS n FROM wrytely_agent.{table}").fetchone()["n"]
            for table in ("messages", "tasks", "responsibilities", "whatsapp_inbound")
        }


def test_acceptance_is_atomic_replayed_and_never_creates_a_generic_chat_task(device):
    db, monitor, offer = prepared(device)
    message = envelope(offer["id"])
    before = counts(db)
    first = execute(db, message)
    assert first["state"] == "applied" and first["result"]["state"] == "accepted"
    assert first["replayed"] is False
    restarted = Store(db._url, canvas_origins=tuple(db._canvas_origins))
    assert execute(restarted, message) == {**first, "replayed": True}
    after = counts(db)
    assert after["messages"] == before["messages"]
    assert after["tasks"] == before["tasks"] + 1
    assert after["responsibilities"] == before["responsibilities"] + 1
    assert after["whatsapp_inbound"] == before["whatsapp_inbound"] + 1
    with db.connection() as conn:
        row = conn.execute(
            "SELECT * FROM wrytely_agent.whatsapp_inbound WHERE provider_id=%s",
            (message.provider_id,),
        ).fetchone()
    assert row["task_id"] is None and row["command_result"]["state"] == "applied"
    assert db.ingest_whatsapp(WhatsAppText(message.provider_id, PHONE, "ACCEPT")) == "duplicate"
    assert (
        db.course_supervision_status("user_alice", monitor["id"])["offers"][0]["state"]
        == "accepted"
    )


def test_decline_is_explicit_durable_and_creates_no_work(device):
    db, monitor, offer = prepared(device)
    before = counts(db)
    result = execute(db, envelope(offer["id"], kind="decline_offer"))
    assert result["result"]["state"] == "declined"
    assert counts(db)["tasks"] == before["tasks"]
    assert counts(db)["responsibilities"] == before["responsibilities"]
    assert (
        db.course_supervision_status("user_alice", monitor["id"])["offers"][0]["state"]
        == "declined"
    )


def test_unexpected_failure_rolls_back_receipt_acceptance_and_created_work(device, monkeypatch):
    db, monitor, offer = prepared(device)
    original = db.create_canvas_draft_responsibility
    before = counts(db)
    message = envelope(offer["id"])

    def crash(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError("synthetic crash after task creation")

    monkeypatch.setattr(db, "create_canvas_draft_responsibility", crash)
    with pytest.raises(RuntimeError):
        execute(db, message)
    assert counts(db) == before
    assert db._transaction_connection.get() is None
    assert (
        db.course_supervision_status("user_alice", monitor["id"])["offers"][0]["state"] == "pending"
    )
    monkeypatch.setattr(db, "create_canvas_draft_responsibility", original)
    assert execute(db, message)["state"] == "applied"
    assert counts(db)["responsibilities"] == before["responsibilities"] + 1


def test_business_rejection_rolls_back_partial_action_but_retains_receipt(device, monkeypatch):
    db, monitor, offer = prepared(device)
    original = db.create_canvas_draft_responsibility
    message = envelope(offer["id"])
    before = counts(db)

    def full(*args, **kwargs):
        original(*args, **kwargs)
        raise QueueFull()

    monkeypatch.setattr(db, "create_canvas_draft_responsibility", full)
    rejected = execute(db, message)
    assert rejected["state"] == "rejected" and rejected["reason"] == "command_unavailable"
    assert counts(db)["tasks"] == before["tasks"]
    assert counts(db)["responsibilities"] == before["responsibilities"]
    assert (
        db.course_supervision_status("user_alice", monitor["id"])["offers"][0]["state"] == "pending"
    )
    monkeypatch.setattr(db, "create_canvas_draft_responsibility", original)
    assert execute(db, message) == {**rejected, "replayed": True}
    assert (
        execute(db, envelope(offer["id"], provider_id="new-explicit-decision"))["state"]
        == "applied"
    )


def test_concurrent_provider_replay_commits_one_receipt_and_responsibility(device):
    db, _, offer = prepared(device)
    message = envelope(offer["id"])
    before = counts(db)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: execute(db, message), range(2)))
    assert sorted(r["replayed"] for r in results) == [False, True]
    assert results[0]["result"] == results[1]["result"]
    assert counts(db)["responsibilities"] == before["responsibilities"] + 1
    assert counts(db)["whatsapp_inbound"] == before["whatsapp_inbound"] + 1


def test_transaction_context_is_thread_and_store_local_and_rolls_back_nested_calls(store, alice):
    other = Store(store._url)
    before = counts(store)
    with pytest.raises(RuntimeError):
        with store._atomic_connection() as outer:
            with store.connection() as nested:
                assert nested is outer
            with other.connection() as separate:
                assert separate is not outer
            with ThreadPoolExecutor(max_workers=1) as pool:
                assert list(pool.map(lambda _: store._transaction_connection.get(), [None])) == [
                    None
                ]
            store.enqueue("user_alice", "Rolled back test", "atomic-rollback")
            raise RuntimeError("rollback")
    assert store._transaction_connection.get() is None and counts(store) == before
    # A later ordinary call still commits; no leaked closed connection/context.
    store.enqueue("user_alice", "Ordinary committed call", "outside-atomic")
    assert counts(store)["tasks"] == before["tasks"] + 1


def test_previously_generic_event_cannot_be_reinterpreted_as_a_command(device):
    db, _, offer = prepared(device)
    before = counts(db)
    with pytest.raises(WhatsAppCommandRejected, match="command_replay_conflict"):
        execute(db, envelope(offer["id"], provider_id="message-one"))
    assert counts(db) == before


@pytest.mark.parametrize("mode", ["paused", "source", "foreign", "expired_offer"])
def test_commands_reject_current_control_and_source_failures(device, mode):
    db, _, offer = prepared(device)
    message = envelope(offer["id"])
    if mode == "paused":
        db.set_paused("user_alice", True)
    elif mode == "source":
        db.rotate_or_revoke("user_alice", device[1]["connection_id"])
    elif mode == "foreign":
        db.provision("user_bob")
        code = db.create_whatsapp_challenge("user_bob")["message"]
        other = "15555550124"
        db.ingest_whatsapp(WhatsAppText("link-bob-command", other, code))
        message = envelope(offer["id"], sender=other)
    else:
        with db.connection() as conn:
            conn.execute(
                "UPDATE wrytely_agent.course_offers SET created_at=now()-interval '25 hours'"
            )
    before = counts(db)
    result = execute(db, message)
    assert result["state"] == "rejected"
    assert counts(db)["tasks"] == before["tasks"]
    assert counts(db)["responsibilities"] == before["responsibilities"]


@pytest.mark.parametrize(
    "mode", ["old", "future", "pre_link", "account", "replay_changed", "relinked"]
)
def test_stale_account_link_or_changed_replay_envelopes_reject(device, mode):
    db, _, offer = prepared(device)
    message = envelope(offer["id"])
    if mode == "old":
        message = envelope(offer["id"], event_at=datetime.now(UTC) - timedelta(days=2))
    elif mode == "future":
        message = envelope(offer["id"], event_at=datetime.now(UTC) + timedelta(minutes=6))
    elif mode == "pre_link":
        message = envelope(offer["id"], event_at=datetime.now(UTC) - timedelta(hours=1))
    elif mode == "account":
        message = envelope(offer["id"], business_id="different-business")
    else:
        execute(db, message)
        if mode == "replay_changed":
            message = message.model_copy(
                update={"command": message.command.model_copy(update={"kind": "decline_offer"})}
            )
        else:
            db.unlink_whatsapp("user_alice")
            code = db.create_whatsapp_challenge("user_alice")["message"]
            db.ingest_whatsapp(WhatsAppText("new-link-command", PHONE, code))
    before = counts(db)
    with pytest.raises(WhatsAppCommandRejected):
        execute(db, message)
    assert counts(db) == before


def test_unknown_sender_is_ignored_without_retaining_instructions(device):
    db = device[0]
    message = envelope(uuid4(), kind="revise_artifact")
    before = counts(db)
    assert execute(db, message) == {"state": "ignored"}
    assert counts(db) == before


@pytest.mark.parametrize(
    "mode", ["valid", "wrong_ref", "wrong_target", "wrong_account", "wrong_link"]
)
def test_offer_reply_requires_original_exact_account_recipient_link_context(device, mode):
    db, monitor, offer = prepared(device)
    queue(db, monitor, offer)
    claim = db.claim_whatsapp_delivery("command-test")
    assert db.authorize_whatsapp_send(claim, **ACCOUNT).state == "permitted"
    db.record_whatsapp_result(
        claim,
        DeliveryResult(internal_id=claim.action_id, state="accepted", provider_ref="wamid.offer"),
    )
    target = uuid4() if mode == "wrong_target" else None
    if mode in ("wrong_account", "wrong_link"):
        with db.connection() as conn:
            conn.execute(
                "UPDATE wrytely_agent.whatsapp_outbound SET "
                + ("business_id=%s" if mode == "wrong_account" else "link_generation=%s"),
                ("other-account" if mode == "wrong_account" else uuid4(),),
            )
    message = envelope(
        target, reply_to_provider_ref="missing" if mode == "wrong_ref" else "wamid.offer"
    )
    result = execute(db, message)
    assert result["state"] == ("applied" if mode == "valid" else "rejected")
    assert db.course_supervision_status("user_alice", monitor["id"])["offers"][0]["state"] == (
        "accepted" if mode == "valid" else "pending"
    )


@pytest.mark.parametrize("kind", ["send_artifact", "revise_artifact"])
def test_explicit_file_and_revision_commands_reuse_existing_checked_pipelines(device, kind):
    db, artifact = prepared_file(device)
    before = counts(db)
    message = envelope(artifact["id"], kind=kind)
    first = execute(db, message)
    assert first["state"] == "applied"
    assert execute(db, message) == {**first, "replayed": True}
    assert counts(db)["messages"] == before["messages"]
    if kind == "send_artifact":
        with db.connection() as conn:
            rows = conn.execute("SELECT * FROM wrytely_agent.whatsapp_outbound").fetchall()
        assert len(rows) == 1 and str(rows[0]["id"]) == first["result"]["id"]
        assert rows[0]["state"] == "queued" and rows[0]["dispatch_at"] is None
        assert counts(db)["tasks"] == before["tasks"]
    else:
        assert first["result"]["parent_artifact_id"] == str(artifact["id"])
        assert counts(db)["tasks"] == before["tasks"] + 1


def test_document_reply_resolves_only_current_owned_artifact(device):
    db, artifact = prepared_file(device)
    db.enqueue_checked_artifact_delivery("user_alice", artifact["id"])
    claim = db.claim_whatsapp_delivery("command-test")
    assert (
        db.authorize_whatsapp_send(claim, **ACCOUNT, supports_documents=True).state == "permitted"
    )
    db.record_whatsapp_result(
        claim,
        DeliveryResult(internal_id=claim.action_id, state="accepted", provider_ref="wamid.file"),
    )
    message = envelope(None, kind="revise_artifact", reply_to_provider_ref="wamid.file")
    result = execute(db, message)
    assert result["state"] == "applied" and result["target_id"] == str(artifact["id"])


@pytest.mark.parametrize(
    "invalid", ["owner", "missing_target", "missing_feedback", "extra_feedback", "unsupported"]
)
def test_command_schema_rejects_untrusted_owner_and_ambiguous_actions(invalid):
    data = envelope(uuid4()).model_dump(mode="json")
    if invalid == "owner":
        data["user_id"] = "user_bob"
    elif invalid == "missing_target":
        data["command"]["target_id"] = None
    elif invalid == "missing_feedback":
        data["command"]["kind"] = "revise_artifact"
    elif invalid == "extra_feedback":
        data["command"]["instructions"] = "Also send all my files"
    else:
        data["command"]["kind"] = "submit_assignment"
    with pytest.raises(ValidationError):
        WhatsAppCommandEnvelope.model_validate(data)
