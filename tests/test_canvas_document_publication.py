"""Synthetic atomic document publication and existing pinned section reads."""

from copy import deepcopy
from uuid import uuid4

import pytest
import test_canvas_evidence as evidence
import test_canvas_sync as sync
from test_canvas_document_uploads import begin, begin_body, finish, finish_body, put, put_body
from test_canvas_sync import device as device

from shared.canvas_sync import CanvasSyncConflict
from shared.source_connections import SourceCredentialRejected


def ready(device, scan, key="doc", due=None):
    body = begin_body(device, scan, key="begin-" + key)
    if due:
        body["object_fields"]["due_at"] = due
    upload = begin(device, body)
    put(device, put_body(body, upload["upload_id"], key="put-" + key))
    root = finish(device, finish_body(body, upload["upload_id"], key="finish-" + key))
    return body, upload, root


def page(device, scan, body, upload, key="document-page"):
    value = evidence.body(device, scan, [], key=key)
    value.update(schema_version=2, batch_type="canvas_documents")
    value["items"] = [
        {
            "kind": body["owner_object"]["kind"],
            "provider_id": body["owner_object"]["provider_id"],
            "provider_updated_at": body["metadata"]["provider_updated_at"],
            "title": body["metadata"]["title"],
            "reference": sync.ORIGIN + "/courses/101/assignments/101",
            "upload_id": upload["upload_id"],
        }
    ]
    value["coverage"]["seen_count"] = 1
    return value


def rows(device, table):
    assert table in {
        "canvas_evidence_observations",
        "canvas_evidence_events",
        "canvas_document_bindings",
        "canvas_document_versions",
        "source_versions",
        "canvas_resource_items",
    }
    with device[0].connection() as conn:
        return conn.execute("SELECT * FROM wrytely_agent." + table).fetchall()


def test_publish_ready_document_atomically_and_read_pinned_original_sections(device):
    scan = evidence.prepare(device)
    body, upload, root = ready(device, scan)
    value = page(device, scan, body, upload)
    receipt = evidence.upload(device, scan, value)
    assert receipt["schema_version"] == 2 and receipt["batch_type"] == "canvas_documents"
    assert "source_versions" not in receipt
    observed = receipt["observations"][0]
    assert observed["document_version_id"] == root["document_version_id"]
    assert observed["document_digest"] == root["document_digest"]
    assert evidence.upload(device, scan, value) == {**receipt, "replayed": True}
    assert len(rows(device, "canvas_evidence_observations")) == 1
    assert len(rows(device, "canvas_evidence_events")) == 1
    assert rows(device, "source_versions") == []
    assert evidence.close(device, scan, receipt)["source_manifest_digest"] is not None
    result = device[0].read_canvas_document_sections(
        "user_alice",
        observed["object_id"],
        observation_id=observed["observation_id"],
        document_version_id=observed["document_version_id"],
    )
    assert result["sections"][0]["text"] == "Café\n📚" and result["freshness"]["usable"]
    listing = device[0].list_canvas_evidence("user_alice", connection_id=body["connection_id"])
    assert str(listing["sources"][0]["document_version_id"]) == root["document_version_id"]
    with pytest.raises(ValueError, match="pinned document"):
        device[0].read_canvas_evidence("user_alice", observed["object_id"])
    device[0].provision("user_bob")
    with pytest.raises(LookupError):
        device[0].read_canvas_document_sections(
            "user_bob",
            observed["object_id"],
            observation_id=observed["observation_id"],
            document_version_id=observed["document_version_id"],
        )


def test_repeat_changed_fields_and_reversion_retain_roots_and_observation_history(device):
    roots = []
    checks = []
    scan = evidence.prepare(device)
    for index, due in enumerate([None, None, "2026-01-04T00:00:00Z", None]):
        if index:
            scan = evidence.next_scan(device, f"publication-cycle-{index}")
        body, upload, root = ready(device, scan, key=f"doc-{index}", due=due)
        receipt = evidence.upload(
            device, scan, page(device, scan, body, upload, key=f"publication-page-{index}")
        )
        evidence.close(device, scan, receipt)
        roots.append(root["document_version_id"])
        checks.append(receipt["observations"][0]["observation_id"])
        assert len(rows(device, "canvas_evidence_events")) == [1, 1, 2, 3][index]
    assert roots[0] == roots[1] == roots[3] != roots[2]
    assert len(set(checks)) == 4 and len(rows(device, "canvas_document_versions")) == 2
    events = rows(device, "canvas_evidence_events")
    changed = [e for e in events if not e["changes"]["initial"]]
    assert all(e["changes"]["changed_fields"] == ["due_at"] for e in changed)
    assert {str(e["previous_observation_id"]) for e in changed} == set(checks[1:3])
    assert rows(device, "source_versions") == []


@pytest.mark.parametrize(
    "change",
    [
        "unready",
        "missing",
        "owner",
        "title",
        "reference",
        "duplicate",
        "extra",
        "discriminator",
        "version",
        "count",
    ],
)
def test_invalid_document_batch_is_atomic_and_does_not_advance_checkpoint(device, change):
    scan = evidence.prepare(device)
    body, upload, root = ready(device, scan)
    value = page(device, scan, body, upload)
    if change == "unready":
        other = begin(device, begin_body(device, scan, key="unready"))
        value["items"][0]["upload_id"] = other["upload_id"]
    if change == "missing":
        value["items"][0]["upload_id"] = str(uuid4())
    if change == "owner":
        value["items"][0]["provider_id"] = "other"
    if change == "title":
        value["items"][0]["title"] = "other"
    if change == "reference":
        value["items"][0]["reference"] = "https://evil.invalid/courses/101"
    if change == "duplicate":
        value["items"] *= 2
        value["coverage"]["seen_count"] = 2
    if change == "extra":
        value["items"][0]["content"] = "forged"
    if change == "discriminator":
        value["operation"] = "finish_document"
    if change == "version":
        value["schema_version"] = True
    if change == "count":
        value["coverage"]["seen_count"] = 2
    with pytest.raises((ValueError, LookupError)):
        evidence.upload(device, scan, value)
    assert (
        rows(device, "canvas_evidence_observations")
        == rows(device, "canvas_document_bindings")
        == rows(device, "canvas_evidence_events")
        == []
    )
    with device[0].connection() as conn:
        assert (
            conn.execute(
                "SELECT checkpoint FROM wrytely_agent.canvas_scans WHERE id=%s", (scan["scan_id"],)
            ).fetchone()["checkpoint"]
            == scan["checkpoint"]
        )


def test_second_missing_upload_rolls_back_first_publication_and_quota_release(device):
    scan = evidence.prepare(device)
    body, upload, root = ready(device, scan)
    value = page(device, scan, body, upload)
    second = deepcopy(value["items"][0])
    second["provider_id"] = "102"
    second["upload_id"] = str(uuid4())
    value["items"].append(second)
    value["coverage"]["seen_count"] = 2
    with pytest.raises(LookupError):
        evidence.upload(device, scan, value)
    assert (
        rows(device, "canvas_evidence_observations")
        == rows(device, "canvas_document_bindings")
        == []
    )
    with device[0].connection() as conn:
        assert (
            conn.execute(
                "SELECT published_at FROM wrytely_agent.canvas_document_uploads WHERE id=%s",
                (upload["upload_id"],),
            ).fetchone()["published_at"]
            is None
        )


def test_final_lease_failure_rolls_back_entire_publication(device, monkeypatch):
    scan = evidence.prepare(device)
    body, upload, root = ready(device, scan)
    value = page(device, scan, body, upload)
    original = device[0]._save

    def late(conn, scan, operation, key, digest, result):
        if operation == "batch":
            conn.execute(
                "UPDATE wrytely_agent.canvas_scans SET "
                "lease_expires_at=clock_timestamp()-interval '1 second' WHERE id=%s",
                (scan["id"],),
            )
        return original(conn, scan, operation, key, digest, result)

    monkeypatch.setattr(device[0], "_save", late)
    with pytest.raises(CanvasSyncConflict, match="lease_expired"):
        evidence.upload(device, scan, value)
    assert (
        rows(device, "canvas_evidence_observations")
        == rows(device, "canvas_document_bindings")
        == rows(device, "canvas_evidence_events")
        == []
    )


@pytest.mark.parametrize("control", ["revoke", "scope", "expired_upload", "expired_lease"])
def test_publication_requires_current_controls_even_for_receipt_replay(device, control):
    scan = evidence.prepare(device)
    body, upload, root = ready(device, scan)
    value = page(device, scan, body, upload)
    evidence.upload(device, scan, value)
    if control == "revoke":
        device[0].rotate_or_revoke("user_alice", body["connection_id"])
    if control == "scope":
        sync.set_scope(device, [], kinds=[])
    if control.startswith("expired"):
        with device[0].connection() as conn:
            if control == "expired_upload":
                conn.execute(
                    "UPDATE wrytely_agent.canvas_document_uploads SET "
                    "expires_at=clock_timestamp()-interval '1 second' WHERE id=%s",
                    (upload["upload_id"],),
                )
            else:
                conn.execute(
                    "UPDATE wrytely_agent.canvas_scans SET "
                    "lease_expires_at=clock_timestamp()-interval '1 second' WHERE id=%s",
                    (scan["scan_id"],),
                )
    with pytest.raises((CanvasSyncConflict, SourceCredentialRejected)):
        device[0].commit_sync_batch(
            device[1]["ingestion_bearer"],
            scan["scan_id"],
            value["generation"],
            scan["lease_token"],
            value["batch_key"],
            scan["checkpoint"],
            value,
        )
    assert len(rows(device, "canvas_evidence_observations")) == 1


def test_mixed_inline_document_pages_are_rejected_both_directions(device):
    scan = evidence.prepare(device)
    body, upload, root = ready(device, scan)
    first = page(device, scan, body, upload)
    first["next_cursor"] = "opaque-next"
    first["coverage"].update(state="partial", reason="more_pages")
    receipt = evidence.upload(device, scan, first)
    scan["checkpoint"] = receipt["checkpoint"]
    inline = evidence.body(device, scan, key="inline-mix", seen=2)
    with pytest.raises(CanvasSyncConflict, match="resource_format_conflict"):
        evidence.upload(device, scan, inline)
    # Separate resource scan begins with inline, then refuses document mode.
    evidence.close(device, scan, receipt, partial=True)
    scan = evidence.next_scan(device, "inline-first-cycle")
    inline = evidence.body(device, scan, key="inline-first", cursor="next-inline")
    receipt = evidence.upload(device, scan, inline)
    scan["checkpoint"] = receipt["checkpoint"]
    body, upload, root = ready(device, scan, key="mixed-second")
    value = page(device, scan, body, upload, key="doc-mix")
    value["coverage"]["seen_count"] = 2
    with pytest.raises(CanvasSyncConflict, match="resource_format_conflict"):
        evidence.upload(device, scan, value)


def test_partial_document_and_failed_latest_scan_never_fall_back_to_complete(device):
    scan = evidence.prepare(device)
    body, upload, root = ready(device, scan)
    receipt = evidence.upload(device, scan, page(device, scan, body, upload))
    evidence.close(device, scan, receipt)
    source = receipt["observations"][0]
    second = evidence.next_scan(device, "partial-latest")
    value = evidence.body(device, second, [], key="partial-empty")
    value.update(schema_version=2, batch_type="canvas_documents")
    value["coverage"].update(state="partial", reason="permission_denied", seen_count=0)
    receipt = evidence.upload(device, second, value)
    with pytest.raises(CanvasSyncConflict, match="incomplete_resource"):
        sync.finish_resource(
            device,
            {**second, "checkpoint": receipt["checkpoint"]},
            key="101/assignments",
            finish_key="bad-complete",
        )
    evidence.close(device, second, receipt, partial=True)
    result = device[0].read_canvas_document_sections(
        "user_alice",
        source["object_id"],
        observation_id=source["observation_id"],
        document_version_id=source["document_version_id"],
    )
    assert (
        not result["freshness"]["usable"] and result["freshness"]["reason"] == "resource_incomplete"
    )


def test_large_published_document_can_be_paged_without_prefix_completion(device):
    from dataclasses import asdict

    from shared.document_sections import split_document_text

    scan = evidence.prepare(device)
    body = begin_body(device, scan)
    document = split_document_text("📚" * 100_000)
    body["manifest"], parts = [], []
    for section in document.sections:
        row = asdict(section)
        parts.append({"slot": row["slot"], "text": row.pop("text")})
        body["manifest"].append(row)
    body["metadata"]["total_characters"] = 100_000
    upload = begin(device, body)
    put(device, put_body(body, upload["upload_id"], parts=parts))
    finish(device, finish_body(body, upload["upload_id"]))
    receipt = evidence.upload(device, scan, page(device, scan, body, upload))
    evidence.close(device, scan, receipt)
    source = receipt["observations"][0]
    first = 0
    chunks = []
    while True:
        result = device[0].read_canvas_document_sections(
            "user_alice",
            source["object_id"],
            observation_id=source["observation_id"],
            document_version_id=source["document_version_id"],
            first_slot=first,
            limit=20,
        )
        assert sum(len(s["text"]) for s in result["sections"]) <= 40_000
        chunks.extend(s["text"] for s in result["sections"])
        if result["next_slot"] is None:
            break
        assert result["next_slot"] > first
        first = result["next_slot"]
    assert "".join(chunks) == "📚" * 100_000
    with pytest.raises(LookupError):
        device[0].read_canvas_document_sections(
            "user_alice",
            source["object_id"],
            observation_id=source["observation_id"],
            document_version_id=str(uuid4()),
        )


def test_file_document_finalization_and_read_use_selected_file_scope(device):
    scan = evidence.prepare(device, kinds=["files"])
    body = begin_body(device, scan)
    body["resource"]["kind"] = "files"
    body["owner_object"] = {"kind": "file", "provider_id": "901"}
    body["object_fields"] = {"filename": "syllabus.txt", "content_type": "text/plain"}
    upload = begin(device, body)
    put(device, put_body(body, upload["upload_id"]))
    finish(device, finish_body(body, upload["upload_id"]))
    value = page(device, scan, body, upload)
    value["resource"]["kind"] = "files"
    receipt = evidence.upload(device, scan, value)
    evidence.close(device, scan, receipt, kind="files")
    source = receipt["observations"][0]
    result = device[0].read_canvas_document_sections(
        "user_alice",
        source["object_id"],
        observation_id=source["observation_id"],
        document_version_id=source["document_version_id"],
    )
    assert result["freshness"]["usable"]


def test_partial_zero_text_documents_cannot_finish_as_complete(device):
    scan = evidence.prepare(device)
    body = begin_body(device, scan)
    body["manifest"] = []
    body["metadata"].update(
        total_characters=0, coverage="restricted", missing=["permission_denied"]
    )
    upload = begin(device, body)
    finish(device, finish_body(body, upload["upload_id"]))
    value = page(device, scan, body, upload)
    receipt = evidence.upload(device, scan, value)
    with pytest.raises(CanvasSyncConflict, match="incomplete_resource"):
        evidence.close(device, scan, receipt)
    evidence.close(device, scan, receipt, partial=True)
    assert receipt["observations"][0]["coverage"] == "restricted"
    assert rows(device, "source_versions") == []


def test_schema1_and_document_batches_share_replay_namespace(device):
    scan = evidence.prepare(device)
    body, upload, root = ready(device, scan)
    # The course-discovery batch already used page-1 in this same scan.
    with pytest.raises(CanvasSyncConflict, match="replay_conflict"):
        evidence.upload(device, scan, page(device, scan, body, upload, key="page-1"))
    assert rows(device, "canvas_evidence_observations") == []


@pytest.mark.parametrize("same_time", [False, True])
def test_historical_or_ambiguous_document_does_not_replace_current_evidence(device, same_time):
    from datetime import UTC, datetime, timedelta

    scan = evidence.prepare(device)
    body, upload, root = ready(device, scan)
    first = page(device, scan, body, upload)
    first["observed_at"] = (datetime.now(UTC) + timedelta(minutes=2)).isoformat()
    receipt = evidence.upload(device, scan, first)
    evidence.close(device, scan, receipt)
    current = receipt["observations"][0]
    scan = evidence.next_scan(device, "history-next")
    body, upload, root = ready(device, scan, key="history-root", due="2026-01-05T00:00:00Z")
    value = page(device, scan, body, upload, key="history-page")
    value["observed_at"] = (
        first["observed_at"]
        if same_time
        else (datetime.now(UTC) + timedelta(minutes=1)).isoformat()
    )
    if same_time:
        with pytest.raises(CanvasSyncConflict, match="ambiguous_observation_time"):
            evidence.upload(device, scan, value)
        assert len(rows(device, "canvas_evidence_observations")) == 1
    else:
        historical = evidence.upload(device, scan, value)
        assert historical["observations"][0]["historical"]
        evidence.close(device, scan, historical, partial=True)
        result = device[0].read_canvas_document_sections(
            "user_alice",
            historical["observations"][0]["object_id"],
            observation_id=historical["observations"][0]["observation_id"],
            document_version_id=root["document_version_id"],
        )
        assert result["historical"] and not result["freshness"]["usable"]
    with device[0].connection() as conn:
        assert (
            str(
                conn.execute(
                    "SELECT latest_observation_id FROM wrytely_agent.canvas_evidence_objects "
                    "WHERE id=%s",
                    (current["object_id"],),
                ).fetchone()["latest_observation_id"]
            )
            == current["observation_id"]
        )
    assert len(rows(device, "canvas_evidence_events")) == 1


def test_second_account_cannot_publish_owned_ready_root(device):
    scan = evidence.prepare(device)
    body, upload, root = ready(device, scan)
    value = page(device, scan, body, upload)
    db = device[0]
    db.provision("user_bob")
    code = db.create_pairing("user_bob", sync.ORIGIN)["code"]
    bob = db.redeem_pairing(code, "bob-doc-publish")
    db.bind_canvas_identity(bob["ingestion_bearer"], sync.ORIGIN, "bob")
    with pytest.raises(SourceCredentialRejected):
        db.commit_sync_batch(
            bob["ingestion_bearer"],
            scan["scan_id"],
            value["generation"],
            scan["lease_token"],
            value["batch_key"],
            scan["checkpoint"],
            value,
        )
    assert rows(device, "canvas_evidence_observations") == []
