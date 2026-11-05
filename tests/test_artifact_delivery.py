"""Real private checked bytes and original dispatch ledger; no provider calls."""

import hashlib
from dataclasses import replace
from uuid import uuid4

import pytest
from test_canvas_sync import device as device
from test_delivery_store import ACCOUNT, PHONE, state, status
from test_private_artifact_reads import ready

from contracts.models import DeliveryResult
from contracts.templates import ArtifactPayload
from integrations.whatsapp import WhatsAppText
from runtime.artifact_rendering import render_private_artifact_docx
from shared.canvas_reads import SourceRefreshRequired
from shared.db import LeaseLost


def prepared_file(device):
    db = device[0]
    _, artifact = ready(device)
    token = db.create_whatsapp_challenge("user_alice")["message"]
    db.ingest_whatsapp(WhatsAppText("link-file", PHONE, token))
    with db.connection() as conn:
        conn.execute("UPDATE wrytely_agent.channel_links SET last_event_at=now()")
        assert (
            conn.execute("SELECT count(*) AS n FROM wrytely_agent.whatsapp_outbound").fetchone()[
                "n"
            ]
            == 0
        )
    db.set_communication_preferences(
        "user_alice", consent=True, timezone="UTC", quiet_start=0, quiet_end=0
    )
    return db, artifact


def authorize(db, claim, **kwargs):
    return db.authorize_whatsapp_send(claim, **ACCOUNT, supports_documents=True, **kwargs)


def test_explicit_checked_file_uses_original_one_attempt_queue_and_receipts(device):
    db, artifact = prepared_file(device)
    rendered = render_private_artifact_docx(db, "user_alice", artifact["id"])
    action = db.enqueue_checked_artifact_delivery("user_alice", artifact["id"])
    assert db.enqueue_checked_artifact_delivery("user_alice", artifact["id"]) == action
    claim = db.claim_whatsapp_delivery("document-worker")
    assert claim.task_id is None and claim.offer_id is None and claim.artifact_file_id
    with pytest.raises(LeaseLost):
        db.read_artifact_delivery_file(claim)
    permitted = authorize(db, claim)
    assert permitted.state == "permitted" and permitted.recipient == PHONE
    assert permitted.text is None and isinstance(permitted.payload, ArtifactPayload)
    exported = db.read_artifact_delivery_file(claim)
    assert exported.descriptor == permitted.payload
    assert exported.content == rendered.content
    assert exported.descriptor.sha256 == hashlib.sha256(exported.content).hexdigest()
    assert exported.descriptor.byte_length == len(exported.content)
    assert exported.descriptor.check_id == rendered.check_id
    with pytest.raises(LeaseLost):
        authorize(db, claim)
    db.record_whatsapp_result(
        claim,
        DeliveryResult(internal_id=claim.action_id, state="accepted", provider_ref="wamid.one"),
    )
    assert db.record_whatsapp_status(status(), **ACCOUNT)["matched"]
    assert state(db)["state"] == "delivered"
    assert db.enqueue_checked_artifact_delivery("user_alice", artifact["id"])["id"] == action["id"]
    assert db.claim_whatsapp_delivery("restart") is None


def test_file_request_is_owned_and_forged_claim_cannot_read_bytes(device):
    db, artifact = prepared_file(device)
    db.provision("user_bob")
    with pytest.raises(LookupError):
        db.enqueue_checked_artifact_delivery("user_bob", artifact["id"])
    db.enqueue_checked_artifact_delivery("user_alice", artifact["id"])
    claim = db.claim_whatsapp_delivery("document-worker")
    authorize(db, claim)
    with pytest.raises(LeaseLost):
        db.read_artifact_delivery_file(replace(claim, artifact_file_id=uuid4()))
    with pytest.raises(LeaseLost):
        db.read_artifact_delivery_file(replace(claim, agent_id=db.agent("user_bob")["id"]))


def test_document_support_is_explicit_and_reply_templates_cannot_send_a_file(device):
    db, artifact = prepared_file(device)
    db.enqueue_checked_artifact_delivery("user_alice", artifact["id"])
    claim = db.claim_whatsapp_delivery("old-worker")
    auth = db.authorize_whatsapp_send(claim, **ACCOUNT)
    assert auth.state == "held" and auth.reason == "document_transport_required"
    with db.connection() as conn:
        conn.execute("UPDATE wrytely_agent.whatsapp_outbound SET retry_at=now()")
        conn.execute("UPDATE wrytely_agent.channel_links SET last_event_at=now()-interval '25h'")
    from test_template_policy import template

    claim = db.claim_whatsapp_delivery("document-worker")
    auth = authorize(
        db,
        claim,
        supports_templates=True,
        approved_templates=[template()],
        reply_template_key="reply_update",
    )
    assert auth.state == "held" and auth.reason == "document_conversation_required"
    assert state(db)["dispatch_at"] is None


@pytest.mark.parametrize(
    "control", ["pause", "consent", "unlink", "source", "check", "bytes", "age"]
)
def test_document_authorization_rechecks_current_controls_sources_checks_and_bytes(device, control):
    db, artifact = prepared_file(device)
    db.enqueue_checked_artifact_delivery("user_alice", artifact["id"])
    claim = db.claim_whatsapp_delivery("document-worker")
    if control == "pause":
        db.set_paused("user_alice", True)
    elif control == "consent":
        db.set_communication_preferences(
            "user_alice", consent=False, timezone="UTC", quiet_start=0, quiet_end=0
        )
    elif control == "unlink":
        db.unlink_whatsapp("user_alice")
    elif control == "source":
        from test_canvas_evidence import next_scan
        from test_typed_document_drafting import TEXT, publish

        publish(
            device, text=TEXT + "\nUpdated requirements", scan=next_scan(device, "updated-file")
        )
    else:
        with db.connection() as conn:
            if control == "age":
                conn.execute(
                    "UPDATE wrytely_agent.canvas_evidence_observations "
                    "SET observed_at=now()-interval '2 hours',received_at=now()-interval '2 hours'"
                )
            elif control == "check":
                conn.execute(
                    "UPDATE wrytely_agent.artifact_checks SET passed=false,"
                    "report=jsonb_set(report,'{passed}','false')"
                )
            else:
                row = conn.execute(
                    "SELECT content FROM wrytely_agent.artifact_delivery_files"
                ).fetchone()
                conn.execute(
                    "UPDATE wrytely_agent.artifact_delivery_files SET content=%s",
                    (b"x" + bytes(row["content"])[1:],),
                )
    auth = authorize(db, claim)
    assert auth.state in ("held", "cancelled") and state(db)["dispatch_at"] is None


def test_parallel_file_requests_reuse_one_immutable_file_and_action(device):
    from concurrent.futures import ThreadPoolExecutor

    db, artifact = prepared_file(device)
    with ThreadPoolExecutor(max_workers=2) as pool:
        actions = list(
            pool.map(
                lambda _: db.enqueue_checked_artifact_delivery("user_alice", artifact["id"]),
                range(2),
            )
        )
    assert actions[0] == actions[1]
    with db.connection() as conn:
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM wrytely_agent.artifact_delivery_files"
            ).fetchone()["n"]
            == 1
        )
        assert (
            conn.execute("SELECT count(*) AS n FROM wrytely_agent.whatsapp_outbound").fetchone()[
                "n"
            ]
            == 1
        )


@pytest.mark.parametrize("control", ["pause", "consent", "unlink"])
def test_private_file_read_rechecks_controls_after_permit_before_upload(device, control):
    db, artifact = prepared_file(device)
    db.enqueue_checked_artifact_delivery("user_alice", artifact["id"])
    claim = db.claim_whatsapp_delivery("document-worker")
    assert authorize(db, claim).state == "permitted"
    if control == "pause":
        db.set_paused("user_alice", True)
    elif control == "consent":
        db.set_communication_preferences(
            "user_alice", consent=False, timezone="UTC", quiet_start=0, quiet_end=0
        )
    else:
        db.unlink_whatsapp("user_alice")
    with pytest.raises(SourceRefreshRequired):
        db.read_artifact_delivery_file(claim)


def test_upload_or_send_crash_never_creates_another_file_send(device):
    db, artifact = prepared_file(device)
    action = db.enqueue_checked_artifact_delivery("user_alice", artifact["id"])
    claim = db.claim_whatsapp_delivery("document-worker")
    assert authorize(db, claim).state == "permitted"
    db.read_artifact_delivery_file(claim)
    with db.connection() as conn:
        conn.execute("UPDATE wrytely_agent.whatsapp_outbound SET lease_until=now()-interval '1s'")
    assert db.claim_whatsapp_delivery("restart") is None
    assert state(db)["state"] == "unknown"
    assert db.enqueue_checked_artifact_delivery("user_alice", artifact["id"])["id"] == action["id"]
    with pytest.raises(LeaseLost):
        db.read_artifact_delivery_file(claim)
