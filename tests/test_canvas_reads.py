import hashlib
from uuid import uuid4

import pytest
import test_canvas_evidence as evidence
import test_canvas_sync as sync
from test_canvas_sync import device as device
from test_planner import plan
from test_worker import ScriptedModel

from runtime.worker import run_once
from shared.canvas_reads import SourceRefreshRequired
from shared.config import Settings
from shared.db import LeaseLost


def collected(device, count=1, text="A📚B"):
    scan = evidence.prepare(device)
    items = []
    for i in range(count):
        item = evidence.assignment()
        item["provider_id"] = str(17 + i)
        item["content"] = text
        items.append(item)
    receipt = evidence.upload(device, scan, evidence.body(device, scan, items))
    evidence.close(device, scan, receipt)
    return evidence.rows(device, "canvas_evidence_objects")


def listing(device, **kwargs):
    return device[0].list_canvas_evidence(
        "user_alice", connection_id=device[1]["connection_id"], **kwargs
    )


def test_owned_short_text_reader_is_private_and_does_not_promote_sources(device):
    obj = collected(device)[0]
    page = listing(device)
    item = page["sources"][0]
    assert item["freshness"]["usable"]
    assert item["document_version_id"] is None
    assert "content" not in item and "fields" not in item and "reference" not in item
    read = device[0].read_canvas_evidence("user_alice", obj["id"])
    assert read["section"] == dict(text="A📚B", offset=0, next_offset=None, total_characters=3)
    assert read["reference"] == "canvas-object:101:assignment:17"
    assert read["fields"]["points_possible"] == "20"
    assert device[0].source_snapshots("user_alice") == []
    for private in ["ingestion_bearer", "provider_subject", "private_payload"]:
        assert private not in read


def test_paging_pins_immutable_observation_and_counts_code_points(device):
    obj = collected(device)[0]
    db = device[0]
    first = db.read_canvas_evidence("user_alice", obj["id"], limit=1)
    assert first["section"]["text"] == "A" and first["section"]["next_offset"] == 1
    with pytest.raises(ValueError, match="Pinned"):
        db.read_canvas_evidence("user_alice", obj["id"], offset=1)
    scan = evidence.next_scan(device, "changed")
    item = evidence.assignment()
    item["content"] = "New instructions"
    receipt = evidence.upload(device, scan, evidence.body(device, scan, [item]))
    evidence.close(device, scan, receipt)
    rest = db.read_canvas_evidence(
        "user_alice", obj["id"], observation_id=first["observation_id"], offset=1
    )
    assert rest["section"]["text"] == "📚B"
    assert rest["historical"] and not rest["freshness"]["usable"]
    assert rest["version_id"] == first["version_id"]
    assert rest["latest_version_id"] != rest["version_id"]
    end = db.read_canvas_evidence(
        "user_alice", obj["id"], observation_id=first["observation_id"], offset=3
    )
    assert end["section"]["text"] == "" and end["section"]["next_offset"] is None


def test_cross_account_and_wrong_object_observation_have_generic_misses(device):
    objs = collected(device, 2)
    db = device[0]
    db.provision("user_bob")
    for who, oid in [("user_bob", objs[0]["id"]), ("user_alice", uuid4())]:
        with pytest.raises(LookupError, match="Not found"):
            db.read_canvas_evidence(who, oid)
    with pytest.raises(LookupError):
        db.list_canvas_evidence("user_bob", connection_id=device[1]["connection_id"])
    with pytest.raises(LookupError):
        db.read_canvas_evidence(
            "user_alice", objs[0]["id"], observation_id=objs[1]["latest_observation_id"]
        )


@pytest.mark.parametrize("change", ["revoke", "scope", "expiry"])
def test_control_change_fences_body_but_keeps_owned_metadata(device, change):
    obj = collected(device)[0]
    db = device[0]
    if change == "revoke":
        db.rotate_or_revoke("user_alice", device[1]["connection_id"])
    elif change == "scope":
        sync.set_scope(device, [], kinds=[])
    else:
        with db.connection() as conn:
            conn.execute(
                "UPDATE wrytely_agent.source_connections "
                "SET credential_expires_at=clock_timestamp()-interval '1 second'"
            )
    assert len(listing(device)["sources"]) == 1
    with pytest.raises(SourceRefreshRequired, match="source_refresh_required"):
        db.read_canvas_evidence("user_alice", obj["id"])


def test_new_failed_resource_attempt_cannot_reuse_old_complete_freshness(device):
    obj = collected(device)[0]
    assert listing(device)["sources"][0]["freshness"]["usable"]
    scan = evidence.next_scan(device, "failed-attempt")
    sync.finish_resource(
        device,
        scan,
        key="101/assignments",
        finish_key="failed",
        outcome="partial",
        reason="provider_unavailable",
    )
    read = device[0].read_canvas_evidence("user_alice", obj["id"])
    assert read["resource_coverage"] == "partial"
    assert not read["freshness"]["usable"]
    assert read["section"]["text"] == "A📚B"


def test_partial_current_evidence_never_falls_back_to_old_complete_version(device):
    obj = collected(device)[0]
    scan = evidence.next_scan(device, "partial")
    value = evidence.assignment()
    value.update(
        content="New partial content", coverage="partial", missing=["linked_content_unread"]
    )
    receipt = evidence.upload(device, scan, evidence.body(device, scan, [value]))
    evidence.close(device, scan, receipt, partial=True)
    read = device[0].read_canvas_evidence("user_alice", obj["id"])
    assert read["section"]["text"] == "New partial content"
    assert read["version_id"] != str(obj["complete_version_id"])
    assert not read["freshness"]["usable"]


def test_list_cursor_is_opaque_owner_filter_generation_bound_and_expires(device):
    collected(device, 3)
    db = device[0]
    page = listing(device, limit=1)
    token = page["next_cursor"]
    assert len(token) == 32
    second = listing(device, limit=1, cursor=token)
    assert page["sources"][0]["object_id"] != second["sources"][0]["object_id"]
    with db.connection() as conn:
        row = conn.execute(
            "SELECT * FROM wrytely_agent.canvas_read_cursors WHERE token_hash=%s",
            (hashlib.sha256(token.encode()).hexdigest(),),
        ).fetchone()
        assert row and token not in str(row)
    for kwargs in [dict(cursor="bad"), dict(cursor="A" * 32), dict(cursor=token, course_id="101")]:
        with pytest.raises(ValueError, match="cursor"):
            listing(device, **kwargs)
    db.provision("user_bob")
    code = db.create_pairing("user_bob", sync.ORIGIN)["code"]
    other = db.redeem_pairing(code, "bob-device")
    with pytest.raises(ValueError):
        db.list_canvas_evidence("user_bob", connection_id=other["connection_id"], cursor=token)
    with db.connection() as conn:
        conn.execute(
            "UPDATE wrytely_agent.canvas_read_cursors "
            "SET expires_at=clock_timestamp()-interval '1 second'"
        )
    with pytest.raises(ValueError):
        listing(device, cursor=token)


def test_generation_change_invalidates_cursor(device):
    collected(device, 2)
    token = listing(device, limit=1)["next_cursor"]
    sync.set_scope(device, [], kinds=[])
    with pytest.raises(ValueError):
        listing(device, cursor=token)


@pytest.mark.parametrize("limit", [0, True, 51, "2"])
def test_invalid_list_limits_reject(device, limit):
    with pytest.raises(ValueError):
        listing(device, limit=limit)


@pytest.mark.parametrize(
    "kwargs",
    [
        dict(limit=0),
        dict(limit=12001),
        dict(offset=-1),
        dict(offset=True),
        dict(offset=4, observation_id=str(uuid4())),
    ],
)
def test_invalid_body_bounds_or_observation_reject(device, kwargs):
    obj = collected(device)[0]
    with pytest.raises((ValueError, LookupError)):
        device[0].read_canvas_evidence("user_alice", obj["id"], **kwargs)


def test_expired_or_unknown_times_never_grant_freshness(device):
    obj = collected(device)[0]
    with device[0].connection() as conn:
        conn.execute(
            "UPDATE wrytely_agent.canvas_evidence_observations "
            "SET observed_at=clock_timestamp()-interval '2 days' WHERE id=%s",
            (obj["latest_observation_id"],),
        )
    assert not device[0].read_canvas_evidence("user_alice", obj["id"])["freshness"]["usable"]


def test_task_readers_restrict_to_bound_sources_and_pause_fences(device):
    objs = collected(device, 2)
    db = device[0]
    user_cursor = listing(device, limit=1)["next_cursor"]
    duty = db.create_responsibility("user_alice", "Inspect one source", "read-scope")
    db.bind_source("user_alice", duty["id"], objs[0]["source_id"])
    run_once(db, ScriptedModel([plan()]), Settings())
    lease = db.claim()
    assert lease is not None
    scoped = db.list_canvas_evidence_for_task(lease, connection_id=device[1]["connection_id"])
    assert [r["object_id"] for r in scoped["sources"]] == [str(objs[0]["id"])]
    with pytest.raises(ValueError):
        db.list_canvas_evidence_for_task(
            lease, connection_id=device[1]["connection_id"], cursor=user_cursor
        )
    assert db.read_canvas_evidence_for_task(lease, objs[0]["id"])["section"]["text"] == "A📚B"
    with pytest.raises(LookupError):
        db.read_canvas_evidence_for_task(lease, objs[1]["id"])
    with db.connection() as conn:
        conn.execute("UPDATE wrytely_agent.agents SET paused=true WHERE id=%s", (lease.agent_id,))
    with pytest.raises(LeaseLost):
        db.read_canvas_evidence_for_task(lease, objs[0]["id"])


def test_restricted_empty_observation_has_no_fake_text_version(device):
    obj = collected(device)[0]
    scan = evidence.next_scan(device, "restricted")
    value = evidence.assignment()
    value.update(content="", coverage="restricted", missing=["permission_denied"])
    receipt = evidence.upload(device, scan, evidence.body(device, scan, [value]))
    evidence.close(device, scan, receipt, partial=True)
    read = device[0].read_canvas_evidence("user_alice", obj["id"])
    assert read["version_id"] is None and read["latest_version_id"] is None
    assert read["section"]["text"] == ""
    assert not read["freshness"]["usable"]


def test_unknown_course_filter_and_invalid_identifiers_are_private(device):
    collected(device)
    with pytest.raises(LookupError):
        listing(device, course_id="999")
    with pytest.raises(ValueError):
        listing(device, course_id="not-a-course")
    for oid in ["bad", True]:
        with pytest.raises(LookupError):
            device[0].read_canvas_evidence("user_alice", oid)


def test_cursor_quota_is_bounded_and_expired_rows_are_reclaimed(device):
    collected(device, 2)
    token = listing(device, limit=1)["next_cursor"]
    with device[0].connection() as conn:
        conn.execute(
            "INSERT INTO wrytely_agent.canvas_read_cursors "
            "(token_hash,agent_id,connection_id,generation,anchor) "
            "SELECT 'synthetic-'||n,c.agent_id,c.connection_id,c.generation,c.anchor "
            "FROM wrytely_agent.canvas_read_cursors c CROSS JOIN generate_series(1,255) n "
            "WHERE c.token_hash=%s",
            (hashlib.sha256(token.encode()).hexdigest(),),
        )
    with pytest.raises(ValueError, match="cursor limit"):
        listing(device, limit=1)
    with device[0].connection() as conn:
        conn.execute(
            "UPDATE wrytely_agent.canvas_read_cursors "
            "SET expires_at=clock_timestamp()-interval '1 second'"
        )
    assert listing(device, limit=1)["next_cursor"]
    with device[0].connection() as conn:
        assert (
            conn.execute("SELECT count(*) AS n FROM wrytely_agent.canvas_read_cursors").fetchone()[
                "n"
            ]
            == 1
        )


def test_task_without_bound_sources_cannot_read_account_evidence(device):
    obj = collected(device)[0]
    db = device[0]
    db.enqueue("user_alice", "A separate reply task", "unbound")
    lease = db.claim()
    assert (
        db.list_canvas_evidence_for_task(lease, connection_id=device[1]["connection_id"])["sources"]
        == []
    )
    with pytest.raises(LookupError):
        db.read_canvas_evidence_for_task(lease, obj["id"])
    for course in ["101", "999"]:
        with pytest.raises(LookupError):
            db.list_canvas_evidence_for_task(
                lease, connection_id=device[1]["connection_id"], course_id=course
            )
    with db.connection() as conn:
        conn.execute(
            "UPDATE wrytely_agent.tasks "
            "SET lease_until=clock_timestamp()-interval '1 second' WHERE id=%s",
            (lease.task_id,),
        )
    with pytest.raises(LeaseLost):
        db.list_canvas_evidence_for_task(lease, connection_id=device[1]["connection_id"])


def test_lease_expiring_inside_read_cannot_pass_on_transaction_start_time(device, monkeypatch):
    obj = collected(device)[0]
    db = device[0]
    duty = db.create_responsibility("user_alice", "Inspect source", "expiry-race")
    db.bind_source("user_alice", duty["id"], obj["source_id"])
    run_once(db, ScriptedModel([plan()]), Settings())
    lease = db.claim()
    original = db._evidence_projection

    def expiring(conn, connection, row):
        result = original(conn, connection, row)
        conn.execute(
            "UPDATE wrytely_agent.tasks SET lease_until=clock_timestamp() WHERE id=%s",
            (lease.task_id,),
        )
        return result

    monkeypatch.setattr(db, "_evidence_projection", expiring)
    with pytest.raises(LeaseLost):
        db.read_canvas_evidence_for_task(lease, obj["id"])
