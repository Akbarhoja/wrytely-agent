from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
import test_canvas_evidence as evidence
import test_canvas_reads as reads
import test_canvas_sync as sync
from test_canvas_sync import device as device
from test_planner import plan
from test_worker import ScriptedModel

from runtime.worker import run_once
from shared.canvas_reads import SourceRefreshRequired
from shared.canvas_sync import CanvasSyncConflict
from shared.config import Settings
from shared.db import LeaseLost
from shared.document_sections import DocumentSection, DocumentSections, split_document_text


def save(device, obj, document=None, *, bind=True, observation_id=None, format="text"):
    document = split_document_text("x" * 30_000) if document is None else document
    with device[0].connection() as conn:
        version = device[0]._stage_canvas_document_sections(
            conn,
            obj["agent_id"],
            obj["id"],
            document,
            format=format,
            extractor_version="synthetic.v1",
        )
        if bind:
            device[0]._bind_canvas_document_sections(
                conn,
                obj["agent_id"],
                obj["id"],
                observation_id or obj["latest_observation_id"],
                version,
            )
    return version


def read(device, obj, version, *, user="user_alice", observation_id=None, **kwargs):
    return device[0].read_canvas_document_sections(
        user,
        obj["id"],
        observation_id=observation_id or obj["latest_observation_id"],
        document_version_id=version,
        **kwargs,
    )


def stored(device, table):
    assert table in {"versions", "sections", "bindings"}
    with device[0].connection() as conn:
        return conn.execute("SELECT * FROM wrytely_agent.canvas_document_" + table).fetchall()


def test_owned_long_document_roundtrips_with_stable_sections_and_explicit_continuation(device):
    obj = reads.collected(device)[0]
    version = save(device, obj, split_document_text("A📚" * 100_000))
    first, sections = 0, []
    while True:
        result = read(device, obj, version, first_slot=first)
        assert result["object_id"] == str(obj["id"])
        assert result["observation_id"] == str(obj["latest_observation_id"])
        assert result["document_version_id"] == str(version)
        assert sum(len(s["text"]) for s in result["sections"]) <= 40_000
        assert result["freshness"]["usable"] is True
        sections.extend(result["sections"])
        if result["next_slot"] is None:
            break
        assert result["next_slot"] > first
        first = result["next_slot"]
    assert "".join(s["text"] for s in sections) == "A📚" * 100_000
    assert len({s["segment_id"] for s in sections}) == len(sections) == result["total_slots"]
    assert read(device, obj, version)["sections"][0] == sections[0]
    assert "section_fingerprint" not in result


def test_unbound_storage_is_invisible_and_binding_is_idempotent_without_freshening(device):
    obj = reads.collected(device)[0]
    checks = evidence.rows(device, "canvas_evidence_observations")
    events = evidence.rows(device, "canvas_evidence_events")
    version = save(device, obj, bind=False)
    with pytest.raises(LookupError, match="Not found"):
        read(device, obj, version)
    assert save(device, obj) == version
    assert save(device, obj) == version
    assert len(stored(device, "versions")) == len(stored(device, "bindings")) == 1
    assert len(stored(device, "sections")) == 2
    assert evidence.rows(device, "canvas_evidence_observations") == checks
    assert evidence.rows(device, "canvas_evidence_events") == events
    assert device[0].source_snapshots("user_alice") == []


def test_immutable_observation_binding_cannot_be_replaced(device):
    obj = reads.collected(device)[0]
    original = save(device, obj)
    with pytest.raises(CanvasSyncConflict, match="document_binding_changed"):
        save(device, obj, split_document_text("new text"))
    assert len(stored(device, "versions")) == 1
    assert read(device, obj, original)["sections"][0]["text"] == "x" * 24_000


@pytest.mark.parametrize("target", ["actor", "observation", "version", "other_object_version"])
def test_cross_account_and_wrong_pinned_identity_never_return_body(device, target):
    objs = reads.collected(device, 2)
    version = save(device, objs[0])
    device[0].provision("user_bob")
    kwargs = {}
    if target == "actor":
        kwargs["user"] = "user_bob"
    elif target == "observation":
        kwargs["observation_id"] = objs[1]["latest_observation_id"]
    elif target == "version":
        version = uuid4()
    else:
        version = save(device, objs[1])
    with pytest.raises(LookupError, match="Not found"):
        read(device, objs[0], version, **kwargs)


@pytest.mark.parametrize("control", ["scope", "revoke", "expiry", "generation", "origin"])
def test_current_access_fences_document_body(device, control):
    obj = reads.collected(device)[0]
    version = save(device, obj)
    db = device[0]
    if control == "scope":
        sync.set_scope(device, [], kinds=[])
    elif control == "revoke":
        db.rotate_or_revoke("user_alice", device[1]["connection_id"])
    elif control == "origin":
        db._canvas_origins = frozenset()
    else:
        with db.connection() as conn:
            if control == "expiry":
                conn.execute(
                    "UPDATE wrytely_agent.source_connections "
                    "SET credential_expires_at=clock_timestamp()-interval '1 second'"
                )
            else:
                conn.execute("UPDATE wrytely_agent.source_connections SET generation=generation+1")
    with pytest.raises(SourceRefreshRequired):
        read(device, obj, version)


def test_real_check_history_reuses_body_version_without_losing_observation_identity(device):
    obj = reads.collected(device)[0]
    versions, observations = [], []
    for index, text in enumerate(["Version A", "Version B", "Version A"]):
        if index:
            scan = evidence.next_scan(device, f"document-check-{index}")
            receipt = evidence.upload(device, scan, evidence.body(device, scan))
            evidence.close(device, scan, receipt)
            observation = receipt["observations"][0]["observation_id"]
        else:
            observation = obj["latest_observation_id"]
        observations.append(str(observation))
        versions.append(save(device, obj, split_document_text(text), observation_id=observation))
    assert versions[0] == versions[2] != versions[1]
    assert len(stored(device, "versions")) == 2 and len(stored(device, "bindings")) == 3
    old = read(device, obj, versions[0], observation_id=observations[0])
    current = read(device, obj, versions[2], observation_id=observations[2])
    assert old["historical"] is True and old["freshness"]["usable"] is False
    assert current["historical"] is False and current["sections"][0]["text"] == "Version A"
    with pytest.raises(LookupError):
        read(device, obj, versions[1], observation_id=observations[2])


def test_interrupted_section_write_rolls_back_root_and_all_parts(device):
    obj = reads.collected(device)[0]
    db = device[0]
    with pytest.raises(RuntimeError, match="synthetic interruption"):
        with db.connection() as conn:

            class Interrupted:
                calls = 0

                def execute(self, query, *args, **kwargs):
                    if "INSERT INTO wrytely_agent.canvas_document_sections" in query:
                        self.calls += 1
                        if self.calls == 2:
                            raise RuntimeError("synthetic interruption")
                    return conn.execute(query, *args, **kwargs)

            db._stage_canvas_document_sections(
                Interrupted(),
                obj["agent_id"],
                obj["id"],
                split_document_text("x" * 60_000),
                format="text",
                extractor_version="synthetic.v1",
            )
    assert (
        stored(device, "versions") == stored(device, "sections") == stored(device, "bindings") == []
    )


def test_binding_and_section_storage_share_caller_transaction_rollback(device):
    obj = reads.collected(device)[0]
    db = device[0]
    with pytest.raises(CanvasSyncConflict, match="synthetic_failure"):
        with db.connection() as conn:
            version = db._stage_canvas_document_sections(
                conn,
                obj["agent_id"],
                obj["id"],
                split_document_text("text"),
                format="text",
                extractor_version="synthetic.v1",
            )
            db._bind_canvas_document_sections(
                conn, obj["agent_id"], obj["id"], obj["latest_observation_id"], version
            )
            raise CanvasSyncConflict("synthetic_failure")
    assert (
        stored(device, "versions") == stored(device, "sections") == stored(device, "bindings") == []
    )


def test_concurrent_identical_storage_and_binding_deduplicates(device):
    obj = reads.collected(device)[0]
    with ThreadPoolExecutor(max_workers=2) as pool:
        versions = list(pool.map(lambda _: save(device, obj), range(2)))
    assert versions[0] == versions[1]
    assert len(stored(device, "versions")) == len(stored(device, "bindings")) == 1


def test_database_binding_fk_forbids_cross_object_root(device):
    from psycopg.errors import ForeignKeyViolation

    objs = reads.collected(device, 2)
    version = save(device, objs[0])
    with pytest.raises(ForeignKeyViolation):
        with device[0].connection() as conn:
            conn.execute(
                "INSERT INTO wrytely_agent.canvas_document_bindings "
                "(observation_id,agent_id,object_id,document_version_id) VALUES (%s,%s,%s,%s)",
                (objs[1]["latest_observation_id"], objs[1]["agent_id"], objs[1]["id"], version),
            )
    assert len(stored(device, "bindings")) == 1


def test_pdf_gap_cannot_be_attached_as_complete_evidence(device):
    import hashlib

    obj = reads.collected(device)[0]
    section = DocumentSection(0, 0, 1, 1, "A", hashlib.sha256(b"A").hexdigest())
    document = DocumentSections((section,), 1, 2)
    with pytest.raises(ValueError, match="gaps require"):
        save(device, obj, document, format="pdf_text")
    assert stored(device, "versions") == []


def test_partial_empty_document_stays_empty_and_unusable(device):
    obj = reads.collected(device)[0]
    scan = evidence.next_scan(device, "empty-document")
    item = evidence.assignment()
    item.update(content="", coverage="unsupported", missing=["image_only"])
    receipt = evidence.upload(device, scan, evidence.body(device, scan, [item]))
    evidence.close(device, scan, receipt, partial=True)
    observation = receipt["observations"][0]["observation_id"]
    version = save(
        device, obj, DocumentSections((), 0, 2), observation_id=observation, format="pdf_text"
    )
    result = read(device, obj, version, observation_id=observation)
    assert result["sections"] == [] and result["next_slot"] is None
    assert not result["freshness"]["usable"] and result["missing"] == ["image_only"]


@pytest.mark.parametrize(
    "bound,value",
    [("first_slot", True), ("first_slot", -1), ("first_slot", 3), ("limit", 0), ("limit", 21)],
)
def test_pinned_read_bounds_reject_without_body(device, bound, value):
    obj = reads.collected(device)[0]
    version = save(device, obj)
    with pytest.raises(ValueError):
        read(device, obj, version, **{bound: value})


def test_task_reader_requires_bound_source_and_current_lease(device):
    objs = reads.collected(device, 2)
    first, second = save(device, objs[0]), save(device, objs[1])
    db = device[0]
    duty = db.create_responsibility("user_alice", "Read one document", "document-scope")
    db.bind_source("user_alice", duty["id"], objs[0]["source_id"])
    run_once(db, ScriptedModel([plan()]), Settings())
    lease = db.claim()
    assert lease is not None

    def scoped(obj, version):
        return db.read_canvas_document_sections_for_task(
            lease,
            obj["id"],
            observation_id=obj["latest_observation_id"],
            document_version_id=version,
        )

    assert scoped(objs[0], first)["sections"][0]["text"] == "x" * 24_000
    with pytest.raises(LookupError):
        scoped(objs[1], second)
    with db.connection() as conn:
        conn.execute("UPDATE wrytely_agent.agents SET paused=true WHERE id=%s", (lease.agent_id,))
    with pytest.raises(LeaseLost):
        scoped(objs[0], first)


def test_latest_failed_resource_check_keeps_document_inspectable_but_unusable(device):
    obj = reads.collected(device)[0]
    version = save(device, obj)
    scan = evidence.next_scan(device, "document-failed-check")
    sync.finish_resource(
        device,
        scan,
        key="101/assignments",
        finish_key="failed-doc-check",
        outcome="partial",
        reason="provider_unavailable",
    )
    result = read(device, obj, version)
    assert result["sections"][0]["text"] == "x" * 24_000
    assert not result["freshness"]["usable"]
    assert result["freshness"]["reason"] == "resource_incomplete"


def test_new_storage_does_not_refresh_old_evidence_age(device):
    obj = reads.collected(device)[0]
    with device[0].connection() as conn:
        conn.execute(
            "UPDATE wrytely_agent.canvas_evidence_observations "
            "SET observed_at=clock_timestamp()-interval '2 days' WHERE id=%s",
            (obj["latest_observation_id"],),
        )
    version = save(device, obj)
    result = read(device, obj, version)
    assert not result["freshness"]["usable"] and result["freshness"]["reason"] == "too_old"


def test_corrupted_stored_body_is_rejected_before_returning_any_page(device):
    obj = reads.collected(device)[0]
    version = save(device, obj)
    with device[0].connection() as conn:
        conn.execute(
            "UPDATE wrytely_agent.canvas_document_sections "
            "SET text=repeat('y',char_length(text)) WHERE document_version_id=%s",
            (version,),
        )
    with pytest.raises(ValueError, match="hash"):
        read(device, obj, version)


def test_lease_expiring_during_section_load_cannot_return_body(device, monkeypatch):
    obj = reads.collected(device)[0]
    version = save(device, obj)
    db = device[0]
    duty = db.create_responsibility("user_alice", "Inspect document", "late-document-lease")
    db.bind_source("user_alice", duty["id"], obj["source_id"])
    run_once(db, ScriptedModel([plan()]), Settings())
    lease = db.claim()
    assert lease is not None
    load = db._load_canvas_document

    def expiring_load(conn, *args):
        result = load(conn, *args)
        conn.execute(
            "UPDATE wrytely_agent.tasks "
            "SET lease_until=clock_timestamp()-interval '1 second' WHERE id=%s",
            (lease.task_id,),
        )
        return result

    monkeypatch.setattr(db, "_load_canvas_document", expiring_load)
    with pytest.raises(LeaseLost):
        db.read_canvas_document_sections_for_task(
            lease,
            obj["id"],
            observation_id=obj["latest_observation_id"],
            document_version_id=version,
        )
