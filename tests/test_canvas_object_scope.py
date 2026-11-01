"""Explicit published-object scope without fake source versions or blanket task access."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
import test_canvas_evidence as evidence
import test_canvas_sync as sync
from test_canvas_document_publication import page, ready
from test_canvas_sync import device as device
from test_worker import ScriptedModel

from contracts.models import PlannerDecision
from runtime.worker import run_once
from shared.canvas_reads import SourceRefreshRequired
from shared.config import Settings
from shared.db import LeaseLost, QueueFull, RequestConflict


def published(device):
    scan = evidence.prepare(device)
    body, upload, _ = ready(device, scan, key="obj")
    receipt = evidence.upload(device, scan, page(device, scan, body, upload))
    evidence.close(device, scan, receipt)
    return receipt["observations"][0]


def published_pair(device):
    from test_canvas_document_uploads import begin, begin_body, finish, finish_body, put, put_body

    scan = evidence.prepare(device)
    items = []
    for provider in ("101", "102"):
        body = begin_body(device, scan, key="begin-" + provider)
        body["owner_object"]["provider_id"] = provider
        upload = begin(device, body)
        put(device, put_body(body, upload["upload_id"], key="put-" + provider))
        finish(device, finish_body(body, upload["upload_id"], key="finish-" + provider))
        item = page(device, scan, body, upload)["items"][0]
        item["reference"] = sync.ORIGIN + "/courses/101/assignments/" + provider
        items.append(item)
    envelope = page(device, scan, body, upload)
    envelope["items"] = items
    envelope["coverage"]["seen_count"] = 2
    receipt = evidence.upload(device, scan, envelope)
    evidence.close(device, scan, receipt)
    return receipt["observations"]


def create(device, objects, *, key="canvas-duty", user="user_alice", **kwargs):
    return device[0].create_canvas_draft_responsibility(
        user,
        "Prepare a private review draft",
        key,
        object_ids=[o["object_id"] for o in objects],
        **kwargs,
    )


def pinned(device, lease, observed):
    return device[0].read_canvas_document_sections_for_task(
        lease,
        observed["object_id"],
        observation_id=observed["observation_id"],
        document_version_id=observed["document_version_id"],
    )


def counts(db):
    with db.connection() as conn:
        return {
            table: conn.execute("SELECT count(*) AS n FROM wrytely_agent." + table).fetchone()["n"]
            for table in (
                "responsibilities",
                "tasks",
                "messages",
                "private_draft_intents",
                "responsibility_canvas_objects",
                "episode_events",
                "source_versions",
            )
        }


def test_document_only_delegation_binds_one_atomic_intent_and_scoped_task(device):
    observed = published(device)
    db = device[0]
    duty = create(device, [observed])
    lease = db.claim()
    assert lease and lease.agent_id == duty["agent_id"]
    result = pinned(device, lease, observed)
    assert result["sections"][0]["text"] == "Café\n📚" and result["freshness"]["usable"]
    listed = db.list_canvas_evidence_for_task(lease, connection_id=device[1]["connection_id"])
    assert [s["object_id"] for s in listed["sources"]] == [observed["object_id"]]
    state = counts(db)
    assert state["responsibilities"] == state["tasks"] == state["private_draft_intents"] == 1
    assert state["responsibility_canvas_objects"] == 1 and state["source_versions"] == 0
    assert db.draft_intent(lease)["canvas_objects_bound"] is True


def test_published_document_has_no_task_access_without_explicit_object_binding(device):
    observed = published(device)
    db = device[0]
    db.create_responsibility("user_alice", "Unbound duty", "unbound")
    lease = db.claim()
    with pytest.raises(LookupError):
        pinned(device, lease, observed)


def test_other_account_cannot_create_scope_or_read_the_bound_document(device):
    observed = published(device)
    db = device[0]
    db.provision("user_bob")
    before = counts(db)
    with pytest.raises(LookupError, match="Not found"):
        create(device, [observed], user="user_bob")
    assert counts(db) == before
    create(device, [observed])
    alice = db.claim()
    db.create_responsibility("user_bob", "Separate duty", "bob")
    bob = db.claim()
    assert bob.user_id == "user_bob" and alice.user_id == "user_alice"
    with pytest.raises(LookupError):
        pinned(device, bob, observed)


def test_exact_replay_preserves_task_and_rechecks_current_authority(device):
    observed = published(device)
    db = device[0]
    duty = create(device, [observed])
    before = counts(db)
    assert create(device, [observed])["id"] == duty["id"]
    assert counts(db) == before
    db.rotate_or_revoke("user_alice", device[1]["connection_id"])
    with pytest.raises(SourceRefreshRequired):
        create(device, [observed])


@pytest.mark.parametrize("kwargs", [{"max_steps": 5}, {"max_revisions": 1}, {"pending_limit": 19}])
def test_changed_replay_limits_conflict_without_creating_more_work(device, kwargs):
    observed = published(device)
    create(device, [observed])
    before = counts(device[0])
    with pytest.raises(RequestConflict):
        create(device, [observed], **kwargs)
    assert counts(device[0]) == before


@pytest.mark.parametrize(
    "kwargs",
    [
        {"max_steps": True},
        {"max_steps": 0},
        {"max_steps": 13},
        {"max_revisions": True},
        {"max_revisions": -1},
        {"max_revisions": 3},
        {"pending_limit": True},
        {"pending_limit": 0},
        {"pending_limit": 1001},
    ],
)
def test_invalid_limits_do_not_create_any_duty(device, kwargs):
    observed = published(device)
    before = counts(device[0])
    with pytest.raises(ValueError):
        create(device, [observed], **kwargs)
    assert counts(device[0]) == before


@pytest.mark.parametrize(
    "ids,error",
    [
        ([], ValueError),
        ([uuid4()] * 9, ValueError),
        ([uuid4(), uuid4()], LookupError),
        (["invalid"], LookupError),
        ([True], LookupError),
    ],
)
def test_bad_object_lists_leave_no_partial_setup(device, ids, error):
    published(device)
    before = counts(device[0])
    with pytest.raises(error):
        device[0].create_canvas_draft_responsibility("user_alice", "Draft", "bad", object_ids=ids)
    assert counts(device[0]) == before


def test_duplicate_ids_and_mixed_owned_unknown_ids_are_atomic(device):
    observed = published(device)
    db = device[0]
    before = counts(db)
    for ids, error in [
        ([observed["object_id"]] * 2, ValueError),
        ([observed["object_id"], str(uuid4())], LookupError),
    ]:
        with pytest.raises(error):
            db.create_canvas_draft_responsibility("user_alice", "Draft", "bad", object_ids=ids)
    assert counts(db) == before


@pytest.mark.parametrize("control", ["revoke", "scope", "expiry", "pause"])
def test_current_controls_fence_old_task_reads_and_commits(device, control):
    observed = published(device)
    db = device[0]
    duty = create(device, [observed])
    lease = db.claim()
    assert pinned(device, lease, observed)["sections"]
    if control == "revoke":
        db.rotate_or_revoke("user_alice", device[1]["connection_id"])
    elif control == "scope":
        sync.set_scope(device, [], kinds=[])
    elif control == "pause":
        db.set_paused("user_alice", True)
    else:
        with db.connection() as conn:
            conn.execute(
                "UPDATE wrytely_agent.source_connections SET "
                "credential_expires_at=clock_timestamp()-interval '1 second'"
            )
    with pytest.raises(LeaseLost):
        pinned(device, lease, observed)
    with pytest.raises(LeaseLost):
        db.complete(lease, "Late result must not commit")
    assert db.draft_responsibility_status("user_alice", duty["id"])["status"] != "done"


def test_capacity_does_not_prevent_exact_replay(device):
    observed = published(device)
    db = device[0]
    duty = create(device, [observed], pending_limit=1)
    assert create(device, [observed], pending_limit=1)["id"] == duty["id"]
    before = counts(db)
    with pytest.raises(QueueFull):
        create(device, [observed], key="over-limit", pending_limit=1)
    assert counts(db) == before


def test_generation_change_cannot_silently_rescope_same_request(device):
    observed = published(device)
    create(device, [observed])
    sync.set_scope(device, [], kinds=[])
    with pytest.raises(SourceRefreshRequired):
        create(device, [observed])


def test_unchanged_refresh_keeps_scope_revision_and_task_but_pins_old_observation(device):
    observed = published(device)
    db = device[0]
    duty = create(device, [observed])
    lease = db.claim()
    before = counts(db)
    scan = evidence.next_scan(device, "unchanged-refresh")
    body, upload, root = ready(device, scan, key="repeat")
    receipt = evidence.upload(device, scan, page(device, scan, body, upload))
    evidence.close(device, scan, receipt)
    newer = receipt["observations"][0]
    assert newer["document_version_id"] == observed["document_version_id"]
    assert newer["observation_id"] != observed["observation_id"]
    assert create(device, [newer])["memory_revision"] == duty["memory_revision"]
    assert counts(db)["tasks"] == before["tasks"]
    old = pinned(device, lease, observed)
    assert old["historical"] and not old["freshness"]["usable"]
    assert pinned(device, lease, newer)["freshness"]["usable"]


def test_changed_document_invalidates_revision_and_old_lease(device):
    observed = published(device)
    db = device[0]
    duty = create(device, [observed])
    lease = db.claim()
    scan = evidence.next_scan(device, "changed")
    body, upload, root = ready(device, scan, key="changed", due="2026-01-04T00:00:00Z")
    receipt = evidence.upload(device, scan, page(device, scan, body, upload))
    evidence.close(device, scan, receipt)
    assert root["document_version_id"] != observed["document_version_id"]
    with pytest.raises(LeaseLost):
        pinned(device, lease, observed)
    with db.connection() as conn:
        state = conn.execute(
            "SELECT * FROM wrytely_agent.responsibilities WHERE id=%s", (duty["id"],)
        ).fetchone()
    assert state["memory_revision"] == duty["memory_revision"] + 1
    assert state["status"] == "blocked"


def test_scope_creation_rolls_back_if_credentials_expire_at_final_check(device, monkeypatch):
    observed = published(device)
    db = device[0]
    before = counts(db)
    original = db._responsibility_task

    def expire(conn, *args, **kwargs):
        task = original(conn, *args, **kwargs)
        conn.execute(
            "UPDATE wrytely_agent.source_connections SET "
            "credential_expires_at=clock_timestamp()-interval '1 second'"
        )
        return task

    monkeypatch.setattr(db, "_responsibility_task", expire)
    with pytest.raises(SourceRefreshRequired):
        create(device, [observed])
    assert counts(db) == before


def test_concurrent_replay_creates_exactly_one_intent_task_and_scope(device):
    observed = published(device)
    barrier = Barrier(2)

    def attempt():
        barrier.wait(timeout=10)
        return create(device, [observed])["id"]

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: attempt(), range(2)))
    assert results[0] == results[1]
    state = counts(device[0])
    assert state["responsibilities"] == state["tasks"] == state["private_draft_intents"] == 1
    assert state["responsibility_canvas_objects"] == 1


def test_legacy_generator_cannot_run_new_document_only_intent(device):
    observed = published(device)
    db = device[0]
    duty = create(device, [observed])
    model = ScriptedModel([])
    assert run_once(db, model, Settings())
    assert model.histories == []
    state = db.draft_responsibility_status("user_alice", duty["id"])
    assert state["status"] == "blocked"
    with db.connection() as conn:
        assert (
            conn.execute(
                "SELECT status_reason FROM wrytely_agent.responsibilities WHERE id=%s",
                (duty["id"],),
            ).fetchone()["status_reason"]
            == "document_drafting_not_wired"
        )
    assert counts(db)["source_versions"] == 0


def test_multiple_objects_replay_in_canonical_order_and_no_unbound_read(device):
    objects = published_pair(device)
    db = device[0]
    duty = create(device, objects)
    assert create(device, objects[::-1])["id"] == duty["id"]
    lease = db.claim()
    for observed in objects:
        assert pinned(device, lease, observed)["sections"]
    db.apply_plan(
        lease,
        PlannerDecision(
            action="blocked", reason="Test complete", step_key="test-finished", instruction=""
        ),
    )
    subset = create(device, objects[:1], key="subset")
    subset_lease = db.claim()
    assert subset_lease and subset["id"] != duty["id"]
    with pytest.raises(LookupError):
        pinned(device, subset_lease, objects[1])
    rows = db.list_canvas_evidence_for_task(subset_lease, connection_id=device[1]["connection_id"])[
        "sources"
    ]
    assert [r["object_id"] for r in rows] == [objects[0]["object_id"]]
    assert counts(db)["source_versions"] == 0


def test_unpublished_ready_root_cannot_be_delegated(device):
    scan = evidence.prepare(device)
    ready(device, scan)
    obj = evidence.rows(device, "canvas_evidence_objects")[0]
    assert obj["latest_observation_id"] is None
    before = counts(device[0])
    with pytest.raises(LookupError, match="Not found"):
        create(device, [{"object_id": str(obj["id"])}])
    assert counts(device[0]) == before


def test_inline_observation_change_also_invalidates_explicit_object_scope(device):
    from test_canvas_reads import collected

    db = device[0]
    obj = collected(device)[0]
    observed = {"object_id": str(obj["id"])}
    duty = create(device, [observed])
    lease = db.claim()
    assert db.read_canvas_evidence_for_task(lease, obj["id"])["section"]["text"] == "A📚B"
    scan = evidence.next_scan(device, "inline-changed")
    item = evidence.assignment()
    item["content"] = "Changed instructions"
    receipt = evidence.upload(device, scan, evidence.body(device, scan, [item]))
    evidence.close(device, scan, receipt)
    with pytest.raises(LeaseLost):
        db.read_canvas_evidence_for_task(lease, obj["id"])
    assert db.draft_responsibility_status("user_alice", duty["id"])["status"] == "blocked"


def test_concurrent_revocation_never_leaves_usable_work(device):
    observed = published(device)
    db = device[0]
    barrier = Barrier(2)

    def delegate():
        barrier.wait(timeout=10)
        try:
            return create(device, [observed])
        except SourceRefreshRequired:
            return None

    def revoke():
        barrier.wait(timeout=10)
        db.rotate_or_revoke("user_alice", device[1]["connection_id"])

    with ThreadPoolExecutor(max_workers=2) as pool:
        created = pool.submit(delegate)
        revoked = pool.submit(revoke)
        duty = created.result(timeout=20)
        revoked.result(timeout=20)
    assert db.claim() is None
    if duty:
        assert db.draft_responsibility_status("user_alice", duty["id"])["status"] == "blocked"
    else:
        assert counts(db)["responsibilities"] == 0


def test_task_clock_is_checked_after_object_authorization(device, monkeypatch):
    observed = published(device)
    db = device[0]
    create(device, [observed])
    lease = db.claim()
    original = db._document_observation

    def expire_lease(conn, *args, **kwargs):
        value = original(conn, *args, **kwargs)
        conn.execute(
            "UPDATE wrytely_agent.tasks SET lease_until=clock_timestamp()-interval '1 second' "
            "WHERE id=%s",
            (lease.task_id,),
        )
        return value

    monkeypatch.setattr(db, "_document_observation", expire_lease)
    with pytest.raises(LeaseLost, match="expired during Canvas scope"):
        db.event(lease, "late-result", {})
    with db.connection() as conn:
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM wrytely_agent.episode_events WHERE kind='late-result'"
            ).fetchone()["n"]
            == 0
        )


def test_fresh_publication_in_new_generation_does_not_rebind_old_delegation(device):
    observed = published(device)
    create(device, [observed])
    sync.set_scope(device, [], kinds=[])
    # Restore source collection under a new generation using the existing actor.
    # Recapture can make an object readable to its owner, never restore old task scope.
    sync.set_scope(device, ["101"], kinds=["assignments"])
    scan = evidence.next_scan(device, "recaptured-generation")
    body, upload, _ = ready(device, scan, key="recaptured")
    receipt = evidence.upload(device, scan, page(device, scan, body, upload))
    evidence.close(device, scan, receipt)
    newer = receipt["observations"][0]
    assert newer["object_id"] == observed["object_id"]
    assert device[0].read_canvas_document_sections(
        "user_alice",
        newer["object_id"],
        observation_id=newer["observation_id"],
        document_version_id=newer["document_version_id"],
    )["freshness"]["usable"]
    with pytest.raises(SourceRefreshRequired):
        create(device, [newer])
    fresh = create(device, [newer], key="new-delegation")
    assert fresh["status"] == "active"
