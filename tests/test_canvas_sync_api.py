"""Owned HTTP acceptance of existing Canvas discovery transactions; synthetic data only."""

import asyncio
import json
from copy import deepcopy
from datetime import UTC, datetime

import pytest
from psycopg import OperationalError
from test_source_connection_api import (
    CANVAS,
    ORIGIN,
    auth,
    bind,
    client_for,
    paired,
)
from test_source_connection_api import (
    canvas_store as canvas_store,
)

DISCOVERY = CANVAS + "/discovery"


def connected(client, who="alice", device="device-1"):
    linked = paired(client, who=who, device=device)
    assert bind(client, linked["ingestion_bearer"], subject=f"provider-{who}").status_code == 200
    return linked


def begin(client, linked, key="scan-1", subject="provider-alice"):
    return client.post(
        DISCOVERY + "/begin",
        headers=auth(linked["ingestion_bearer"]),
        json={
            "connection_id": linked["connection_id"],
            "generation": linked["generation"],
            "subject": subject,
            "scope_revision": linked.get("scope_revision", 0),
            "begin_key": key,
        },
    )


def envelope(linked, scan, ids=("101",), *, key="page-1", cursor=None, seen=None):
    return {
        "schema_version": 1,
        "connection_id": linked["connection_id"],
        "generation": linked["generation"],
        "scan_id": scan["scan_id"],
        "batch_key": key,
        "subject": "provider-alice",
        "resource": {"course_id": None, "kind": "courses"},
        "observed_at": datetime.now(UTC).isoformat(),
        "items": [
            {
                "provider_id": value,
                "provider_updated_at": None,
                "title": "Synthetic course",
                "reference": f"{ORIGIN}/courses/{value}",
                "content": "",
                "fields": {
                    "course_code": "SYN-101",
                    "timezone": "America/Denver",
                    "enrollment_state": "active",
                },
                "coverage": "complete",
                "missing": [],
            }
            for value in ids
        ],
        "coverage": {
            "state": "partial" if cursor else "complete",
            "reason": "more_pages" if cursor else None,
            "seen_count": len(ids) if seen is None else seen,
        },
        "next_cursor": cursor,
    }


def batch(client, linked, scan, body):
    return client.post(
        DISCOVERY + "/batch",
        headers=auth(linked["ingestion_bearer"]),
        json={
            "scan_id": scan["scan_id"],
            "generation": linked["generation"],
            "lease_token": scan["lease_token"],
            "batch_key": body["batch_key"],
            "expected_checkpoint": scan["checkpoint"],
            "envelope": body,
        },
    )


def resource(
    client, linked, scan, key="courses", outcome="complete", reason=None, finish_key="resource-1"
):
    return client.post(
        DISCOVERY + "/resource",
        headers=auth(linked["ingestion_bearer"]),
        json={
            "scan_id": scan["scan_id"],
            "generation": linked["generation"],
            "lease_token": scan["lease_token"],
            "resource_key": key,
            "finish_key": finish_key,
            "expected_checkpoint": scan["checkpoint"],
            "outcome": outcome,
            "reason": reason,
        },
    )


def finish(client, linked, scan):
    return client.post(
        DISCOVERY + "/finish",
        headers=auth(linked["ingestion_bearer"]),
        json={
            "scan_id": scan["scan_id"],
            "generation": linked["generation"],
            "lease_token": scan["lease_token"],
            "finish_key": "finish-1",
        },
    )


def scope(client, linked, who="alice", ids=("101",), kinds=("assignments",)):
    return client.post(
        CANVAS + "/scope",
        headers=auth(who),
        json={
            "connection_id": linked["connection_id"],
            "generation": linked["generation"],
            "mode": "explicit_set",
            "course_ids": list(ids),
            "resource_kinds": list(kinds),
        },
    )


def assert_private(response, status):
    assert response.status_code == status, response.text
    assert response.headers["cache-control"] == "no-store"


def test_discover_then_select_scope_and_finish_selected_resource_partial(canvas_store):
    client = client_for(canvas_store)
    linked = connected(client)
    opened = begin(client, linked)
    assert_private(opened, 200)
    scan = opened.json()
    receipt = batch(client, linked, scan, envelope(linked, scan))
    assert_private(receipt, 200)
    scan["checkpoint"] = receipt.json()["checkpoint"]
    assert_private(resource(client, linked, scan), 200)
    assert_private(finish(client, linked, scan), 200)
    selected = scope(client, linked)
    assert_private(selected, 200)
    current = selected.json()
    assert current["generation"] > linked["generation"]
    assert current["scope_revision"] == 1
    assert current["course_ids"] == ["101"]
    linked = {**linked, **current}
    scan = begin(client, linked, key="scan-2").json()
    receipt = batch(client, linked, scan, envelope(linked, scan))
    assert_private(receipt, 200)
    scan["checkpoint"] = receipt.json()["checkpoint"]
    assert_private(resource(client, linked, scan), 200)
    assert_private(finish(client, linked, scan), 409)
    assert_private(
        resource(
            client,
            linked,
            scan,
            "101/assignments",
            "unsupported",
            "unsupported_format",
            "unsupported-1",
        ),
        200,
    )
    done = finish(client, linked, scan)
    assert_private(done, 200)
    assert done.json()["coverage"] == "partial"


def test_replay_resume_replaces_lease_and_preserves_original_batch_receipt(canvas_store):
    client = client_for(canvas_store)
    linked = connected(client)
    opened = begin(client, linked)
    assert_private(opened, 200)
    scan = opened.json()
    assert begin(client, linked).json() == scan
    page = envelope(linked, scan, cursor="PRIVATE_CURSOR")
    first = batch(client, linked, scan, page)
    assert_private(first, 200)
    replay = batch(client, linked, scan, page)
    assert_private(replay, 200)
    assert replay.json()["replayed"] is True
    assert replay.json()["checkpoint"] == first.json()["checkpoint"]
    resumed = client.post(
        DISCOVERY + "/resume",
        headers=auth(linked["ingestion_bearer"]),
        json={
            "scan_id": scan["scan_id"],
            "generation": linked["generation"],
            "resume_key": "resume-1",
        },
    )
    assert_private(resumed, 200)
    new_scan = resumed.json()
    assert new_scan["lease_token"] != scan["lease_token"]
    assert new_scan["checkpoint"] == first.json()["checkpoint"]
    next_page = envelope(linked, scan, ("102",), key="page-2", seen=2)
    old_scan = {**scan, "checkpoint": first.json()["checkpoint"]}
    assert_private(batch(client, linked, old_scan, next_page), 409)
    assert_private(batch(client, linked, new_scan, next_page), 200)
    assert_private(batch(client, linked, scan, page), 200)
    changed = deepcopy(page)
    changed["items"][0]["title"] = "Changed"
    assert_private(batch(client, linked, scan, changed), 409)


@pytest.mark.parametrize(
    "kind", ["missing", "session", "other_owner", "revoked", "expired", "pending"]
)
def test_begin_requires_current_bound_ingestion_authority(canvas_store, kind):
    client = client_for(canvas_store)
    linked = paired(client) if kind == "pending" else connected(client)
    if kind == "revoked":
        client.post(
            CANVAS.rsplit("/canvas", 1)[0] + "/" + linked["connection_id"] + "/revoke",
            headers=auth(),
        )
    elif kind == "expired":
        with canvas_store.connection() as conn:
            conn.execute(
                "UPDATE wrytely_agent.source_connections "
                "SET credential_expires_at=clock_timestamp()-interval '1 second' WHERE id=%s",
                (linked["connection_id"],),
            )
    token = linked["ingestion_bearer"]
    if kind == "session":
        token = "alice"
    elif kind == "other_owner":
        token = connected(client, who="bob")["ingestion_bearer"]
    headers = {} if kind == "missing" else auth(token)
    response = client.post(
        DISCOVERY + "/begin",
        headers=headers,
        json={
            "connection_id": linked["connection_id"],
            "generation": linked["generation"],
            "subject": "provider-alice",
            "scope_revision": 0,
            "begin_key": "private-1",
        },
    )
    assert_private(response, 409 if kind == "pending" else 401)
    assert "provider-alice" not in response.text
    assert token not in response.text


def test_scope_requires_session_owner_and_generation(canvas_store):
    client = client_for(canvas_store)
    linked = connected(client)
    assert_private(scope(client, linked, who="bob", ids=()), 404)
    assert_private(scope(client, linked, who=linked["ingestion_bearer"], ids=()), 401)
    assert_private(scope(client, {**linked, "generation": 99}, ids=()), 409)
    assert_private(scope(client, linked), 409)  # undiscovered IDs cannot be selected


@pytest.mark.parametrize(
    "extra",
    [
        {"user_id": "PRIVATE"},
        {"actor": "PRIVATE"},
        {"generation": True},
        {"begin_key": "PRIVATE/INVALID"},
        {"connection_id": "not-a-uuid"},
    ],
)
def test_begin_rejects_undeclared_authority_or_invalid_controls(canvas_store, extra):
    client = client_for(canvas_store)
    linked = connected(client)
    response = client.post(
        DISCOVERY + "/begin",
        headers=auth(linked["ingestion_bearer"]),
        json={
            "connection_id": linked["connection_id"],
            "generation": linked["generation"],
            "subject": "provider-alice",
            "scope_revision": 0,
            "begin_key": "begin-1",
            **extra,
        },
    )
    assert_private(response, 422)
    assert response.json() == {"detail": "Invalid Canvas request"}


def test_large_valid_metadata_page_is_not_limited_to_control_body_size(canvas_store):
    client = client_for(canvas_store)
    linked = connected(client)
    opened = begin(client, linked)
    assert_private(opened, 200)
    scan = opened.json()
    page = envelope(linked, scan, tuple(str(n) for n in range(1, 51)))
    for item in page["items"]:
        item["title"] = "x" * 500
    assert_private(batch(client, linked, scan, page), 200)


def test_discovery_route_cannot_ingest_or_complete_academic_content(canvas_store):
    client = client_for(canvas_store)
    linked = connected(client)
    opened = begin(client, linked)
    assert_private(opened, 200)
    scan = opened.json()
    page = envelope(linked, scan)
    page["resource"] = {"course_id": "101", "kind": "assignments"}
    assert_private(batch(client, linked, scan, page), 422)
    assert_private(resource(client, linked, scan, "101/assignments"), 422)


@pytest.mark.parametrize(
    "path,size",
    [
        (DISCOVERY + "/begin", 16385),
        (DISCOVERY + "/batch", 2 * 1024 * 1024 + 1),
        (CANVAS + "/scope", 65537),
        (DISCOVERY + "/resource", 65537),
    ],
)
def test_streamed_route_caps_reject_overflow_without_content_length(canvas_store, path, size):
    client = client_for(canvas_store)
    response = client.post(
        path,
        content=iter([b"x" * (size // 2), b"x" * (size - size // 2)]),
        headers={"content-type": "application/json"},
    )
    assert_private(response, 413)


def test_query_storage_failure_and_validation_details_stay_private(
    canvas_store, monkeypatch, caplog
):
    client = client_for(canvas_store)
    linked = connected(client)
    response = client.post(
        DISCOVERY + "/begin?user_id=PRIVATE",
        headers=auth(linked["ingestion_bearer"]),
        json={
            "connection_id": linked["connection_id"],
            "generation": 1,
            "subject": "provider-alice",
            "scope_revision": 0,
            "begin_key": "begin-1",
        },
    )
    assert_private(response, 422)

    def broken(*args):
        raise OperationalError("PRIVATE_STORAGE")

    monkeypatch.setattr(canvas_store, "begin_sync", broken)
    response = begin(client, linked)
    assert_private(response, 503)
    assert "PRIVATE" not in response.text + caplog.text
    assert linked["ingestion_bearer"] not in caplog.text


@pytest.mark.parametrize("operation", ["resume", "batch", "resource", "finish"])
def test_other_account_cannot_read_or_change_scan_receipts(canvas_store, operation):
    client = client_for(canvas_store)
    linked = connected(client)
    scan = begin(client, linked).json()
    bob = connected(client, who="bob")
    forged = {**linked, "ingestion_bearer": bob["ingestion_bearer"]}
    if operation == "resume":
        response = client.post(
            DISCOVERY + "/resume",
            headers=auth(bob["ingestion_bearer"]),
            json={
                "scan_id": scan["scan_id"],
                "generation": linked["generation"],
                "resume_key": "resume-bob",
            },
        )
    elif operation == "batch":
        response = batch(client, forged, scan, envelope(linked, scan))
    elif operation == "resource":
        response = resource(client, forged, scan, outcome="partial", reason="login_required")
    else:
        response = finish(client, forged, scan)
    assert_private(response, 401)
    assert scan["lease_token"] not in response.text
    assert scan["scan_id"] not in response.text


def test_stale_checkpoint_and_expired_lease_are_controlled_conflicts(canvas_store):
    client = client_for(canvas_store)
    linked = connected(client)
    scan = begin(client, linked).json()
    stale = deepcopy(scan)
    stale["checkpoint"]["sequence"] += 1
    response = batch(client, linked, stale, envelope(linked, scan))
    assert_private(response, 409)
    assert response.json() == {"detail": {"code": "checkpoint_changed"}}
    with canvas_store.connection() as conn:
        conn.execute(
            "UPDATE wrytely_agent.canvas_scans "
            "SET lease_expires_at=clock_timestamp()-interval '1 second' WHERE id=%s",
            (scan["scan_id"],),
        )
    response = batch(client, linked, scan, envelope(linked, scan))
    assert_private(response, 409)
    assert response.json() == {"detail": {"code": "lease_expired"}}


def test_scope_change_fences_old_scan_and_missing_scope_is_private(canvas_store):
    client = client_for(canvas_store)
    linked = connected(client)
    scan = begin(client, linked).json()
    assert_private(scope(client, linked, ids=(), kinds=("assignments",)), 200)
    assert_private(batch(client, linked, scan, envelope(linked, scan)), 409)
    missing = scope(
        client, {**linked, "connection_id": "00000000-0000-4000-8000-000000000001"}, ids=()
    )
    nonowned = scope(client, linked, who="bob", ids=())
    assert_private(missing, 404)
    assert_private(nonowned, 404)
    assert missing.json() == nonowned.json() == {"detail": "Not found"}


def test_serialized_envelope_cap_remains_one_mib_and_rejects_atomically(canvas_store):
    client = client_for(canvas_store)
    linked = connected(client)
    scan = begin(client, linked).json()
    page = envelope(linked, scan, ("101", "102"))
    for item in page["items"]:
        item["coverage"] = "partial"
        item["missing"] = ["PRIVATE" + "x" * 530000]
    response = batch(client, linked, scan, page)
    assert_private(response, 422)
    assert response.json() == {"detail": "Invalid Canvas request"}
    with canvas_store.connection() as conn:
        assert (
            conn.execute("SELECT count(*) AS n FROM wrytely_agent.canvas_catalog").fetchone()["n"]
            == 0
        )
        assert (
            conn.execute(
                "SELECT checkpoint->>'sequence' AS sequence "
                "FROM wrytely_agent.canvas_scans WHERE id=%s",
                (scan["scan_id"],),
            ).fetchone()["sequence"]
            == "0"
        )


def test_batch_stream_cap_stops_at_overflow_without_reading_remainder():
    from fastapi import APIRouter, FastAPI, Request

    from app.canvas_sync_api import DiscoveryBatchRoute

    api = FastAPI()
    router = APIRouter(route_class=DiscoveryBatchRoute)

    @router.post("/bounded")
    async def endpoint(request: Request):
        return {"size": len(await request.body())}

    api.include_router(router)
    delivered, messages = [], []
    chunks = [b"x" * (1024 * 1024), b"x" * (1024 * 1024 + 1), b"unread"]

    async def receive():
        index = len(delivered)
        delivered.append(index)
        return {"type": "http.request", "body": chunks[index], "more_body": True}

    async def send(message):
        messages.append(message)

    request_scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/bounded",
        "root_path": "",
        "query_string": b"",
        "headers": [(b"content-type", b"application/json"), (b"content-length", b"1")],
        "server": ("test", 80),
        "client": ("test", 1234),
    }
    asyncio.run(api(request_scope, receive, send))
    assert delivered == [0, 1]
    assert messages[0]["status"] == 413
    assert (b"cache-control", b"no-store") in messages[0]["headers"]


def test_full_thousand_course_selection_fits_the_scope_route(canvas_store):
    client = client_for(canvas_store)
    linked = connected(client)
    scan = begin(client, linked).json()
    ids = [str(10000000000000000000 + n) for n in range(1000)]
    for offset in range(0, 1000, 50):
        page = envelope(
            linked,
            scan,
            ids[offset : offset + 50],
            key=f"page-{offset}",
            cursor=f"cursor-{offset}" if offset < 950 else None,
            seen=offset + 50,
        )
        response = batch(client, linked, scan, page)
        assert_private(response, 200)
        scan["checkpoint"] = response.json()["checkpoint"]
    assert_private(resource(client, linked, scan), 200)
    assert_private(finish(client, linked, scan), 200)
    assert len(json.dumps(ids)) > 16384
    response = scope(client, linked, ids=ids)
    assert_private(response, 200)
    assert set(response.json()["course_ids"]) == set(ids)


def test_maximum_encoded_checkpoint_fits_resource_receipt_route(canvas_store):
    client = client_for(canvas_store)
    linked = connected(client)
    scan = begin(client, linked).json()
    response = batch(client, linked, scan, envelope(linked, scan, cursor="🧪" * 4000))
    assert_private(response, 200)
    scan["checkpoint"] = response.json()["checkpoint"]
    body = {
        "scan_id": scan["scan_id"],
        "generation": linked["generation"],
        "lease_token": scan["lease_token"],
        "resource_key": "courses",
        "finish_key": "partial-1",
        "expected_checkpoint": scan["checkpoint"],
        "outcome": "partial",
        "reason": "provider_unavailable",
    }
    encoded = json.dumps(body)
    assert 16384 < len(encoded) < 65536
    response = client.post(
        DISCOVERY + "/resource",
        headers={**auth(linked["ingestion_bearer"]), "content-type": "application/json"},
        content=encoded,
    )
    assert_private(response, 200)


def test_disabled_sync_does_not_begin_a_scan(canvas_store):
    client = client_for(canvas_store)
    linked = connected(client)
    response = begin(client_for(canvas_store, enabled=False), linked)
    assert_private(response, 503)
    with canvas_store.connection() as conn:
        assert (
            conn.execute("SELECT count(*) AS n FROM wrytely_agent.canvas_scans").fetchone()["n"]
            == 0
        )


def test_unknown_future_conflict_is_redacted(canvas_store, monkeypatch):
    from shared.canvas_sync import CanvasSyncConflict

    client = client_for(canvas_store)
    linked = connected(client)

    def broken(*args):
        raise CanvasSyncConflict("PRIVATE_FUTURE_DETAIL")

    monkeypatch.setattr(canvas_store, "begin_sync", broken)
    response = begin(client, linked)
    assert_private(response, 409)
    assert response.json() == {"detail": {"code": "state_changed"}}
