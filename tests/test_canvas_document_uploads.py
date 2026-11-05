"""Synthetic private upload staging against disposable Postgres; no source IO."""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import asdict
from uuid import uuid4

import pytest
import test_canvas_evidence as evidence
import test_canvas_sync as sync
from test_canvas_document_wire import assignment_data
from test_canvas_sync import device as device

from shared.canvas_document_uploads import CanvasDocumentUploadLimited
from shared.canvas_sync import CanvasSyncConflict
from shared.db import Store
from shared.document_sections import split_document_text
from shared.source_connections import SourceCredentialRejected


def test_linked_file_requires_parent_scope_and_leaves_no_staging_when_denied(device):
    scan = evidence.prepare(device, kinds=["files"])
    body = begin_body(device, scan)
    body["resource"]["kind"] = "files"
    body["owner_object"] = {"kind": "file", "provider_id": "17"}
    body["object_fields"] = {
        "filename": "manual.txt",
        "content_type": "text/plain",
        "linked_from": ["assignment:31"],
    }
    with pytest.raises(CanvasSyncConflict, match="resource_not_selected"):
        begin(device, body)
    assert count(device, "canvas_document_uploads") == 0


def test_linked_file_staging_keeps_parent_provenance_across_restart(device):
    scan = evidence.prepare(device, kinds=["files", "assignments"])
    body = begin_body(device, scan)
    body["resource"]["kind"] = "files"
    body["owner_object"] = {"kind": "file", "provider_id": "17"}
    body["object_fields"] = {
        "filename": "starter.c",
        "content_type": "text/x-c",
        "linked_from": ["assignment:31"],
    }
    upload = begin(device, body)
    put(device, put_body(body, upload["upload_id"]))
    root = finish(device, finish_body(body, upload["upload_id"]))
    restarted = Store(device[0]._url, canvas_origins=(sync.ORIGIN,))
    assert (
        finish((restarted, device[1]), finish_body(body, upload["upload_id"]))[
            "document_version_id"
        ]
        == root["document_version_id"]
    )
    with restarted.connection() as conn:
        payload = conn.execute(
            "SELECT protocol_payload FROM wrytely_agent.canvas_document_versions WHERE id=%s",
            (root["document_version_id"],),
        ).fetchone()["protocol_payload"]
    assert payload["fields"]["object_fields"]["linked_from"] == ["assignment:31"]


def begin_body(device, scan, key="begin-doc"):
    data = assignment_data()
    return {
        "schema_version": 2,
        "operation": "begin_document",
        "connection_id": device[1]["connection_id"],
        "generation": sync.context(device)["generation"],
        "scan_id": scan["scan_id"],
        "subject": sync.SUBJECT,
        "lease_token": scan["lease_token"],
        "request_key": key,
        **{
            k: data[k]
            for k in ("resource", "owner_object", "object_fields", "metadata", "manifest")
        },
    }


def begin(device, body):
    return device[0].begin_document_upload(
        device[1]["ingestion_bearer"], body, extractor_versions=("fixture.v1",)
    )


def put_body(body, upload_id, *, key="put-doc", parts=None):
    return {
        **{
            k: v
            for k, v in body.items()
            if k not in {"resource", "owner_object", "object_fields", "metadata", "manifest"}
        },
        "operation": "put_document_parts",
        "request_key": key,
        "upload_id": upload_id,
        "parts": assignment_data()["parts"] if parts is None else parts,
    }


def put(device, body):
    return device[0].put_document_parts(device[1]["ingestion_bearer"], body)


def count(device, table):
    assert table in {
        "canvas_document_uploads",
        "canvas_document_upload_parts",
        "canvas_document_upload_receipts",
        "canvas_evidence_observations",
        "source_versions",
    }
    with device[0].connection() as conn:
        return conn.execute("SELECT count(*) AS n FROM wrytely_agent." + table).fetchone()["n"]


def test_begin_put_restart_original_cumulative_receipts_and_no_evidence(device):
    scan = evidence.prepare(device)
    body = begin_body(device, scan)
    receipt = begin(device, body)
    assert receipt["received_slots"] == [] and not receipt["replayed"]
    restart = Store(device[0]._url, canvas_origins=(sync.ORIGIN,))
    restarted = (restart, device[1])
    assert begin(restarted, body) == {**receipt, "replayed": True}
    request = put_body(body, receipt["upload_id"])
    uploaded = put(restarted, request)
    assert uploaded["received_slots"] == [0]
    assert uploaded["expires_at"] == receipt["expires_at"]
    assert put(device, request) == {**uploaded, "replayed": True}
    # The old begin receipt remains empty even after slots have arrived.
    assert begin(device, body) == {**receipt, "replayed": True}
    assert count(device, "canvas_document_upload_parts") == 1
    assert count(device, "canvas_document_upload_receipts") == 2
    assert count(device, "canvas_evidence_observations") == 0
    assert count(device, "source_versions") == 0


def test_changed_replay_and_changed_existing_slot_are_atomic_conflicts(device):
    body = begin_body(device, evidence.prepare(device))
    receipt = begin(device, body)
    changed = deepcopy(body)
    changed["metadata"]["title"] = "Changed"
    with pytest.raises(CanvasSyncConflict, match="document_conflict"):
        begin(device, changed)
    request = put_body(body, receipt["upload_id"])
    put(device, request)
    for key in (request["request_key"], "other-key"):
        changed = deepcopy(request)
        changed["request_key"] = key
        changed["parts"][0]["text"] = "Changed"
        with pytest.raises(CanvasSyncConflict, match="document_conflict"):
            put(device, changed)
    repeated = deepcopy(request)
    repeated["request_key"] = "same-text-new-key"
    assert put(device, repeated)["received_slots"] == [0]
    assert count(device, "canvas_document_upload_parts") == 1


@pytest.mark.parametrize(
    "container,key,value",
    [
        (None, "schema_version", True),
        (None, "schema_version", "2"),
        (None, "operation", "finish_document"),
        (None, "batch_type", "canvas_documents"),
        (None, "agent_id", "untrusted"),
        (None, "generation", True),
        (None, "scan_id", "bad"),
        (None, "request_key", "bad key"),
        ("metadata", "total_characters", True),
        ("metadata", "extractor_version", "unconfigured"),
        ("resource", "course_id", "102"),
        ("metadata", "total_characters", 7),
    ],
)
def test_invalid_begin_requests_do_not_create_staging(device, container, key, value):
    body = begin_body(device, evidence.prepare(device))
    target = body if container is None else body[container]
    target[key] = value
    with pytest.raises((ValueError, CanvasSyncConflict)):
        begin(device, body)
    assert count(device, "canvas_document_uploads") == 0


@pytest.mark.parametrize(
    "parts",
    [
        [],
        [{"slot": True, "text": "x"}],
        [{"slot": 0, "text": "x"}, {"slot": 0, "text": "x"}],
        [{"slot": 1, "text": "x"}],
        [{"slot": 0, "text": "Changed"}],
        [{"slot": 0, "text": "\ud800"}],
        [{"slot": 0, "text": "x", "url": "hidden"}],
        [{"slot": 0, "text": "x" * 24001}],
    ],
)
def test_invalid_parts_leave_no_parts_or_receipt(device, parts):
    body = begin_body(device, evidence.prepare(device))
    upload = begin(device, body)
    with pytest.raises(ValueError):
        put(device, put_body(body, upload["upload_id"], parts=parts))
    assert count(device, "canvas_document_upload_parts") == 0
    assert count(device, "canvas_document_upload_receipts") == 1


@pytest.mark.parametrize(
    "control",
    [
        "revoke",
        "scope",
        "credential_expiry",
        "lease",
        "upload_expiry",
        "subject",
        "generation",
        "scan",
        "connection",
    ],
)
def test_current_controls_fence_new_writes_and_replays(device, control):
    body = begin_body(device, evidence.prepare(device))
    upload = begin(device, body)
    request = put_body(body, upload["upload_id"])
    put(device, request)
    if control == "revoke":
        device[0].rotate_or_revoke("user_alice", body["connection_id"])
    elif control == "scope":
        sync.set_scope(device, [], kinds=[])
    elif control in {"subject", "generation", "scan", "connection"}:
        field = {
            "subject": "subject",
            "generation": "generation",
            "scan": "scan_id",
            "connection": "connection_id",
        }[control]
        request[field] = (
            "other"
            if control == "subject"
            else request["generation"] + 1
            if control == "generation"
            else str(uuid4())
        )
    else:
        with device[0].connection() as conn:
            if control == "credential_expiry":
                conn.execute(
                    "UPDATE wrytely_agent.source_connections SET "
                    "credential_expires_at=clock_timestamp()-interval '1 second' WHERE id=%s",
                    (body["connection_id"],),
                )
            if control == "lease":
                conn.execute(
                    "UPDATE wrytely_agent.canvas_scans SET "
                    "lease_expires_at=clock_timestamp()-interval '1 second' WHERE id=%s",
                    (body["scan_id"],),
                )
            if control == "upload_expiry":
                conn.execute(
                    "UPDATE wrytely_agent.canvas_document_uploads SET "
                    "expires_at=clock_timestamp()-interval '1 second' WHERE id=%s",
                    (upload["upload_id"],),
                )
    for key in (request["request_key"], "new-put"):
        request["request_key"] = key
        with pytest.raises((CanvasSyncConflict, SourceCredentialRejected)):
            put(device, request)
    assert count(device, "canvas_document_upload_parts") == 1
    assert count(device, "canvas_document_upload_receipts") == 2


def test_lease_rotation_replays_exact_body_with_current_authority_only(device):
    scan = evidence.prepare(device)
    body = begin_body(device, scan)
    upload = begin(device, body)
    with device[0].connection() as conn:
        conn.execute(
            "UPDATE wrytely_agent.canvas_scans SET "
            "lease_expires_at=clock_timestamp()-interval '1 second' WHERE id=%s",
            (scan["scan_id"],),
        )
    new = device[0].resume_sync(
        device[1]["ingestion_bearer"], scan["scan_id"], body["generation"], "new-lease"
    )
    with pytest.raises(CanvasSyncConflict, match="lease_replaced"):
        begin(device, body)
    body["lease_token"] = new["lease_token"]
    assert begin(device, body) == {**upload, "replayed": True}
    assert put(device, put_body(body, upload["upload_id"]))["received_slots"] == [0]


def test_parallel_begins_enforce_four_upload_connection_quota(device):
    body = begin_body(device, evidence.prepare(device))

    def attempt(index):
        try:
            return begin(device, body | {"request_key": f"parallel-{index}"})
        except CanvasDocumentUploadLimited:
            return None

    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(attempt, range(6)))
    assert sum(r is not None for r in results) == 4
    assert count(device, "canvas_document_uploads") == 4
    assert count(device, "canvas_document_upload_receipts") == 4


def test_rollback_if_authority_expires_before_receipt_commit(device, monkeypatch):
    body = begin_body(device, evidence.prepare(device))
    upload = begin(device, body)
    original = device[0]._save_document_receipt

    def late(conn, *args, **kwargs):
        conn.execute(
            "UPDATE wrytely_agent.canvas_scans SET "
            "lease_expires_at=clock_timestamp()-interval '1 second' WHERE id=%s",
            (body["scan_id"],),
        )
        return original(conn, *args, **kwargs)

    monkeypatch.setattr(device[0], "_save_document_receipt", late)
    with pytest.raises(CanvasSyncConflict, match="lease_expired"):
        put(device, put_body(body, upload["upload_id"]))
    assert count(device, "canvas_document_upload_parts") == 0
    assert count(device, "canvas_document_upload_receipts") == 1


def test_multi_slot_out_of_order_batches_preserve_original_receipt(device):
    body = begin_body(device, evidence.prepare(device))
    document = split_document_text("abcdef", section_characters=2)
    body["manifest"] = []
    parts = []
    for section in document.sections:
        row = asdict(section)
        parts.append({"slot": row["slot"], "text": row.pop("text")})
        body["manifest"].append(row)
    upload = begin(device, body)
    first = put_body(body, upload["upload_id"], parts=[parts[2]])
    receipt = put(device, first)
    assert receipt["received_slots"] == [2]
    assert put(device, put_body(body, upload["upload_id"], key="rest", parts=parts[:2]))[
        "received_slots"
    ] == [0, 1, 2]
    assert put(device, first) == {**receipt, "replayed": True}


def test_upload_is_bound_to_own_scan_and_opaque_upload_id(device):
    scan = evidence.prepare(device)
    body = begin_body(device, scan)
    upload = begin(device, body)
    request = put_body(body, str(uuid4()))
    with pytest.raises(LookupError, match="Not found"):
        put(device, request)
    request["upload_id"] = upload["upload_id"]
    # A new authorized scan is still not authority over an old scan's upload.
    with device[0].connection() as conn:
        conn.execute(
            "UPDATE wrytely_agent.canvas_scans SET state='aborted' WHERE id=%s", (scan["scan_id"],)
        )
    other = evidence.next_scan(device, "other-scan")
    request["scan_id"] = other["scan_id"]
    request["lease_token"] = other["lease_token"]
    with pytest.raises(LookupError, match="Not found"):
        put(device, request)


def test_other_account_credential_cannot_write_or_replay_private_upload(device):
    body = begin_body(device, evidence.prepare(device))
    upload = begin(device, body)
    request = put_body(body, upload["upload_id"])
    put(device, request)
    db = device[0]
    db.provision("user_bob")
    code = db.create_pairing("user_bob", sync.ORIGIN)["code"]
    bob = db.redeem_pairing(code, "bob-device")
    db.bind_canvas_identity(bob["ingestion_bearer"], sync.ORIGIN, "bob-canvas")
    with pytest.raises(SourceCredentialRejected):
        db.put_document_parts(bob["ingestion_bearer"], request)
    with pytest.raises(SourceCredentialRejected):
        db.begin_document_upload(bob["ingestion_bearer"], body, extractor_versions=("fixture.v1",))
    assert count(device, "canvas_document_upload_parts") == 1


def test_quota_counts_expired_uncollected_text_without_deleting_it(device):
    body = begin_body(device, evidence.prepare(device))
    doc = split_document_text("📚" * 200_000)
    body["manifest"], parts = [], []
    for section in doc.sections:
        row = asdict(section)
        parts.append({"slot": row["slot"], "text": row.pop("text")})
        body["manifest"].append(row)
    body["metadata"]["total_characters"] = 200_000
    # Each legitimate root has800000 UTF8 bytes; expired staged bodies remain
    # counted until separately reviewed cleanup exists. Ten fit under8MiB.
    for index in range(10):
        request = body | {"request_key": f"large-{index}"}
        upload = begin(device, request)
        put(device, put_body(request, upload["upload_id"], key=f"large-put-{index}", parts=parts))
        with device[0].connection() as conn:
            conn.execute(
                "UPDATE wrytely_agent.canvas_document_uploads SET "
                "expires_at=clock_timestamp()-interval '1 second' WHERE id=%s",
                (upload["upload_id"],),
            )
    request = body | {"request_key": "too-much"}
    upload = begin(device, request)
    with pytest.raises(CanvasDocumentUploadLimited, match="document_bytes_limit"):
        put(device, put_body(request, upload["upload_id"], key="too-much-put", parts=parts))
    with device[0].connection() as conn:
        assert (
            conn.execute(
                "SELECT sum(octet_length(text)) AS n FROM "
                "wrytely_agent.canvas_document_upload_parts"
            ).fetchone()["n"]
            == 8_000_000
        )
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM wrytely_agent.canvas_document_upload_parts "
                "WHERE upload_id=%s",
                (upload["upload_id"],),
            ).fetchone()["n"]
            == 0
        )


def test_request_utf8_size_cap_applies_before_begin_transaction(device):
    body = begin_body(device, evidence.prepare(device))
    body["object_fields"]["rubric"] = [
        {"id": "r1", "description": "📚" * 300_000, "points": "1", "ratings": []}
    ]
    with pytest.raises(ValueError, match="size limit"):
        begin(device, body)
    assert count(device, "canvas_document_uploads") == 0


def test_begin_expiry_is_bounded_by_scan_and_does_not_extend_on_put(device):
    from datetime import UTC, datetime, timedelta

    body = begin_body(device, evidence.prepare(device))
    with device[0].connection() as conn:
        conn.execute(
            "UPDATE wrytely_agent.canvas_scans SET expires_at=clock_timestamp()+interval "
            "'10 minutes' WHERE id=%s",
            (body["scan_id"],),
        )
    upload = begin(device, body)
    expiry = datetime.fromisoformat(upload["expires_at"])
    assert timedelta(minutes=9) < expiry - datetime.now(UTC) <= timedelta(minutes=10)
    assert put(device, put_body(body, upload["upload_id"]))["expires_at"] == upload["expires_at"]


@pytest.mark.parametrize("change", ["scan_expiry", "resource_closed", "begin_final_expiry"])
def test_expired_scan_or_closed_resource_never_returns_old_begin_receipt(
    device, change, monkeypatch
):
    body = begin_body(device, evidence.prepare(device))
    if change == "begin_final_expiry":
        original = device[0]._save_document_receipt

        def late(conn, *args, **kwargs):
            conn.execute(
                "UPDATE wrytely_agent.canvas_scans SET "
                "lease_expires_at=clock_timestamp()-interval '1 second' WHERE id=%s",
                (body["scan_id"],),
            )
            return original(conn, *args, **kwargs)

        monkeypatch.setattr(device[0], "_save_document_receipt", late)
    else:
        begin(device, body)
        with device[0].connection() as conn:
            if change == "scan_expiry":
                conn.execute(
                    "UPDATE wrytely_agent.canvas_scans SET "
                    "expires_at=clock_timestamp()-interval '1 second' WHERE id=%s",
                    (body["scan_id"],),
                )
            else:
                conn.execute(
                    "UPDATE wrytely_agent.canvas_resources SET coverage='partial' WHERE "
                    "scan_id=%s AND resource_key='101/assignments'",
                    (body["scan_id"],),
                )
    with pytest.raises(CanvasSyncConflict):
        begin(device, body)
    if change == "begin_final_expiry":
        assert count(device, "canvas_document_uploads") == 0
        assert count(device, "canvas_document_upload_receipts") == 0


def test_parts_do_not_accept_publication_discriminator_or_unrecognized_fields(device):
    body = begin_body(device, evidence.prepare(device))
    upload = begin(device, body)
    request = put_body(body, upload["upload_id"])
    for field, value in (
        ("batch_type", "canvas_documents"),
        ("content", "extra"),
        ("schema_version", True),
    ):
        with pytest.raises(ValueError):
            put(device, request | {field: value})
    assert count(device, "canvas_document_upload_parts") == 0


def finish_body(body, upload_id, key="finish-doc"):
    value = put_body(body, upload_id, key=key)
    del value["parts"]
    value["operation"] = "finish_document"
    return value


def finish(device, request):
    return device[0].finish_document_upload(
        device[1]["ingestion_bearer"], request, extractor_versions=("fixture.v1",)
    )


def test_finish_reuses_sections_and_exposes_no_evidence_until_publication(device):
    body = begin_body(device, evidence.prepare(device))
    upload = begin(device, body)
    put(device, put_body(body, upload["upload_id"]))
    request = finish_body(body, upload["upload_id"])
    receipt = finish(device, request)
    assert receipt["ready"] is True and "received_slots" not in receipt
    assert receipt["expires_at"] == upload["expires_at"]
    assert finish(device, request) == {**receipt, "replayed": True}
    assert count(device, "source_versions") == count(device, "canvas_evidence_observations") == 0
    with device[0].connection() as conn:
        obj = conn.execute("SELECT * FROM wrytely_agent.canvas_evidence_objects").fetchone()
        assert obj["latest_observation_id"] is None and obj["source_id"] is None
        doc, _ = device[0]._load_canvas_document(
            conn, obj["agent_id"], obj["id"], receipt["document_version_id"]
        )
        assert "".join(s.text for s in doc.sections) == "Café\n📚"
    assert (
        device[0].list_canvas_evidence("user_alice", connection_id=body["connection_id"])["sources"]
        == []
    )


def test_missing_parts_and_expired_finish_create_no_root(device):
    body = begin_body(device, evidence.prepare(device))
    upload = begin(device, body)
    with pytest.raises(ValueError):
        finish(device, finish_body(body, upload["upload_id"]))
    put(device, put_body(body, upload["upload_id"]))
    with device[0].connection() as conn:
        conn.execute(
            "UPDATE wrytely_agent.canvas_document_uploads SET "
            "expires_at=clock_timestamp()-interval '1 second' WHERE id=%s",
            (upload["upload_id"],),
        )
    with pytest.raises(CanvasSyncConflict, match="document_expired"):
        finish(device, finish_body(body, upload["upload_id"]))
    with device[0].connection() as conn:
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM wrytely_agent.canvas_document_versions"
            ).fetchone()["n"]
            == 0
        )


def test_protocol_roots_bind_fields_and_deduplicate_same_object_reversion(device):
    body = begin_body(device, evidence.prepare(device))
    receipts = []
    for index in range(3):
        value = deepcopy(body)
        value["request_key"] = f"begin-{index}"
        if index == 1:
            value["object_fields"]["due_at"] = "2026-01-03T00:00:00Z"
        upload = begin(device, value)
        put(device, put_body(value, upload["upload_id"], key=f"put-{index}"))
        receipts.append(finish(device, finish_body(value, upload["upload_id"], f"finish-{index}")))
    assert receipts[0]["document_version_id"] == receipts[2]["document_version_id"]
    assert receipts[0]["document_version_id"] != receipts[1]["document_version_id"]
    assert (
        receipts[0]["document_digest"]
        == receipts[2]["document_digest"]
        != receipts[1]["document_digest"]
    )
    with device[0].connection() as conn:
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM wrytely_agent.canvas_document_versions"
            ).fetchone()["n"]
            == 2
        )


def test_finish_fences_lease_at_final_receipt_and_rolls_back_root(device, monkeypatch):
    body = begin_body(device, evidence.prepare(device))
    upload = begin(device, body)
    put(device, put_body(body, upload["upload_id"]))
    original = device[0]._save_document_receipt

    def late(conn, *args, **kwargs):
        conn.execute(
            "UPDATE wrytely_agent.canvas_scans SET "
            "lease_expires_at=clock_timestamp()-interval '1 second' WHERE id=%s",
            (body["scan_id"],),
        )
        return original(conn, *args, **kwargs)

    monkeypatch.setattr(device[0], "_save_document_receipt", late)
    with pytest.raises(CanvasSyncConflict, match="lease_expired"):
        finish(device, finish_body(body, upload["upload_id"]))
    with device[0].connection() as conn:
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM wrytely_agent.canvas_document_versions"
            ).fetchone()["n"]
            == 0
        )
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM wrytely_agent.canvas_evidence_objects"
            ).fetchone()["n"]
            == 0
        )


@pytest.mark.parametrize("change", ["revoke", "scope", "generation", "extra", "upload"])
def test_finish_controls_and_strict_wire_remain_enforced(device, change):
    body = begin_body(device, evidence.prepare(device))
    upload = begin(device, body)
    put(device, put_body(body, upload["upload_id"]))
    request = finish_body(body, upload["upload_id"])
    finish(device, request)
    if change == "revoke":
        device[0].rotate_or_revoke("user_alice", body["connection_id"])
    if change == "scope":
        sync.set_scope(device, [], kinds=[])
    if change == "generation":
        request["generation"] += 1
    if change == "extra":
        request["parts"] = []
    if change == "upload":
        request["upload_id"] = str(uuid4())
        request["request_key"] = "other"
    with pytest.raises((ValueError, LookupError, SourceCredentialRejected)):
        finish(device, request)


def test_finish_rejects_whole_text_nfc_change_across_individually_valid_parts(device):
    import hashlib

    body = begin_body(device, evidence.prepare(device))
    body["metadata"]["total_characters"] = 2
    texts = ["e", "\u0301"]
    body["manifest"] = []
    for index, text in enumerate(texts):
        body["manifest"].append(
            {
                "slot": index,
                "start": index,
                "end": index + 1,
                "page": None,
                "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
            }
        )
    upload = begin(device, body)
    put(
        device,
        put_body(
            body, upload["upload_id"], parts=[{"slot": i, "text": t} for i, t in enumerate(texts)]
        ),
    )
    with pytest.raises(ValueError, match="normalization"):
        finish(device, finish_body(body, upload["upload_id"]))
    with device[0].connection() as conn:
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM wrytely_agent.canvas_document_versions"
            ).fetchone()["n"]
            == 0
        )


def test_zero_text_unsupported_root_is_ready_without_claiming_complete(device):
    body = begin_body(device, evidence.prepare(device))
    body["manifest"] = []
    body["metadata"].update(
        format="pdf_text",
        total_pages=2,
        total_characters=0,
        coverage="unsupported",
        missing=["image_only"],
    )
    upload = begin(device, body)
    receipt = finish(device, finish_body(body, upload["upload_id"]))
    assert receipt["ready"]
    with device[0].connection() as conn:
        root = conn.execute(
            "SELECT protocol_payload FROM wrytely_agent.canvas_document_versions WHERE id=%s",
            (receipt["document_version_id"],),
        ).fetchone()["protocol_payload"]
        assert root["coverage"] == "unsupported" and root["missing"] == ["image_only"]
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM wrytely_agent.canvas_document_sections"
            ).fetchone()["n"]
            == 0
        )
    assert count(device, "source_versions") == count(device, "canvas_evidence_observations") == 0


def test_parallel_finish_reuses_one_root_and_original_receipt(device):
    body = begin_body(device, evidence.prepare(device))
    upload = begin(device, body)
    put(device, put_body(body, upload["upload_id"]))
    request = finish_body(body, upload["upload_id"])
    with ThreadPoolExecutor(max_workers=4) as pool:
        receipts = list(pool.map(lambda _: finish(device, request), range(4)))
    assert len({r["receipt_id"] for r in receipts}) == 1
    assert len({r["document_version_id"] for r in receipts}) == 1
    assert sum(not r["replayed"] for r in receipts) == 1
    with device[0].connection() as conn:
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM wrytely_agent.canvas_document_versions"
            ).fetchone()["n"]
            == 1
        )


def test_finish_uses_current_extractor_configuration_and_private_identity(device):
    body = begin_body(device, evidence.prepare(device))
    upload = begin(device, body)
    put(device, put_body(body, upload["upload_id"]))
    request = finish_body(body, upload["upload_id"])
    with pytest.raises(ValueError, match="Unconfigured"):
        device[0].finish_document_upload(
            device[1]["ingestion_bearer"], request, extractor_versions=("different.v1",)
        )
    db = device[0]
    db.provision("user_bob")
    code = db.create_pairing("user_bob", sync.ORIGIN)["code"]
    bob = db.redeem_pairing(code, "bob-finish")
    db.bind_canvas_identity(bob["ingestion_bearer"], sync.ORIGIN, "bob")
    with pytest.raises(SourceCredentialRejected):
        db.finish_document_upload(
            bob["ingestion_bearer"], request, extractor_versions=("fixture.v1",)
        )
