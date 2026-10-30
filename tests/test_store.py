from concurrent.futures import ThreadPoolExecutor

import pytest

from shared.db import LeaseLost, QueueFull, RequestConflict, Store


def expire(store, task_id):
    with store.connection() as conn:
        conn.execute(
            "UPDATE wrytely_agent.tasks SET lease_until=now()-interval '1 second' WHERE id=%s",
            (task_id,),
        )


def test_migration_repeat_is_safe(store):
    store.migrate()
    with store.connection() as conn:
        versions = conn.execute(
            "SELECT version FROM wrytely_agent.migrations ORDER BY version"
        ).fetchall()
        assert [row["version"] for row in versions] == [
            "001",
            "002",
            "003",
            "004",
            "005",
            "006",
            "007",
            "009",
        ]


def test_concurrent_provisioning_is_idempotent(store):
    with ThreadPoolExecutor(max_workers=5) as pool:
        agents = list(pool.map(store.provision, ["user_alice"] * 5))
    assert len({a["id"] for a in agents}) == 1


def test_messages_are_durable_idempotent_and_private(store, alice):
    store.provision("user_bob")
    first = store.enqueue("user_alice", "My private assignment", "key")
    assert store.enqueue("user_alice", "My private assignment", "key") == first
    restarted = Store(store._url)
    assert len(restarted.messages("user_alice")) == 1
    assert restarted.messages("user_bob") == []
    assert restarted.task("user_bob", first["task_id"]) is None
    with pytest.raises(RequestConflict):
        store.enqueue("user_alice", "Different assignment", "key")


def test_unprovisioned_user_cannot_enqueue(store):
    with pytest.raises(LookupError):
        store.enqueue("user_unknown", "Hello", "key")


def test_queue_limit_and_retry_of_existing_request(store, alice):
    store.enqueue("user_alice", "One", "one", limit=1)
    with pytest.raises(QueueFull):
        store.enqueue("user_alice", "Two", "two", limit=1)
    assert store.enqueue("user_alice", "One", "one", limit=1)


def test_concurrent_workers_claim_only_one_task_per_agent(store, alice):
    for i in range(4):
        store.enqueue("user_alice", f"Question {i}", str(i))
    with ThreadPoolExecutor(max_workers=5) as pool:
        leases = list(pool.map(lambda _: store.claim(), range(5)))
    assert len([lease for lease in leases if lease]) == 1


def test_different_students_make_progress_independently(store, alice):
    store.provision("user_bob")
    store.enqueue("user_alice", "Alice", "one")
    store.enqueue("user_bob", "Bob", "one")
    first, second = store.claim(), store.claim()
    assert first.agent_id != second.agent_id


def test_expired_attempt_cannot_write_or_complete(store, alice):
    store.enqueue("user_alice", "Question", "one")
    old = store.claim()
    expire(store, old.task_id)
    new = store.claim()
    assert new.task_id == old.task_id
    assert new.lease_token != old.lease_token
    for operation in [
        lambda: store.complete(old, "Wrong"),
        lambda: store.event(old, "event", {}),
        lambda: store.heartbeat(old),
        lambda: store.retry(old, "failed"),
    ]:
        with pytest.raises(LeaseLost):
            operation()
    store.complete(new, "Correct")
    assert [m["content"] for m in store.messages("user_alice")] == ["Question", "Correct"]


def test_crash_attempt_limit_blocks_instead_of_restarting_forever(store, alice):
    task = store.enqueue("user_alice", "Question", "one")
    for _ in range(3):
        lease = store.claim()
        expire(store, lease.task_id)
    assert store.claim() is None
    assert store.task("user_alice", task["task_id"])["status"] == "blocked"


def test_pause_blocks_current_attempt_and_new_claims(store, alice):
    store.enqueue("user_alice", "Question", "one")
    lease = store.claim()
    store.set_paused("user_alice", True)
    assert store.claim() is None
    with pytest.raises(LeaseLost):
        store.complete(lease, "Should not be delivered")
    store.set_paused("user_alice", False)
    with pytest.raises(LeaseLost):
        store.complete(lease, "Old worker cannot resume")
    resumed = store.claim()
    assert resumed.attempt > lease.attempt
    store.complete(resumed, "Resumed")


def test_retry_after_completion_cannot_duplicate_response(store, alice):
    store.enqueue("user_alice", "Question", "one")
    lease = store.claim()
    store.complete(lease, "Answer")
    with pytest.raises(LeaseLost):
        store.complete(lease, "Duplicate")
    assert store.claim() is None


def test_pause_final_claim_can_resume_with_new_fence(store, alice):
    task = store.enqueue("user_alice", "Question", "pause-final")
    old = store.claim(max_attempts=1)
    store.set_paused("user_alice", True)
    assert store.claim(max_attempts=1) is None
    store.set_paused("user_alice", False)
    expire(store, task["task_id"])
    resumed = store.claim(max_attempts=1)
    assert resumed is not None
    assert resumed.attempt > old.attempt
    assert resumed.lease_token != old.lease_token
    with pytest.raises(LeaseLost):
        store.complete(old, "Old worker cannot complete")
    store.complete(resumed, "Resumed work")
    assert store.task("user_alice", task["task_id"])["status"] == "done"


def test_resume_does_not_revive_pre_pause_lease(store, alice):
    store.enqueue("user_alice", "Question", "pause-revocation")
    old = store.claim()
    store.set_paused("user_alice", True)
    store.set_paused("user_alice", False)
    with pytest.raises(LeaseLost):
        store.complete(old, "Stale worker result")


def test_pause_interruptions_do_not_forgive_later_execution_failure(store, alice):
    task = store.enqueue("user_alice", "Question", "pause-then-fail")
    store.claim(max_attempts=1)
    store.set_paused("user_alice", True)
    store.set_paused("user_alice", True)
    store.set_paused("user_alice", False)
    expire(store, task["task_id"])
    resumed = store.claim(max_attempts=1)
    assert resumed is not None
    store.retry(resumed, "execution_failed", max_attempts=1)
    assert store.task("user_alice", task["task_id"])["status"] == "blocked"
    assert store.claim(max_attempts=1) is None


def test_expired_crash_is_not_reclassified_by_pause(store, alice):
    task = store.enqueue("user_alice", "Question", "expired-before-pause")
    lease = store.claim(max_attempts=1)
    expire(store, lease.task_id)
    store.set_paused("user_alice", True)
    store.set_paused("user_alice", False)
    assert store.claim(max_attempts=1) is None
    assert store.task("user_alice", task["task_id"])["status"] == "blocked"


def test_repeated_pause_preserves_monotonic_claims_and_prior_failure(store, alice):
    task = store.enqueue("user_alice", "Question", "pause-counts")
    first = store.claim(max_attempts=2)
    store.retry(first, "execution_failed", max_attempts=2)
    with store.connection() as conn:
        conn.execute(
            "UPDATE wrytely_agent.tasks SET available_at=now() WHERE id=%s", (first.task_id,)
        )
    previous = first
    for _ in range(3):
        current = store.claim(max_attempts=2)
        assert current.attempt > previous.attempt
        store.set_paused("user_alice", True)
        store.set_paused("user_alice", True)
        store.set_paused("user_alice", False)
        with pytest.raises(LeaseLost):
            store.complete(current, "Late result")
        previous = current
    final = store.claim(max_attempts=2)
    assert final.attempt == 5
    store.retry(final, "execution_failed", max_attempts=2)
    assert store.task("user_alice", task["task_id"])["status"] == "blocked"
    with store.connection() as conn:
        count = conn.execute(
            "SELECT count(*) AS n FROM wrytely_agent.episode_events "
            "WHERE task_id=%s AND kind='control_interrupted'",
            (final.task_id,),
        ).fetchone()["n"]
    assert count == 3
