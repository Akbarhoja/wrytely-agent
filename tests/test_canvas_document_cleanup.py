"""Operator staging cleanup, synthetic Store and disposable Postgres only."""

from concurrent.futures import ThreadPoolExecutor

import pytest
import test_canvas_evidence as evidence
from test_canvas_document_publication import page, ready
from test_canvas_document_uploads import begin, begin_body, finish, finish_body, put, put_body
from test_canvas_sync import device as device

from shared.canvas_sync import CanvasSyncConflict


def expire(device, upload_id):
    with device[0].connection() as conn:
        conn.execute(
            "UPDATE wrytely_agent.canvas_document_uploads SET "
            "expires_at=clock_timestamp()-interval '1 second' WHERE id=%s",
            (upload_id,),
        )


def age_root(device, root, hours=25):
    with device[0].connection() as conn:
        conn.execute(
            "UPDATE wrytely_agent.canvas_document_versions SET "
            "created_at=clock_timestamp()-(%s*interval '1 hour') WHERE id=%s",
            (hours, root["document_version_id"]),
        )


def snapshot(device):
    with device[0].connection() as conn:
        return {
            table: conn.execute("SELECT * FROM wrytely_agent." + table + " ORDER BY id").fetchall()
            for table in (
                "canvas_document_versions",
                "canvas_document_sections",
                "canvas_evidence_observations",
                "canvas_evidence_events",
            )
        }


def test_expired_upload_becomes_content_free_tombstone_with_original_receipts(device):
    body = begin_body(device, evidence.prepare(device))
    upload = begin(device, body)
    request = put_body(body, upload["upload_id"])
    put(device, request)
    with device[0].connection() as conn:
        original = conn.execute(
            "SELECT * FROM wrytely_agent.canvas_document_upload_receipts ORDER BY operation"
        ).fetchall()
    expire(device, upload["upload_id"])
    result = device[0].cleanup_canvas_document_staging()
    assert result == {
        "uploads_cleaned": 1,
        "upload_parts_deleted": 1,
        "upload_bytes_deleted": len("Café\n📚".encode()),
        "roots_deleted": 0,
        "root_parts_deleted": 0,
    }
    with device[0].connection() as conn:
        row = conn.execute("SELECT * FROM wrytely_agent.canvas_document_uploads").fetchone()
        assert row["header"] == {} and row["cleaned_at"] is not None
        assert row["object_id"] is None and row["document_version_id"] is None
        assert (
            conn.execute(
                "SELECT * FROM wrytely_agent.canvas_document_upload_receipts ORDER BY operation"
            ).fetchall()
            == original
        )
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM wrytely_agent.canvas_document_upload_parts"
            ).fetchone()["n"]
            == 0
        )
    for operation in (
        lambda: begin(device, body),
        lambda: put(device, request),
        lambda: finish(device, finish_body(body, upload["upload_id"])),
    ):
        with pytest.raises(CanvasSyncConflict, match="document_expired"):
            operation()
    assert not any(device[0].cleanup_canvas_document_staging().values())


@pytest.mark.parametrize("age,expected", [(0, 0), (23, 0), (25, 1)])
def test_expired_ready_root_is_removed_only_after_orphan_age_bound(device, age, expected):
    scan = evidence.prepare(device)
    body, upload, root = ready(device, scan)
    age_root(device, root, age)
    expire(device, upload["upload_id"])
    result = device[0].cleanup_canvas_document_staging()
    assert result["uploads_cleaned"] == 1 and result["roots_deleted"] == expected
    with device[0].connection() as conn:
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM wrytely_agent.canvas_document_versions"
            ).fetchone()["n"]
            == 1 - expected
        )
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM wrytely_agent.canvas_document_sections"
            ).fetchone()["n"]
            == 1 - expected
        )
        # Shell IDs and no-text receipts are not evidence and remain for safe replay.
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM wrytely_agent.canvas_document_upload_receipts"
            ).fetchone()["n"]
            == 3
        )
        assert (
            conn.execute(
                "SELECT latest_observation_id FROM wrytely_agent.canvas_evidence_objects"
            ).fetchone()["latest_observation_id"]
            is None
        )


def test_live_ready_upload_protects_reused_old_root(device):
    scan = evidence.prepare(device)
    body, old_upload, root = ready(device, scan)
    age_root(device, root)
    expire(device, old_upload["upload_id"])
    _, live_upload, live_root = ready(device, scan, key="live-root")
    assert live_root["document_version_id"] == root["document_version_id"]
    result = device[0].cleanup_canvas_document_staging()
    assert result["uploads_cleaned"] == 1 and result["roots_deleted"] == 0
    # Active upload is neither scrubbed nor shortened by maintenance.
    with device[0].connection() as conn:
        row = conn.execute(
            "SELECT header,cleaned_at FROM wrytely_agent.canvas_document_uploads WHERE id=%s",
            (live_upload["upload_id"],),
        ).fetchone()
        assert row["header"] and row["cleaned_at"] is None
    assert (
        finish(
            device,
            finish_body(
                body | {"request_key": "unused"}, live_upload["upload_id"], key="finish-again"
            ),
        )["document_version_id"]
        == root["document_version_id"]
    )


def test_all_published_and_historical_reversion_roots_remain_readable(device):
    scan = evidence.prepare(device)
    published = []
    for index, due in enumerate((None, "2026-01-05T00:00:00Z", None)):
        if index:
            scan = evidence.next_scan(device, f"cleanup-cycle-{index}")
        body, upload, root = ready(device, scan, key=f"cleanup-{index}", due=due)
        receipt = evidence.upload(
            device, scan, page(device, scan, body, upload, key=f"cleanup-page-{index}")
        )
        evidence.close(device, scan, receipt)
        published.append(receipt["observations"][0])
        age_root(device, root)
        expire(device, upload["upload_id"])
    before = snapshot(device)
    result = device[0].cleanup_canvas_document_staging()
    assert result["uploads_cleaned"] == 3 and result["roots_deleted"] == 0
    assert snapshot(device) == before
    for item in published:
        result = device[0].read_canvas_document_sections(
            "user_alice",
            item["object_id"],
            observation_id=item["observation_id"],
            document_version_id=item["document_version_id"],
        )
        assert result["sections"][0]["text"] == "Café\n📚"
    assert published[0]["document_version_id"] == published[2]["document_version_id"]


def test_observation_payload_protects_root_even_without_binding_row(device):
    scan = evidence.prepare(device)
    body, upload, root = ready(device, scan)
    receipt = evidence.upload(device, scan, page(device, scan, body, upload))
    evidence.close(device, scan, receipt)
    age_root(device, root)
    expire(device, upload["upload_id"])
    with device[0].connection() as conn:
        conn.execute("DELETE FROM wrytely_agent.canvas_document_bindings")
    result = device[0].cleanup_canvas_document_staging()
    assert result["uploads_cleaned"] == 1 and result["roots_deleted"] == 0


def test_each_candidate_class_respects_small_pass_bound_and_reclaims_quota(device):
    scan = evidence.prepare(device)
    for index in range(5):
        _, upload, root = ready(
            device, scan, key=f"bound-{index}", due=f"2026-01-{index + 1:02d}T00:00:00Z"
        )
        age_root(device, root)
        expire(device, upload["upload_id"])
    totals = []
    for _ in range(3):
        result = device[0].cleanup_canvas_document_staging(limit=2)
        assert result["uploads_cleaned"] <= 2 and result["roots_deleted"] <= 2
        totals.append(result)
    assert sum(r["uploads_cleaned"] for r in totals) == 5
    assert sum(r["roots_deleted"] for r in totals) == 5
    # Maintenance never changes source/check/event state; quota can store a new part.
    body, upload, root = ready(device, scan, key="after-cleanup")
    assert root["ready"]
    assert snapshot(device)["canvas_evidence_observations"] == []


def test_busy_agent_is_skipped_without_waiting_or_taking_writer_lock_order(device):
    scan = evidence.prepare(device)
    _, upload, root = ready(device, scan)
    age_root(device, root)
    expire(device, upload["upload_id"])
    with device[0].connection() as writer:
        agent = writer.execute(
            "SELECT agent_id FROM wrytely_agent.canvas_document_uploads WHERE id=%s",
            (upload["upload_id"],),
        ).fetchone()["agent_id"]
        writer.execute("SELECT id FROM wrytely_agent.agents WHERE id=%s FOR UPDATE", (agent,))
        with ThreadPoolExecutor(max_workers=1) as pool:
            assert not any(
                pool.submit(device[0].cleanup_canvas_document_staging).result(timeout=3).values()
            )
    result = device[0].cleanup_canvas_document_staging()
    assert result["uploads_cleaned"] == result["roots_deleted"] == 1


def test_concurrent_passes_never_double_count_or_delete_referenced_state(device):
    _, upload, root = ready(device, evidence.prepare(device))
    age_root(device, root)
    expire(device, upload["upload_id"])
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: device[0].cleanup_canvas_document_staging(), range(2)))
    assert sum(r["uploads_cleaned"] for r in results) == 1
    assert sum(r["roots_deleted"] for r in results) == 1


def test_failure_rolls_back_part_scrubbing_and_tombstone(device, monkeypatch):
    body, upload, root = ready(device, evidence.prepare(device))
    age_root(device, root)
    expire(device, upload["upload_id"])
    before = snapshot(device)
    original = device[0]._cleanup_document_upload

    def failing(conn, upload_id):
        original(conn, upload_id)
        raise RuntimeError("synthetic maintenance interruption")

    monkeypatch.setattr(device[0], "_cleanup_document_upload", failing)
    with pytest.raises(RuntimeError):
        device[0].cleanup_canvas_document_staging()
    assert snapshot(device) == before
    with device[0].connection() as conn:
        row = conn.execute(
            "SELECT header,cleaned_at FROM wrytely_agent.canvas_document_uploads"
        ).fetchone()
        assert row["header"] and row["cleaned_at"] is None
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM wrytely_agent.canvas_document_upload_parts"
            ).fetchone()["n"]
            == 1
        )


@pytest.mark.parametrize("limit", [True, False, 0, -1, 101, 1.5, "100", None])
def test_invalid_limits_do_not_start_maintenance(device, limit):
    with pytest.raises(ValueError):
        device[0].cleanup_canvas_document_staging(limit=limit)


def test_preexisting_internal_nonprotocol_sections_are_outside_cleanup_scope(device):
    _, upload, root = ready(device, evidence.prepare(device))
    db = device[0]
    with db.connection() as conn:
        owned = conn.execute(
            "SELECT agent_id,object_id FROM wrytely_agent.canvas_document_uploads WHERE id=%s",
            (upload["upload_id"],),
        ).fetchone()
        document, _ = db._load_canvas_document(
            conn, owned["agent_id"], owned["object_id"], root["document_version_id"]
        )
        legacy = db._stage_canvas_document_sections(
            conn,
            owned["agent_id"],
            owned["object_id"],
            document,
            format="text",
            extractor_version="fixture.v1",
        )
    age_root(device, root)
    age_root(device, {"document_version_id": legacy})
    expire(device, upload["upload_id"])
    result = db.cleanup_canvas_document_staging()
    assert result["roots_deleted"] == 1
    with db.connection() as conn:
        retained = conn.execute(
            "SELECT id,protocol_payload FROM wrytely_agent.canvas_document_versions"
        ).fetchall()
        assert retained == [{"id": legacy, "protocol_payload": None}]
        assert (
            db._load_canvas_document(conn, owned["agent_id"], owned["object_id"], legacy)[0]
            == document
        )


def test_locked_root_is_skipped_and_available_for_later_bounded_pass(device):
    _, upload, root = ready(device, evidence.prepare(device))
    age_root(device, root)
    expire(device, upload["upload_id"])
    with device[0].connection() as writer:
        writer.execute(
            "SELECT id FROM wrytely_agent.canvas_document_versions WHERE id=%s FOR UPDATE",
            (root["document_version_id"],),
        )
        with ThreadPoolExecutor(max_workers=1) as pool:
            result = pool.submit(device[0].cleanup_canvas_document_staging).result(timeout=3)
        assert result["uploads_cleaned"] == 1 and result["roots_deleted"] == 0
    assert device[0].cleanup_canvas_document_staging()["roots_deleted"] == 1
