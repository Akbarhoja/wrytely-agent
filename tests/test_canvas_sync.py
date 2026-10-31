from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from threading import Barrier

import pytest
from pydantic import ValidationError

from contracts.canvas_sync import DiscoveryBatch
from shared.canvas_sync import CanvasSyncConflict
from shared.db import Store
from shared.source_connections import SourceCredentialRejected

ORIGIN = "https://canvas.example.edu"
SUBJECT = "synthetic-canvas-subject"


@pytest.fixture
def device(store, alice):
    with store.connection() as conn:
        conn.execute("TRUNCATE wrytely_agent.source_pairing_rates")
    db = Store(store._url, canvas_origins=(ORIGIN,))
    code = db.create_pairing("user_alice", ORIGIN)["code"]
    linked = db.redeem_pairing(code, "device-1")
    db.bind_canvas_identity(linked["ingestion_bearer"], ORIGIN, SUBJECT)
    return db, linked


def context(device):
    db, linked = device
    return db.canvas_connection_context(linked["ingestion_bearer"], ORIGIN)


def begin(device, key="scan-1"):
    db, linked = device
    current = context(device)
    return db.begin_sync(
        linked["ingestion_bearer"],
        linked["connection_id"],
        current["generation"],
        SUBJECT,
        current["scope_revision"],
        key,
    )


def course(value="101", state="active"):
    return {
        "provider_id": value,
        "provider_updated_at": None,
        "title": "Synthetic course",
        "reference": f"{ORIGIN}/courses/{value}",
        "content": "",
        "fields": {
            "course_code": "SYN-101",
            "timezone": "America/Denver",
            "enrollment_state": state,
        },
        "coverage": "complete",
        "missing": [],
    }


def envelope(device, scan, items=None, *, key="page-1", cursor=None, seen=None):
    linked = device[1]
    items = [course()] if items is None else items
    return {
        "schema_version": 1,
        "connection_id": linked["connection_id"],
        "generation": context(device)["generation"],
        "scan_id": scan["scan_id"],
        "batch_key": key,
        "subject": SUBJECT,
        "resource": {"course_id": None, "kind": "courses"},
        "observed_at": datetime.now(UTC).isoformat(),
        "items": items,
        "coverage": {
            "state": "partial" if cursor else "complete",
            "reason": "more_pages" if cursor else None,
            "seen_count": len(items) if seen is None else seen,
        },
        "next_cursor": cursor,
    }


def commit(device, scan, body):
    return device[0].commit_sync_batch(
        device[1]["ingestion_bearer"],
        scan["scan_id"],
        context(device)["generation"],
        scan["lease_token"],
        body["batch_key"],
        scan["checkpoint"],
        body,
    )


def finish_resource(
    device, scan, key="courses", outcome="complete", reason=None, finish_key="end-courses"
):
    return device[0].finish_resource(
        device[1]["ingestion_bearer"],
        scan["scan_id"],
        context(device)["generation"],
        scan["lease_token"],
        key,
        finish_key,
        scan["checkpoint"],
        outcome=outcome,
        reason=reason,
    )


def finish(device, scan):
    return device[0].finish_sync(
        device[1]["ingestion_bearer"],
        scan["scan_id"],
        context(device)["generation"],
        scan["lease_token"],
        "end-scan",
    )


def discover(device, items=None):
    scan = begin(device)
    receipt = commit(device, scan, envelope(device, scan, items))
    scan["checkpoint"] = receipt["checkpoint"]
    finish_resource(device, scan)
    finish(device, scan)
    return scan


def set_scope(device, ids, kinds=None, mode="explicit_set"):
    return device[0].set_canvas_scope(
        "user_alice",
        device[1]["connection_id"],
        context(device)["generation"],
        mode=mode,
        course_ids=ids,
        resource_kinds=["assignments"] if kinds is None else kinds,
    )


def test_new_context_is_private_discovery_only_even_before_identity(device):
    db, linked = device
    code = db.create_pairing("user_alice", ORIGIN)["code"]
    replacement = db.redeem_pairing(code, "device-1")
    current = db.canvas_connection_context(replacement["ingestion_bearer"], ORIGIN)
    assert current["state"] == "pending_identity"
    assert current["course_ids"] == [] and current["resource_kinds"] == []
    assert current["discovery"] == {
        "coverage": "unknown",
        "last_attempt_at": None,
        "last_complete_at": None,
    }
    assert "synthetic-canvas" not in str(current)
    assert "credential_hash" not in current and "device_public_id" not in current
    with pytest.raises(CanvasSyncConflict, match="identity_required"):
        db.begin_sync(
            replacement["ingestion_bearer"],
            linked["connection_id"],
            current["generation"],
            SUBJECT,
            current["scope_revision"],
            "pending",
        )


def test_begin_replay_is_original_response_and_only_one_scan_is_active(device):
    scan = begin(device)
    assert begin(device) == scan
    with pytest.raises(CanvasSyncConflict, match="resume_existing_scan"):
        begin(device, "different")
    db, linked = device
    resumed = db.resume_sync(linked["ingestion_bearer"], scan["scan_id"], 1, "resume-1")
    assert resumed["lease_token"] != scan["lease_token"]
    assert begin(device) == scan  # Old begin replay cannot recover a replaced writer lease.


def test_course_discovery_closes_with_no_academic_sources_or_implicit_selection(device):
    discover(device)
    current = context(device)
    assert current["course_ids"] == []
    assert current["discovery"]["coverage"] == "complete"
    assert current["discovery"]["last_complete_at"] is not None
    with device[0].connection() as conn:
        assert (
            conn.execute("SELECT count(*) AS n FROM wrytely_agent.academic_sources").fetchone()["n"]
            == 0
        )
    selected = set_scope(device, ["101"])
    assert selected["course_ids"] == ["101"] and selected["generation"] == 2


def test_paginated_discovery_checkpoint_survives_new_store_and_lost_ack(device):
    db, linked = device
    scan = begin(device)
    body = envelope(device, scan, cursor="private-opaque-next")
    receipt = commit(device, scan, body)
    before = context(device)
    restarted = Store(db._url, canvas_origins=(ORIGIN,))
    resumed = restarted.resume_sync(linked["ingestion_bearer"], scan["scan_id"], 1, "resume-1")
    assert resumed["checkpoint"] == receipt["checkpoint"]
    replay = restarted.commit_sync_batch(
        linked["ingestion_bearer"],
        scan["scan_id"],
        1,
        scan["lease_token"],
        body["batch_key"],
        scan["checkpoint"],
        body,
    )
    assert replay == {**receipt, "replayed": True}
    assert context(device) == before
    changed = deepcopy(body)
    changed["items"][0]["title"] = "Changed"
    with pytest.raises(CanvasSyncConflict, match="replay_conflict"):
        commit(device, scan, changed)
    final_body = envelope(device, resumed, [course("102")], key="page-2", seen=2)
    final = commit(device, resumed, final_body)
    resumed["checkpoint"] = final["checkpoint"]
    finish_resource(device, resumed)
    assert finish(device, resumed)["coverage"] == "complete"


def test_uncommitted_batch_needs_fresh_lease_and_same_capture_can_resume(device):
    scan = begin(device)
    body = envelope(device, scan)
    with device[0].connection() as conn:
        conn.execute(
            "UPDATE wrytely_agent.canvas_scans SET lease_expires_at=now()-interval '1 second'"
        )
    with pytest.raises(CanvasSyncConflict, match="lease_expired"):
        commit(device, scan, body)
    resumed = device[0].resume_sync(device[1]["ingestion_bearer"], scan["scan_id"], 1, "resume")
    first = commit(device, resumed, body)
    assert first["replayed"] is False
    assert (
        device[0].resume_sync(device[1]["ingestion_bearer"], scan["scan_id"], 1, "resume")[
            "lease_token"
        ]
        == resumed["lease_token"]
    )


def test_stale_checkpoint_and_replaced_lease_cannot_advance_new_page(device):
    scan = begin(device)
    first = commit(device, scan, envelope(device, scan, cursor="next"))
    resumed = device[0].resume_sync(device[1]["ingestion_bearer"], scan["scan_id"], 1, "resume")
    page = envelope(device, resumed, [course("102")], key="page-2", seen=2)
    with pytest.raises(CanvasSyncConflict, match="lease_replaced"):
        commit(device, scan, page)
    old_checkpoint = dict(resumed, checkpoint=scan["checkpoint"])
    with pytest.raises(CanvasSyncConflict, match="checkpoint_changed"):
        commit(device, old_checkpoint, page)
    assert resumed["checkpoint"] == first["checkpoint"]


def test_incomplete_enumeration_can_terminalize_partial_and_replay_without_freshness(device):
    scan = begin(device)
    receipt = commit(device, scan, envelope(device, scan, cursor="lost-cursor"))
    scan["checkpoint"] = receipt["checkpoint"]
    with pytest.raises(CanvasSyncConflict, match="incomplete_resource"):
        finish_resource(device, scan)
    partial = finish_resource(device, scan, outcome="partial", reason="cursor_invalid")
    assert partial["source_manifest_digest"] is None
    assert finish(device, scan)["coverage"] == "partial"
    assert context(device)["discovery"]["last_complete_at"] is None
    with device[0].connection() as conn:
        conn.execute(
            "UPDATE wrytely_agent.canvas_scans SET lease_expires_at=now()-interval '1 second'"
        )
    replay = finish_resource(device, scan, outcome="partial", reason="cursor_invalid")
    assert replay == {**partial, "replayed": True}
    assert finish(device, scan)["replayed"] is True


def test_finish_cannot_claim_complete_without_observations_or_open_resources(device):
    scan = begin(device)
    with pytest.raises(CanvasSyncConflict, match="incomplete_resource"):
        finish_resource(device, scan)
    with pytest.raises(CanvasSyncConflict, match="resources_open"):
        finish(device, scan)


def test_empty_observed_catalog_is_complete_but_does_not_delete_prior_evidence(device):
    discover(device)
    first = context(device)["discovery"]["last_complete_at"]
    second = begin(device, "scan-2")
    receipt = commit(device, second, envelope(device, second, []))
    second["checkpoint"] = receipt["checkpoint"]
    finish_resource(device, second)
    finish(device, second)
    assert context(device)["discovery"]["last_complete_at"] >= first
    with device[0].connection() as conn:
        row = conn.execute(
            "SELECT missing_pending_confirmation FROM wrytely_agent.canvas_catalog "
            "WHERE course_id='101'"
        ).fetchone()
    assert row["missing_pending_confirmation"] is True
    with pytest.raises(CanvasSyncConflict, match="course_not_discovered"):
        set_scope(device, ["101"])


def test_partial_scan_does_not_erase_previous_complete_time_or_course(device):
    discover(device)
    previous = context(device)["discovery"]["last_complete_at"]
    second = begin(device, "scan-2")
    finish_resource(device, second, outcome="restricted", reason="permission_denied")
    finish(device, second)
    current = context(device)
    assert current["discovery"]["coverage"] == "restricted"
    assert current["discovery"]["last_complete_at"] == previous
    assert set_scope(device, ["101"])["course_ids"] == ["101"]


def test_scope_changes_fence_scans_without_repairing_and_identical_scope_is_idempotent(device):
    discover(device)
    scan = begin(device, "scan-2")
    first = set_scope(device, ["101"])
    assert first["generation"] == 2 and first["scope_revision"] == 1
    assert set_scope(device, ["101"]) == first
    assert context(device) == first
    with pytest.raises(CanvasSyncConflict, match="generation_changed"):
        device[0].resume_sync(device[1]["ingestion_bearer"], scan["scan_id"], 1, "late")
    empty = set_scope(device, [])
    assert empty["generation"] == 3 and empty["course_ids"] == []
    new_scan = begin(device, "scan-3")
    with device[0].connection() as conn:
        keys = conn.execute(
            "SELECT resource_key FROM wrytely_agent.canvas_resources WHERE scan_id=%s",
            (new_scan["scan_id"],),
        ).fetchall()
    assert keys == [{"resource_key": "courses"}]


def test_posted_unknown_course_and_cross_owner_scope_cannot_grant_collection(device):
    with pytest.raises(CanvasSyncConflict, match="course_not_discovered"):
        set_scope(device, ["999"])
    db, linked = device
    db.provision("user_bob")
    with pytest.raises(LookupError, match="Not found"):
        db.set_canvas_scope(
            "user_bob",
            linked["connection_id"],
            1,
            mode="explicit_set",
            course_ids=[],
            resource_kinds=[],
        )
    with pytest.raises(SourceCredentialRejected):
        db.canvas_connection_context("x" * 43, ORIGIN)
    with pytest.raises(SourceCredentialRejected):
        db.canvas_connection_context(linked["ingestion_bearer"], "https://other.example.edu")


def test_all_active_selects_only_observed_active_courses_and_tracks_uncollected_resources(device):
    discover(device, [course(), course("102", "completed")])
    selected = set_scope(device, [], mode="all_active")
    assert selected["course_ids"] == ["101"]
    scan = begin(device, "all-active")
    receipt = commit(device, scan, envelope(device, scan, [course("103")]))
    scan["checkpoint"] = receipt["checkpoint"]
    assert context(device)["course_ids"] == ["101", "103"]
    finish_resource(device, scan)
    with pytest.raises(CanvasSyncConflict, match="resources_open"):
        finish(device, scan)
    for course_key in ("101/assignments", "103/assignments"):
        with pytest.raises(CanvasSyncConflict, match="incomplete_resource"):
            finish_resource(device, scan, key=course_key, finish_key=course_key.replace("/", ":"))
        finish_resource(
            device,
            scan,
            key=course_key,
            finish_key=course_key.replace("/", ":"),
            outcome="unsupported",
            reason="unsupported_format",
        )
    assert finish(device, scan)["coverage"] == "partial"


def test_repair_and_subject_switch_clear_scope_catalog_and_abort_active_scan(device):
    discover(device)
    set_scope(device, ["101"])
    scan = begin(device, "selected")
    db, linked = device
    code = db.create_pairing("user_alice", ORIGIN)["code"]
    new = db.redeem_pairing(code, "device-1")
    db.bind_canvas_identity(new["ingestion_bearer"], ORIGIN, "different-subject")
    current = db.canvas_connection_context(new["ingestion_bearer"], ORIGIN)
    assert current["course_ids"] == [] and current["discovery"]["coverage"] == "unknown"
    with db.connection() as conn:
        assert (
            conn.execute(
                "SELECT state FROM wrytely_agent.canvas_scans WHERE id=%s", (scan["scan_id"],)
            ).fetchone()["state"]
            == "aborted"
        )
    with pytest.raises(CanvasSyncConflict, match="course_not_discovered"):
        db.set_canvas_scope(
            "user_alice",
            new["connection_id"],
            current["generation"],
            mode="explicit_set",
            course_ids=["101"],
            resource_kinds=["assignments"],
        )


def test_revoke_prevents_receipt_replay(device):
    scan = begin(device)
    body = envelope(device, scan)
    commit(device, scan, body)
    device[0].rotate_or_revoke("user_alice", device[1]["connection_id"])
    with pytest.raises(SourceCredentialRejected):
        device[0].commit_sync_batch(
            device[1]["ingestion_bearer"],
            scan["scan_id"],
            1,
            scan["lease_token"],
            body["batch_key"],
            scan["checkpoint"],
            body,
        )


def test_expired_scan_cannot_resume_and_new_scan_has_monotonic_sequence(device):
    scan = begin(device)
    with device[0].connection() as conn:
        conn.execute("UPDATE wrytely_agent.canvas_scans SET expires_at=now()-interval '1 second'")
    context(device)  # Persist expiry/abort history even when a later invalid request rolls back.
    with pytest.raises(CanvasSyncConflict, match="scan_terminal"):
        device[0].resume_sync(device[1]["ingestion_bearer"], scan["scan_id"], 1, "expired")
    assert begin(device, "next-scan")["scan_sequence"] == 2


def test_atomic_rollback_on_bad_second_course_preserves_checkpoint_and_catalog(device):
    scan = begin(device)
    body = envelope(device, scan, [course(), course("102")])
    body["items"][1]["reference"] = "https://unrelated.example.edu/courses/102"
    with pytest.raises(ValueError, match="reference mismatch"):
        commit(device, scan, body)
    with device[0].connection() as conn:
        assert (
            conn.execute("SELECT count(*) AS n FROM wrytely_agent.canvas_catalog").fetchone()["n"]
            == 0
        )
        assert (
            conn.execute("SELECT count(*) AS n FROM wrytely_agent.canvas_scan_courses").fetchone()[
                "n"
            ]
            == 0
        )
    body["items"][1] = course("102")
    assert commit(device, scan, body)["checkpoint"]["sequence"] == 1


def test_concurrent_duplicate_batches_commit_one_receipt(device):
    scan = begin(device)
    body = envelope(device, scan)
    barrier = Barrier(2)

    def run(_):
        barrier.wait(timeout=5)
        return commit(device, scan, body)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(run, range(2)))
    assert {r["replayed"] for r in results} == {True, False}
    assert results[0]["receipt_id"] == results[1]["receipt_id"]


@pytest.mark.parametrize(
    "field,value",
    [("content", "Not metadata"), ("provider_id", "../101"), ("fields", {"extra": "not-declared"})],
)
def test_discovery_cannot_smuggle_course_content_or_invalid_fields(device, field, value):
    scan = begin(device)
    body = envelope(device, scan)
    body["items"][0][field] = value
    with pytest.raises(ValidationError):
        commit(device, scan, body)


@pytest.mark.parametrize("timestamp", ["2026-01-01", "2026-01-01T00:00:00+01:60"])
def test_observations_require_valid_aware_timestamps(device, timestamp):
    scan = begin(device)
    body = envelope(device, scan)
    body["observed_at"] = timestamp
    with pytest.raises(ValidationError):
        commit(device, scan, body)


def test_future_or_prescan_capture_cannot_refresh_discovery(device):
    scan = begin(device)
    for timestamp in [
        datetime.now(UTC) + timedelta(minutes=6),
        datetime.now(UTC) - timedelta(days=2),
    ]:
        body = envelope(device, scan)
        body["observed_at"] = timestamp.isoformat()
        with pytest.raises(ValueError, match="outside scan window"):
            commit(device, scan, body)


def test_item_and_cursor_limits_reject_before_persistence(device):
    scan = begin(device)
    body = envelope(device, scan, [course(str(i)) for i in range(1, 52)])
    with pytest.raises(ValidationError):
        DiscoveryBatch.model_validate(body)
    body = envelope(device, scan, cursor="x" * 4001)
    with pytest.raises(ValidationError):
        commit(device, scan, body)


@pytest.mark.parametrize("limit", [0, 21, True, "2"])
def test_private_connection_list_rejects_invalid_limits(device, limit):
    with pytest.raises(ValueError, match="list limit"):
        device[0].list_source_connections("user_alice", limit=limit)


def test_private_connection_list_paginates_and_binds_cursor_to_owner(device):
    db, linked = device
    db.provision("user_bob")
    code = db.create_pairing("user_alice", ORIGIN)["code"]
    second = db.redeem_pairing(code, "device-2")
    first_page = db.list_source_connections("user_alice", limit=1)
    assert first_page["connections"][0]["connection_id"] == second["connection_id"]
    next_page = db.list_source_connections("user_alice", limit=1, cursor=first_page["next_cursor"])
    assert next_page["connections"][0]["connection_id"] == linked["connection_id"]
    assert next_page["next_cursor"] is None
    assert db.list_source_connections("unknown") == {"connections": [], "next_cursor": None}
    for user, cursor in [("user_bob", first_page["next_cursor"]), ("user_alice", "bad")]:
        with pytest.raises(LookupError, match="^Not found$"):
            db.list_source_connections(user, cursor=cursor)
    assert "credential_hash" not in str(first_page)
    assert "device-2" not in str(first_page)


def test_other_account_cannot_replay_a_saved_batch(device):
    scan = begin(device)
    body = envelope(device, scan)
    commit(device, scan, body)
    db, _ = device
    db.provision("user_bob")
    code = db.create_pairing("user_bob", ORIGIN)["code"]
    other = db.redeem_pairing(code, "other-device")
    db.bind_canvas_identity(other["ingestion_bearer"], ORIGIN, "bob-subject")
    with pytest.raises(SourceCredentialRejected):
        db.commit_sync_batch(
            other["ingestion_bearer"],
            scan["scan_id"],
            1,
            scan["lease_token"],
            body["batch_key"],
            scan["checkpoint"],
            body,
        )


def test_cursor_cycle_and_boolean_checkpoint_cannot_advance(device):
    scan = begin(device)
    first = commit(device, scan, envelope(device, scan, cursor="cycle"))
    scan["checkpoint"] = first["checkpoint"]
    second = envelope(device, scan, [course("102")], key="page-2", cursor="cycle", seen=2)
    with pytest.raises(CanvasSyncConflict, match="cursor_cycle"):
        commit(device, scan, second)
    bad_scan = deepcopy(scan)
    bad_scan["checkpoint"]["sequence"] = True
    second["next_cursor"] = "different"
    with pytest.raises(ValidationError):
        commit(device, bad_scan, second)


def test_schema_version_is_integer_not_boolean(device):
    scan = begin(device)
    body = envelope(device, scan)
    body["schema_version"] = True
    with pytest.raises(ValidationError):
        commit(device, scan, body)


def test_revoke_racing_batch_never_leaves_an_active_old_scan(device):
    scan = begin(device)
    body = envelope(device, scan)
    barrier = Barrier(2)
    db, linked = device

    def run(which):
        barrier.wait(timeout=5)
        if which == "revoke":
            return db.rotate_or_revoke("user_alice", linked["connection_id"])
        try:
            return db.commit_sync_batch(
                linked["ingestion_bearer"],
                scan["scan_id"],
                1,
                scan["lease_token"],
                body["batch_key"],
                scan["checkpoint"],
                body,
            )
        except SourceCredentialRejected:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(run, ["batch", "revoke"]))
    with db.connection() as conn:
        assert (
            conn.execute(
                "SELECT state FROM wrytely_agent.canvas_scans WHERE id=%s", (scan["scan_id"],)
            ).fetchone()["state"]
            == "aborted"
        )
    with pytest.raises(SourceCredentialRejected):
        db.canvas_connection_context(linked["ingestion_bearer"], ORIGIN)


def test_repeated_existing_consent_is_idempotent_after_course_becomes_missing(device):
    discover(device)
    first = set_scope(device, ["101"])
    scan = begin(device, "empty-after-consent")
    receipt = commit(device, scan, envelope(device, scan, []))
    scan["checkpoint"] = receipt["checkpoint"]
    finish_resource(device, scan)
    repeated = set_scope(device, ["101"])
    assert repeated["generation"] == first["generation"]
    assert repeated["scope_revision"] == first["scope_revision"]


def test_expiry_during_batch_rolls_back_catalog_checkpoint_and_receipt(device, monkeypatch):
    db, _ = device
    scan = begin(device)
    body = envelope(device, scan)
    save = db._save

    def expire_before_commit(conn, scan_row, operation, key, digest, result):
        if operation == "batch":
            conn.execute(
                "UPDATE wrytely_agent.canvas_scans SET "
                "lease_expires_at=clock_timestamp()-interval '1 second' "
                "WHERE id=%s",
                (scan_row["id"],),
            )
        return save(conn, scan_row, operation, key, digest, result)

    with monkeypatch.context() as patch:
        patch.setattr(db, "_save", expire_before_commit)
        with pytest.raises(CanvasSyncConflict, match="lease_expired"):
            commit(device, scan, body)
    with db.connection() as conn:
        assert (
            conn.execute("SELECT count(*) AS n FROM wrytely_agent.canvas_catalog").fetchone()["n"]
            == 0
        )
    assert commit(device, scan, body)["checkpoint"]["sequence"] == 1
