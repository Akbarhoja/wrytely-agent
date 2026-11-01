"""M-owned HTTP acceptance of existing staged C2v1 evidence; synthetic data only."""

import asyncio
from copy import deepcopy

import httpx
import pytest
from psycopg import OperationalError
from test_canvas_sync_api import (
    assert_private,
    batch,
    begin,
    connected,
    envelope,
    finish,
    resource,
    scope,
)
from test_source_connection_api import CANVAS, ORIGIN, auth, client_for
from test_source_connection_api import canvas_store as canvas_store

ACADEMIC = CANVAS + "/academic"


def prepared(store, kinds=("assignments",)):
    client = client_for(store)
    linked = connected(client)
    scan = begin(client, linked).json()
    receipt = batch(client, linked, scan, envelope(linked, scan))
    assert_private(receipt, 200)
    scan["checkpoint"] = receipt.json()["checkpoint"]
    assert_private(resource(client, linked, scan), 200)
    assert_private(finish(client, linked, scan), 200)
    selected = scope(client, linked, kinds=kinds)
    assert_private(selected, 200)
    linked = {**linked, **selected.json()}
    scan = begin(client, linked, key="academic-scan").json()
    receipt = batch(client, linked, scan, envelope(linked, scan, key="discovery-again"))
    assert_private(receipt, 200)
    scan["checkpoint"] = receipt.json()["checkpoint"]
    assert_private(resource(client, linked, scan, finish_key="courses-again"), 200)
    return client, linked, scan


def item(kind="assignments"):
    fields = {
        "assignments": {
            "due_at": "2026-11-02T05:59:00Z",
            "unlock_at": None,
            "lock_at": None,
            "points_possible": "20",
            "submission_types": ["online_upload"],
            "rubric": [
                {"id": "r1", "description": "Explain reasoning", "points": "20", "ratings": []}
            ],
            "published": True,
        },
        "syllabus": {"page_id": None, "module_ids": [], "source_format": "html_text"},
        "pages": {"page_id": "17", "module_ids": [], "source_format": "html_text"},
        "announcements": {
            "author_role": "teacher",
            "posted_at": "2026-10-31T00:00:00Z",
            "announcement_id": "17",
        },
        "discussions": {
            "topic_id": "17",
            "parent_entry_id": None,
            "author_role": "teacher",
            "required_initial_post": False,
            "due_at": None,
        },
        "submissions": {
            "assignment_id": "17",
            "submitted_at": None,
            "workflow_state": "unsubmitted",
            "attempt": 0,
            "late": False,
            "missing": False,
        },
        "grades": {
            "assignment_id": "17",
            "score": None,
            "points_possible": "20",
            "grading_type": "points",
            "grade": None,
            "grade_basis": None,
        },
    }
    singular = {
        "assignments": "assignment",
        "syllabus": "syllabus",
        "pages": "page",
        "announcements": "announcement",
        "discussions": "discussion",
        "submissions": "submission",
        "grades": "grade",
    }[kind]
    return {
        "kind": singular,
        "provider_id": "17",
        "provider_updated_at": None,
        "title": "Synthetic academic item",
        "reference": f"{ORIGIN}/courses/101/{kind}/17",
        "content": "Synthetic instructions for a controlled fixture.",
        "fields": fields[kind],
        "coverage": "complete",
        "missing": [],
    }


def body(linked, scan, *, kind="assignments"):
    value = envelope(linked, scan, (), key="academic-page")
    value["resource"] = {"course_id": "101", "kind": kind}
    value["items"] = [item(kind)]
    value["coverage"]["seen_count"] = 1
    return {
        "scan_id": scan["scan_id"],
        "generation": linked["generation"],
        "lease_token": scan["lease_token"],
        "batch_key": value["batch_key"],
        "expected_checkpoint": deepcopy(scan["checkpoint"]),
        "envelope": value,
    }


def upload(client, linked, value, *, token=None, path=""):
    return client.post(
        ACADEMIC + "/batch" + path, headers=auth(token or linked["ingestion_bearer"]), json=value
    )


def close(client, linked, scan, *, kind="assignments", outcome="complete", reason=None):
    return client.post(
        ACADEMIC + "/resource",
        headers=auth(linked["ingestion_bearer"]),
        json={
            "scan_id": scan["scan_id"],
            "generation": linked["generation"],
            "lease_token": scan["lease_token"],
            "resource_key": "101/" + kind,
            "finish_key": "close-academic",
            "expected_checkpoint": scan["checkpoint"],
            "outcome": outcome,
            "reason": reason,
        },
    )


def count(store, table):
    assert table in {"source_versions", "canvas_evidence_observations", "canvas_evidence_events"}
    with store.connection() as conn:
        return conn.execute("SELECT count(*) AS n FROM wrytely_agent." + table).fetchone()["n"]


@pytest.mark.parametrize(
    "kind",
    ["assignments", "syllabus", "pages", "announcements", "discussions", "submissions", "grades"],
)
def test_supported_academic_kind_is_staged_and_can_finish(canvas_store, kind):
    client, linked, scan = prepared(canvas_store, (kind,))
    value = body(linked, scan, kind=kind)
    result = upload(client, linked, value)
    assert_private(result, 200)
    receipt = result.json()
    assert len(receipt["source_versions"]) == len(receipt["observations"]) == 1
    assert value["envelope"]["items"][0]["content"] not in result.text
    assert linked["ingestion_bearer"] not in result.text
    assert count(canvas_store, "source_versions") == 1
    with canvas_store.connection() as conn:
        assert (
            conn.execute("SELECT latest_version_id FROM wrytely_agent.academic_sources").fetchone()[
                "latest_version_id"
            ]
            is None
        )
    scan["checkpoint"] = receipt["checkpoint"]
    assert_private(close(client, linked, scan, kind=kind), 200)
    done = finish(client, linked, scan)
    assert_private(done, 200)
    assert done.json()["coverage"] == "complete"


def test_exact_replay_is_stable_and_changed_body_conflicts(canvas_store):
    client, linked, scan = prepared(canvas_store)
    value = body(linked, scan)
    first = upload(client, linked, value)
    assert_private(first, 200)
    with canvas_store.connection() as conn:
        checked = conn.execute(
            "SELECT last_successful_check_at FROM wrytely_agent.canvas_evidence_objects"
        ).fetchone()
    replay = upload(client, linked, value)
    assert_private(replay, 200)
    assert replay.json() == {**first.json(), "replayed": True}
    changed = deepcopy(value)
    changed["envelope"]["items"][0]["content"] += " Changed."
    assert_private(upload(client, linked, changed), 409)
    assert (
        count(canvas_store, "source_versions") == count(canvas_store, "canvas_evidence_events") == 1
    )
    assert count(canvas_store, "canvas_evidence_observations") == 1
    with canvas_store.connection() as conn:
        assert (
            conn.execute(
                "SELECT last_successful_check_at FROM wrytely_agent.canvas_evidence_objects"
            ).fetchone()
            == checked
        )


@pytest.mark.parametrize("token", ["alice", "bob", "other_owner", "missing"])
def test_academic_upload_requires_owned_ingestion_credential(canvas_store, token):
    client, linked, scan = prepared(canvas_store)
    value = body(linked, scan)
    if token == "other_owner":
        token = connected(client, who="bob")["ingestion_bearer"]
    if token == "missing":
        response = client.post(ACADEMIC + "/batch", json=value)
    else:
        response = upload(client, linked, value, token=token)
    assert_private(response, 401)
    assert count(canvas_store, "source_versions") == 0


@pytest.mark.parametrize("change", ["lease", "scope", "revoke"])
def test_academic_transaction_rechecks_controls(canvas_store, change):
    client, linked, scan = prepared(canvas_store)
    value = body(linked, scan)
    if change == "lease":
        with canvas_store.connection() as conn:
            conn.execute(
                "UPDATE wrytely_agent.canvas_scans "
                "SET lease_expires_at=clock_timestamp()-interval '1 second' WHERE id=%s",
                (scan["scan_id"],),
            )
    elif change == "scope":
        assert_private(scope(client, linked, kinds=("syllabus",)), 200)
    else:
        canvas_store.rotate_or_revoke("user_alice", linked["connection_id"])
    assert_private(upload(client, linked, value), 401 if change == "revoke" else 409)
    assert count(canvas_store, "source_versions") == 0


@pytest.mark.parametrize(
    "field,value",
    [
        ("schema_version", 2),
        ("schema_version", True),
        ("resource", {"course_id": "101", "kind": "files"}),
        ("resource", {"course_id": "101", "kind": "modules"}),
        ("user_id", "user_alice"),
    ],
)
def test_unsupported_schema_resource_and_posted_identity_are_rejected(canvas_store, field, value):
    client, linked, scan = prepared(canvas_store)
    payload = body(linked, scan)
    payload["envelope"][field] = value
    assert_private(upload(client, linked, payload), 422)
    assert count(canvas_store, "source_versions") == 0


@pytest.mark.parametrize(
    "field,value",
    [
        ("reference", "https://evil.example/courses/101/assignments/17"),
        ("reference", ORIGIN + "/courses/102/assignments/17"),
        ("reference", ORIGIN + "/courses/101/%2e%2e/assignments/17"),
        ("upload_id", "not-schema2"),
        ("title", "x" * 301),
        ("content", "x" * 24001),
    ],
)
def test_invalid_item_or_reference_never_writes(canvas_store, field, value):
    client, linked, scan = prepared(canvas_store)
    payload = body(linked, scan)
    payload["envelope"]["items"][0][field] = value
    assert_private(upload(client, linked, payload), 422)
    assert count(canvas_store, "canvas_evidence_observations") == 0


@pytest.mark.parametrize("field,raw", [("content", "\u0344" * 12001), ("title", "\u0344" * 151)])
def test_normalized_partial_blank_title_cannot_exceed_http_text_bound(canvas_store, field, raw):
    client, linked, scan = prepared(canvas_store)
    payload = body(linked, scan)
    entry = payload["envelope"]["items"][0]
    entry.update(title="", content="", coverage="partial", missing=["instructions_missing"])
    entry[field] = raw
    assert_private(upload(client, linked, payload), 422)
    assert count(canvas_store, "canvas_evidence_observations") == 0


@pytest.mark.parametrize("field,raw", [("content", "\u0344" * 12000), ("title", "\u0344" * 150)])
def test_exact_normalized_boundary_remains_accepted_without_clipping(canvas_store, field, raw):
    client, linked, scan = prepared(canvas_store)
    payload = body(linked, scan)
    entry = payload["envelope"]["items"][0]
    entry.update(title="", content="", coverage="partial", missing=["instructions_missing"])
    entry[field] = raw
    response = upload(client, linked, payload)
    assert_private(response, 200)
    assert count(canvas_store, "canvas_evidence_observations") == 1
    with canvas_store.connection() as conn:
        saved = conn.execute(
            "SELECT payload FROM wrytely_agent.canvas_evidence_observations"
        ).fetchone()["payload"]
        assert len(saved[field]) == (24000 if field == "content" else 300)


def test_store_envelope_cap_remains_one_mib_and_rolls_back_every_item(canvas_store):
    client, linked, scan = prepared(canvas_store)
    payload = body(linked, scan)
    payload["envelope"]["items"] = []
    for number in range(50):
        entry = item()
        entry.update(
            provider_id=str(number + 1),
            content="x" * 23000,
            reference=f"{ORIGIN}/courses/101/assignments/{number + 1}",
        )
        payload["envelope"]["items"].append(entry)
    payload["envelope"]["coverage"]["seen_count"] = 50
    assert_private(upload(client, linked, payload), 422)
    assert count(canvas_store, "source_versions") == 0
    assert count(canvas_store, "canvas_evidence_observations") == 0


def test_chunked_body_limit_stops_before_parsing_or_writing(canvas_store):
    client, linked, _ = prepared(canvas_store)
    consumed = []

    async def run():
        async def chunks():
            for number, data in enumerate([b"x" * 1048576, b"x" * 1048576, b"x", b"unread"]):
                consumed.append(number)
                yield data

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=client.app), base_url="http://test"
        ) as transport:
            return await transport.post(
                ACADEMIC + "/batch",
                headers={**auth(linked["ingestion_bearer"]), "Content-Type": "application/json"},
                content=chunks(),
            )

    assert_private(asyncio.run(run()), 413)
    assert consumed == [0, 1, 2]
    assert count(canvas_store, "source_versions") == 0


@pytest.mark.parametrize("token", ["alice", "other_owner"])
def test_resource_terminalization_requires_same_ingestion_owner(canvas_store, token):
    client, linked, scan = prepared(canvas_store)
    if token == "other_owner":
        token = connected(client, who="bob")["ingestion_bearer"]
    assert_private(close(client, {**linked, "ingestion_bearer": token}, scan), 401)


def test_partial_observation_does_not_create_fake_version_or_complete_resource(canvas_store):
    client, linked, scan = prepared(canvas_store)
    payload = body(linked, scan)
    payload["envelope"]["items"][0].update(
        content="", coverage="partial", missing=["instructions_missing"]
    )
    payload["envelope"]["coverage"] = {
        "state": "partial",
        "reason": "extraction_failed",
        "seen_count": 1,
    }
    response = upload(client, linked, payload)
    assert_private(response, 200)
    assert response.json()["source_versions"] == []
    assert count(canvas_store, "source_versions") == 0
    scan["checkpoint"] = response.json()["checkpoint"]
    assert_private(close(client, linked, scan), 409)
    assert_private(close(client, linked, scan, outcome="partial", reason="extraction_failed"), 200)
    assert finish(client, linked, scan).json()["coverage"] == "partial"


def test_query_body_cap_disabled_config_and_storage_failure_are_private(
    canvas_store, monkeypatch, caplog
):
    client, linked, scan = prepared(canvas_store)
    payload = body(linked, scan)
    assert_private(upload(client, linked, payload, path="?unknown=1"), 422)
    large = client.post(
        ACADEMIC + "/batch",
        headers={**auth(linked["ingestion_bearer"]), "Content-Type": "application/json"},
        content=b" " * (2 * 1024 * 1024 + 1),
    )
    assert_private(large, 413)
    assert_private(upload(client_for(canvas_store, enabled=False), linked, payload), 503)

    def broken(*args):
        raise OperationalError("PRIVATE_STORAGE")

    monkeypatch.setattr(canvas_store, "commit_sync_batch", broken)
    response = upload(client, linked, payload)
    assert_private(response, 503)
    assert "PRIVATE_STORAGE" not in response.text + caplog.text


@pytest.mark.parametrize("kind", ["files", "modules", "courses"])
def test_academic_resource_cannot_close_unsupported_kind(canvas_store, kind):
    client, linked, scan = prepared(canvas_store)
    assert_private(close(client, linked, scan, kind=kind), 422)
