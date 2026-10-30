from concurrent.futures import ThreadPoolExecutor
from threading import Event
from uuid import uuid4

import pytest
from test_academic_memory import observation

from shared.db import QueueFull, RequestConflict, Store


def sources(store, count=2, user="user_alice"):
    return [store.observe_source(user, observation(key=f"source:{i}")) for i in range(count)]


def create(store, rows, **kwargs):
    return store.create_bound_responsibility(
        "user_alice",
        "Analyze sources",
        "bound",
        source_ids=[r["source_id"] for r in rows],
        **kwargs,
    )


def test_first_claim_has_all_bound_sources_and_canonical_replay_keeps_progress(store, alice):
    rows = sources(store)
    duty = create(store, rows)
    lease = store.claim()
    context = store.context(lease)
    assert {s["version_id"] for s in context["academic_memory"]["sources"]} == {
        row["id"] for row in rows
    }
    assert context["responsibility"]["memory_revision"] == duty["memory_revision"]
    assert create(Store(store._url), rows[::-1])["id"] == duty["id"]
    with store.connection() as conn:
        assert conn.execute("SELECT count(*) AS n FROM wrytely_agent.tasks").fetchone()["n"] == 1
        assert not conn.execute("SELECT 1 FROM wrytely_agent.drafting_requests").fetchall()
    # Later source changes do not mutate the original request's identity or reset it.
    store.observe_source("user_alice", observation("v2", key="source:0"))
    replay = create(store, rows)
    assert replay["id"] == duty["id"]
    assert replay["status"] == "blocked"
    with pytest.raises(RequestConflict):
        create(store, rows[:1])
    with pytest.raises(RequestConflict):
        create(store, rows, max_steps=3)


@pytest.mark.parametrize("bad", ["missing", "other", "malformed"])
def test_invalid_source_is_indistinguishable_and_leaves_no_duty_or_task(store, alice, bad):
    rows = sources(store, 1)
    store.provision("user_bob")
    source_id = uuid4()
    if bad == "other":
        source_id = sources(store, 1, "user_bob")[0]["source_id"]
    if bad == "malformed":
        source_id = "not-a-uuid"
    with pytest.raises(LookupError, match="^Source not found$"):
        store.create_bound_responsibility(
            "user_alice", "Analyze", "bad", source_ids=[rows[0]["source_id"], source_id]
        )
    assert store.responsibilities("user_alice") == []
    assert store.tasks("user_alice") == []


@pytest.mark.parametrize("ids", [[], [uuid4()] * 2, [uuid4() for _ in range(9)]])
def test_source_count_and_duplicates_rejected(store, alice, ids):
    with pytest.raises(ValueError):
        store.create_bound_responsibility("user_alice", "Analyze", "bad", source_ids=ids)


def test_concurrent_same_request_creates_one_fully_bound_plan(store, alice):
    rows = sources(store)
    with ThreadPoolExecutor(max_workers=4) as pool:
        duties = list(pool.map(lambda _: create(Store(store._url), rows), range(4)))
    assert len({r["id"] for r in duties}) == 1
    assert len(store.tasks("user_alice")) == 1


def test_worker_cannot_claim_partial_setup_and_failure_rolls_back(store, alice):
    rows = sources(store)
    entered, release = Event(), Event()

    class HeldStore(Store):
        def _responsibility_task(self, conn, *args, **kwargs):
            entered.set()
            assert release.wait(5)
            return super()._responsibility_task(conn, *args, **kwargs)

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(create, HeldStore(store._url), rows)
        try:
            assert entered.wait(5)
            assert store.claim() is None
            assert store.responsibilities("user_alice") == []
        finally:
            release.set()
        duty = future.result()
    assert store.context(store.claim())["responsibility"]["id"] == duty["id"]

    class FailingStore(Store):
        def _responsibility_task(self, conn, *args, **kwargs):
            super()._responsibility_task(conn, *args, **kwargs)
            raise RuntimeError("synthetic rollback")

    with pytest.raises(RuntimeError, match="rollback"):
        FailingStore(store._url).create_bound_responsibility(
            "user_alice", "Other", "rollback", source_ids=[rows[0]["source_id"]]
        )
    assert len(store.responsibilities("user_alice")) == 1
    assert len(store.tasks("user_alice")) == 1


def test_pause_capacity_and_legacy_key_do_not_bypass_setup(store, alice):
    rows = sources(store)
    store.set_paused("user_alice", True)
    duty = create(store, rows)
    assert store.claim() is None
    assert create(store, rows, pending_limit=1)["id"] == duty["id"]
    with pytest.raises(QueueFull):
        store.create_bound_responsibility(
            "user_alice", "Other", "capacity", source_ids=[rows[0]["source_id"]], pending_limit=1
        )
    store.create_responsibility("user_alice", "Legacy", "legacy")
    with pytest.raises(RequestConflict):
        store.create_bound_responsibility(
            "user_alice", "Legacy", "legacy", source_ids=[rows[0]["source_id"]]
        )


def test_source_update_serializes_with_setup_and_invalidates_after_commit(store, alice):
    rows = sources(store, 1)
    entered, release, updating = Event(), Event(), Event()

    class HeldStore(Store):
        def _responsibility_task(self, conn, *args, **kwargs):
            entered.set()
            assert release.wait(5)
            return super()._responsibility_task(conn, *args, **kwargs)

    def update():
        updating.set()
        return Store(store._url).observe_source(
            "user_alice", observation("v2", key="source:0", content="Changed requirement")
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        setup = pool.submit(create, HeldStore(store._url), rows)
        try:
            assert entered.wait(5)
            changed = pool.submit(update)
            assert updating.wait(5)
            assert not changed.done()
        finally:
            release.set()
        duty = setup.result()
        changed.result()
    saved = store.responsibilities("user_alice")[0]
    assert saved["id"] == duty["id"]
    assert (saved["status"], saved["status_reason"]) == ("blocked", "source_changed")
    assert store.tasks("user_alice")[0]["status"] == "blocked"
    assert store.claim() is None
