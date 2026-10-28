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
        assert [row["version"] for row in versions] == ["001", "002", "003", "004", "005"]


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
    store.complete(lease, "Resumed")


def test_retry_after_completion_cannot_duplicate_response(store, alice):
    store.enqueue("user_alice", "Question", "one")
    lease = store.claim()
    store.complete(lease, "Answer")
    with pytest.raises(LeaseLost):
        store.complete(lease, "Duplicate")
    assert store.claim() is None
