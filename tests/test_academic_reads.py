import json
from contextlib import contextmanager
from uuid import uuid4

import pytest
from test_academic_memory import observation
from test_artifacts import assessment, prepare
from test_worker import ScriptedModel

from runtime.verification import verify_artifact
from shared.config import Settings
from shared.db import Store


def test_source_projections_are_current_private_bounded_and_json_safe(store, alice):
    store.provision("user_bob")
    other = store.observe_source("user_bob", observation())
    first = store.observe_source("user_alice", observation(age=2))
    latest = store.observe_source("user_alice", observation("v2", content="Current evidence"))
    rows = store.source_snapshots("user_alice")
    assert len(rows) == 1
    assert rows[0]["source_id"] == str(first["source_id"])
    assert rows[0]["version_id"] == str(latest["id"])
    assert set(rows[0]) == {
        "source_id",
        "version_id",
        "title",
        "reference",
        "coverage",
        "retrieved_at",
        "external_revision",
    }
    detail = store.source_snapshot("user_alice", str(first["source_id"]))
    assert detail == rows[0] | {"content": "Current evidence"}
    json.dumps(detail)
    assert store.source_snapshot("user_alice", other["source_id"]) is None
    assert store.source_snapshot("user_alice", uuid4()) is None
    assert store.source_snapshots("missing-user") == []
    for i in range(52):
        store.observe_source("user_alice", observation(key=f"bounded:{i}"))
    page = store.source_snapshots("user_alice")
    assert len(page) == 50
    assert page == store.source_snapshots("user_alice")
    assert page == sorted(page, key=lambda x: (x["retrieved_at"], x["source_id"]), reverse=True)


def test_artifact_reads_project_latest_check_and_staleness_without_internal_state(store, alice):
    lease, artifact, policy, rubric, source, draft = prepare(store, alice)
    store.provision("user_bob")
    duty_id = artifact["responsibility_id"]
    before = store.artifact_review("user_alice", artifact["id"])
    assert before["latest_check"] is None
    assert before["artifact"]["state"] == "review"
    assert set(before["artifact"]) == {
        "id",
        "responsibility_id",
        "task_id",
        "memory_revision",
        "draft",
        "state",
        "created_at",
        "stale",
    }
    failed = verify_artifact(
        store,
        ScriptedModel([assessment(claim_support=["uncertain"])]),
        Settings(),
        lease,
        artifact["id"],
        policy=policy,
        rubric=rubric,
    )
    assert store.artifact_review("user_alice", artifact["id"])["latest_check"] == failed
    passed = verify_artifact(
        store,
        ScriptedModel([assessment()]),
        Settings(),
        lease,
        artifact["id"],
        policy=policy,
        rubric=rubric,
    )
    result = Store(store._url).artifact_review("user_alice", str(artifact["id"]))
    assert result["latest_check"] == passed
    assert result["artifact"]["draft"] == draft.model_dump(mode="json")
    assert not result["artifact"]["stale"]
    json.dumps(result)
    assert store.artifact_review("user_bob", artifact["id"]) is None
    assert store.responsibility_artifacts("user_bob", duty_id) is None
    assert store.responsibility_artifacts("user_alice", uuid4()) is None
    summaries = store.responsibility_artifacts("user_alice", duty_id)
    assert summaries == [
        {
            "id": str(artifact["id"]),
            "task_id": str(lease.task_id),
            "title": "Review draft",
            "state": "ready",
            "stale": False,
            "created_at": artifact["created_at"].isoformat(),
        }
    ]
    store.observe_source("user_alice", observation("v2", key="rubric", content="Changed evidence"))
    assert store.artifact_review("user_alice", artifact["id"])["artifact"]["stale"]
    assert store.responsibility_artifacts("user_alice", duty_id)[0]["stale"]


def test_artifact_list_is_bounded_stable_and_distinguishes_empty_from_not_owned(store, alice):
    lease, artifact, _, _, _, draft = prepare(store, alice)
    empty = store.create_responsibility("user_alice", "Empty", "empty")
    assert store.responsibility_artifacts("user_alice", empty["id"]) == []
    for i in range(52):
        store.save_draft(lease, draft, f"revision:{i}")
    rows = store.responsibility_artifacts("user_alice", artifact["responsibility_id"])
    assert len(rows) == 50
    assert rows == store.responsibility_artifacts("user_alice", artifact["responsibility_id"])
    assert rows == sorted(rows, key=lambda x: (x["created_at"], x["id"]), reverse=True)


def test_storage_failures_propagate_instead_of_empty_reads():
    class BrokenStore(Store):
        @contextmanager
        def connection(self):
            raise RuntimeError("Storage unavailable")
            yield

    store = BrokenStore("unused")
    calls = [
        lambda: store.source_snapshots("user"),
        lambda: store.source_snapshot("user", uuid4()),
        lambda: store.responsibility_artifacts("user", uuid4()),
        lambda: store.artifact_review("user", uuid4()),
    ]
    for call in calls:
        with pytest.raises(RuntimeError, match="Storage unavailable"):
            call()
