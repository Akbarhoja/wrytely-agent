from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from threading import Barrier

import pytest
import test_canvas_sync as sync
from pydantic import ValidationError
from test_canvas_sync import device as device

from shared.canvas_sync import CanvasSyncConflict
from shared.source_connections import SourceCredentialRejected


def assignment():
    return {
        "kind": "assignment",
        "provider_id": "17",
        "provider_updated_at": None,
        "title": "Synthetic assignment",
        "reference": sync.ORIGIN + "/courses/101/assignments/17",
        "content": "Explain your reasoning and cite three sources.",
        "coverage": "complete",
        "missing": [],
        "fields": {
            "due_at": "2026-11-02T05:59:00Z",
            "unlock_at": None,
            "lock_at": None,
            "points_possible": "20",
            "submission_types": ["online_upload"],
            "rubric": [
                {"id": "r1", "description": "Use three sources", "points": "20", "ratings": []}
            ],
            "published": True,
        },
    }


def prepare(device, kinds=None):
    sync.discover(device)
    sync.set_scope(device, ["101"], kinds=["assignments"] if kinds is None else kinds)
    return next_scan(device, "academic-1")


def next_scan(device, key):
    scan = sync.begin(device, key)
    receipt = sync.commit(device, scan, sync.envelope(device, scan))
    scan["checkpoint"] = receipt["checkpoint"]
    sync.finish_resource(device, scan)
    return scan


def body(
    device, scan, items=None, *, key="academic-page-1", kind="assignments", cursor=None, seen=None
):
    value = sync.envelope(device, scan, [], key=key, cursor=cursor)
    value["items"] = [assignment()] if items is None else items
    value["resource"] = {"course_id": "101", "kind": kind}
    value["coverage"]["seen_count"] = len(value["items"]) if seen is None else seen
    return value


def upload(device, scan, value):
    return sync.commit(device, scan, value)


def close(device, scan, receipt, *, kind="assignments", partial=False):
    scan["checkpoint"] = receipt["checkpoint"]
    result = sync.finish_resource(
        device,
        scan,
        key="101/" + kind,
        finish_key="end-" + kind,
        outcome="partial" if partial else "complete",
        reason="extraction_failed" if partial else None,
    )
    sync.finish(device, scan)
    return result


def rows(device, table):
    allowed = {
        "source_versions",
        "canvas_evidence_objects",
        "canvas_evidence_observations",
        "canvas_evidence_events",
        "canvas_evidence_payloads",
        "academic_sources",
    }
    assert table in allowed
    with device[0].connection() as conn:
        return conn.execute("SELECT * FROM wrytely_agent." + table).fetchall()


def test_complete_text_metadata_provenance_and_event_are_atomic_and_staged(device):
    scan = prepare(device)
    value = body(device, scan)
    receipt = upload(device, scan, value)
    version = rows(device, "source_versions")[0]
    payload = rows(device, "canvas_evidence_payloads")[0]
    check = rows(device, "canvas_evidence_observations")[0]
    obj = rows(device, "canvas_evidence_objects")[0]
    assert version["content"] == value["items"][0]["content"]
    assert payload["payload"]["fields"]["due_at"] == "2026-11-02T05:59:00.000000Z"
    assert check["reference"] == value["items"][0]["reference"]
    assert obj["complete_version_id"] == version["id"]
    assert check["version_id"] == version["id"]
    assert len(rows(device, "canvas_evidence_events")) == 1
    assert receipt["source_versions"][0]["version_id"] == str(version["id"])
    assert receipt["observations"][0]["historical"] is False
    # No half-integrated collection path can activate the old drafting/read freshness rules.
    assert rows(device, "academic_sources")[0]["latest_version_id"] is None
    assert device[0].source_snapshots("user_alice") == []
    assert close(device, scan, receipt)["source_manifest_digest"] is not None


def test_unchanged_observation_reuses_version_but_real_check_advances_and_replay_does_not(device):
    scan = prepare(device)
    receipt = upload(device, scan, body(device, scan))
    close(device, scan, receipt)
    original_version = rows(device, "source_versions")[0]
    original_check_time = rows(device, "canvas_evidence_objects")[0]["last_successful_check_at"]
    second = next_scan(device, "academic-2")
    value = body(device, second)
    value["items"][0]["provider_updated_at"] = "2026-10-31T03:00:00Z"
    value["items"][0]["reference"] += "?synthetic-link-version=2"
    receipt2 = upload(device, second, value)
    assert receipt2["source_versions"][0]["version_id"] == str(original_version["id"])
    assert len(rows(device, "source_versions")) == 1
    assert len(rows(device, "canvas_evidence_observations")) == 2
    assert len(rows(device, "canvas_evidence_events")) == 1
    current = rows(device, "canvas_evidence_objects")[0]
    assert current["last_successful_check_at"] > original_check_time
    replay = upload(device, second, value)
    assert replay == {**receipt2, "replayed": True}
    assert rows(device, "canvas_evidence_objects")[0] == current
    assert rows(device, "source_versions")[0]["retrieved_at"] == original_version["retrieved_at"]


def test_due_date_change_creates_new_version_even_when_body_is_unchanged(device):
    first = prepare(device)
    receipt = upload(device, first, body(device, first))
    close(device, first, receipt)
    second = next_scan(device, "academic-2")
    value = body(device, second)
    value["items"][0]["fields"]["due_at"] = "2026-11-03T05:59:00Z"
    upload(device, second, value)
    assert len(rows(device, "source_versions")) == 2
    assert len(rows(device, "canvas_evidence_events")) == 2


def test_content_reversion_reuses_immutable_version_and_records_new_transition(device):
    scan = prepare(device)
    ids = []
    for number, text in enumerate(["Version A", "Version B", "Version A"]):
        if number:
            scan = next_scan(device, f"academic-{number + 1}")
        value = body(device, scan)
        value["items"][0]["content"] = text
        receipt = upload(device, scan, value)
        ids.append(receipt["source_versions"][0]["version_id"])
        close(device, scan, receipt)
    assert ids[0] == ids[2] and ids[1] != ids[0]
    assert len(rows(device, "source_versions")) == 2
    assert len(rows(device, "canvas_evidence_events")) == 3
    assert str(rows(device, "canvas_evidence_objects")[0]["complete_version_id"]) == ids[0]


def test_partial_new_content_preserves_complete_evidence_and_blocks_complete_resource(device):
    first = prepare(device)
    receipt = upload(device, first, body(device, first))
    close(device, first, receipt)
    complete_id = rows(device, "canvas_evidence_objects")[0]["complete_version_id"]
    checked = rows(device, "canvas_evidence_objects")[0]["last_successful_check_at"]
    second = next_scan(device, "academic-2")
    value = body(device, second)
    value["items"][0].update(
        content="Changed but rubric unavailable", coverage="partial", missing=["rubric_attachment"]
    )
    receipt2 = upload(device, second, value)
    obj = rows(device, "canvas_evidence_objects")[0]
    assert obj["complete_version_id"] == complete_id
    assert obj["last_successful_check_at"] == checked
    second["checkpoint"] = receipt2["checkpoint"]
    with pytest.raises(CanvasSyncConflict, match="incomplete_resource"):
        sync.finish_resource(device, second, key="101/assignments", finish_key="cannot-complete")
    assert close(device, second, receipt2, partial=True)["source_manifest_digest"] is None


def test_restricted_empty_content_is_retained_without_inventing_text_version(device):
    scan = prepare(device)
    item = assignment()
    item.update(content="", coverage="restricted", missing=["initial_post_required"])
    receipt = upload(device, scan, body(device, scan, [item]))
    assert receipt["source_versions"] == []
    assert receipt["observations"][0]["version_id"] is None
    assert len(rows(device, "canvas_evidence_observations")) == 1
    assert rows(device, "source_versions") == []
    assert rows(device, "canvas_evidence_objects")[0]["complete_version_id"] is None


def test_older_capture_stages_history_without_replacing_newer_check(device):
    scan = prepare(device)
    value = body(device, scan)
    value["observed_at"] = (datetime.now(UTC) + timedelta(minutes=2)).isoformat()
    receipt = upload(device, scan, value)
    close(device, scan, receipt)
    previous = rows(device, "canvas_evidence_objects")[0]
    second = next_scan(device, "academic-2")
    older = body(device, second)
    older["items"][0]["content"] = "Older captured requirements"
    result = upload(device, second, older)
    assert result["observations"][0]["historical"] is True
    current = rows(device, "canvas_evidence_objects")[0]
    assert current["latest_observation_id"] == previous["latest_observation_id"]
    assert current["complete_version_id"] == previous["complete_version_id"]
    assert current["last_successful_check_at"] == previous["last_successful_check_at"]
    assert len(rows(device, "canvas_evidence_events")) == 1


def test_batch_failure_after_first_item_rolls_back_all_evidence_and_progress(device):
    scan = prepare(device)
    first, second = assignment(), assignment()
    second["provider_id"] = "18"
    second["reference"] = "https://unrelated.example.edu/courses/101/assignments/18"
    value = body(device, scan, [first, second])
    with pytest.raises(ValueError, match="reference outside course"):
        upload(device, scan, value)
    for table in (
        "source_versions",
        "canvas_evidence_objects",
        "canvas_evidence_observations",
        "canvas_evidence_events",
    ):
        assert rows(device, table) == []
    second["reference"] = sync.ORIGIN + "/courses/101/assignments/18"
    result = upload(device, scan, value)
    assert len(result["source_versions"]) == 2


def test_atomic_lease_expiry_rolls_back_versions_checks_and_events(device, monkeypatch):
    scan = prepare(device)
    value = body(device, scan)
    db, _ = device
    original = db._save

    def expire(conn, scan_row, operation, key, digest, result):
        if operation == "batch":
            conn.execute(
                "UPDATE wrytely_agent.canvas_scans SET "
                "lease_expires_at=clock_timestamp()-interval '1 second' WHERE id=%s",
                (scan_row["id"],),
            )
        return original(conn, scan_row, operation, key, digest, result)

    with monkeypatch.context() as patch:
        patch.setattr(db, "_save", expire)
        with pytest.raises(CanvasSyncConflict, match="lease_expired"):
            upload(device, scan, value)
    assert rows(device, "source_versions") == []
    assert rows(device, "canvas_evidence_observations") == []
    assert rows(device, "canvas_evidence_events") == []
    assert upload(device, scan, value)["replayed"] is False


def test_lost_ack_after_resume_replays_exact_receipt_without_repeating_effects(device):
    scan = prepare(device)
    value = body(device, scan)
    receipt = upload(device, scan, value)
    current = rows(device, "canvas_evidence_objects")[0]
    resumed = device[0].resume_sync(
        device[1]["ingestion_bearer"],
        scan["scan_id"],
        sync.context(device)["generation"],
        "resume-academic",
    )
    assert resumed["checkpoint"] == receipt["checkpoint"]
    replay = upload(device, scan, value)
    assert replay == {**receipt, "replayed": True}
    assert rows(device, "canvas_evidence_objects")[0] == current
    assert len(rows(device, "canvas_evidence_events")) == 1
    changed = deepcopy(value)
    changed["items"][0]["content"] += " modified"
    with pytest.raises(CanvasSyncConflict, match="replay_conflict"):
        upload(device, scan, changed)


def test_concurrent_duplicate_uploads_have_one_version_check_and_event(device):
    scan = prepare(device)
    value = body(device, scan)
    barrier = Barrier(2)

    def run(_):
        barrier.wait(timeout=5)
        return upload(device, scan, value)

    with ThreadPoolExecutor(max_workers=2) as pool:
        receipts = list(pool.map(run, range(2)))
    assert {r["replayed"] for r in receipts} == {True, False}
    for table in ("source_versions", "canvas_evidence_observations", "canvas_evidence_events"):
        assert len(rows(device, table)) == 1


def test_unselected_resource_and_other_account_cannot_write_or_replay_evidence(device):
    scan = prepare(device)
    value = body(device, scan)
    value["resource"]["course_id"] = "999"
    with pytest.raises(CanvasSyncConflict, match="resource_not_selected"):
        upload(device, scan, value)
    value["resource"]["course_id"] = "101"
    upload(device, scan, value)
    db, _ = device
    db.provision("user_bob")
    code = db.create_pairing("user_bob", sync.ORIGIN)["code"]
    other = db.redeem_pairing(code, "bob-device")
    db.bind_canvas_identity(other["ingestion_bearer"], sync.ORIGIN, "bob-subject")
    with pytest.raises(SourceCredentialRejected):
        db.commit_sync_batch(
            other["ingestion_bearer"],
            scan["scan_id"],
            2,
            scan["lease_token"],
            value["batch_key"],
            scan["checkpoint"],
            value,
        )


def test_revoke_racing_upload_keeps_old_generation_terminal(device):
    scan = prepare(device)
    value = body(device, scan)
    barrier = Barrier(2)

    def run(which):
        barrier.wait(timeout=5)
        if which == "revoke":
            return device[0].rotate_or_revoke("user_alice", device[1]["connection_id"])
        try:
            return upload(device, scan, value)
        except SourceCredentialRejected:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(run, ["write", "revoke"]))
    with device[0].connection() as conn:
        assert (
            conn.execute(
                "SELECT state FROM wrytely_agent.canvas_scans WHERE id=%s", (scan["scan_id"],)
            ).fetchone()["state"]
            == "aborted"
        )


@pytest.mark.parametrize(
    "kind,resource,fields",
    [
        ("syllabus", "syllabus", {"page_id": None, "module_ids": [], "source_format": "text"}),
        ("page", "pages", {"page_id": "chapter-1", "module_ids": [], "source_format": "html"}),
        (
            "announcement",
            "announcements",
            {
                "author_role": "instructor",
                "posted_at": "2026-10-31T00:00:00Z",
                "announcement_id": "17",
            },
        ),
        (
            "discussion",
            "discussions",
            {
                "topic_id": "17",
                "parent_entry_id": None,
                "author_role": "instructor",
                "required_initial_post": False,
                "due_at": None,
            },
        ),
        (
            "entry",
            "discussions",
            {
                "topic_id": "17",
                "parent_entry_id": "18",
                "author_role": "student",
                "required_initial_post": None,
                "due_at": None,
            },
        ),
        (
            "submission",
            "submissions",
            {
                "assignment_id": "17",
                "submitted_at": None,
                "workflow_state": "unsubmitted",
                "attempt": 0,
                "late": False,
                "missing": False,
            },
        ),
        (
            "grade",
            "grades",
            {
                "assignment_id": "17",
                "score": "18",
                "points_possible": "20",
                "grading_type": "points",
                "grade": "90%",
                "grade_basis": "posted",
            },
        ),
    ],
)
def test_bounded_text_resource_types_preserve_exact_fields(device, kind, resource, fields):
    scan = prepare(device, [resource])
    item = assignment()
    item.update(kind=kind, fields=fields)
    receipt = upload(device, scan, body(device, scan, [item], kind=resource))
    assert receipt["source_versions"]
    assert rows(device, "canvas_evidence_payloads")[0]["payload"]["kind"] == kind
    assert close(device, scan, receipt, kind=resource)["coverage"] == "complete"


@pytest.mark.parametrize(
    "field,value",
    [
        ("content", "x" * 24001),
        ("fields", {"unreviewed": True}),
        ("missing", ["arbitrary raw provider error!"]),
    ],
)
def test_oversized_or_undeclared_evidence_rejects_without_partial_writes(device, field, value):
    scan = prepare(device)
    value_body = body(device, scan)
    value_body["items"][0][field] = value
    with pytest.raises(ValidationError):
        upload(device, scan, value_body)
    assert rows(device, "canvas_evidence_events") == []


def test_rubric_key_collisions_and_floats_cannot_create_nonportable_versions(device):
    scan = prepare(device)
    value = body(device, scan)
    value["items"][0]["fields"]["points_possible"] = 1.25
    with pytest.raises(ValidationError):
        upload(device, scan, value)
    value["items"][0] = assignment()
    value["items"][0]["fields"]["rubric"] = [
        {"id": key, "description": "Same criterion", "points": "1", "ratings": []}
        for key in ("é", "e\u0301")
    ]
    with pytest.raises(ValidationError, match="normalized rubric ID"):
        upload(device, scan, value)


def test_full_empty_enumeration_marks_missing_without_deleting_complete_evidence(device):
    scan = prepare(device)
    receipt = upload(device, scan, body(device, scan))
    close(device, scan, receipt)
    before = rows(device, "canvas_evidence_objects")[0]
    second = next_scan(device, "academic-2")
    empty = upload(device, second, body(device, second, []))
    close(device, second, empty)
    after = rows(device, "canvas_evidence_objects")[0]
    assert after["missing_pending_confirmation"] is True
    assert after["complete_version_id"] == before["complete_version_id"]
    assert len(rows(device, "source_versions")) == 1


def test_decimal_and_equivalent_date_formatting_do_not_create_false_revisions(device):
    scan = prepare(device)
    first_body = body(device, scan)
    first = upload(device, scan, first_body)
    close(device, scan, first)
    second = next_scan(device, "academic-2")
    value = body(device, second)
    value["items"][0]["fields"]["points_possible"] = "20.000"
    value["items"][0]["fields"]["rubric"][0]["points"] = "20.00"
    value["items"][0]["fields"]["due_at"] = "2026-11-02T00:59:00-05:00"
    original = deepcopy(value)
    repeated = upload(device, second, value)
    assert value == original
    assert repeated["source_versions"] == first["source_versions"]
    assert len(rows(device, "canvas_evidence_events")) == 1


def test_partial_enumeration_never_marks_unseen_objects_missing(device):
    scan = prepare(device)
    first = upload(device, scan, body(device, scan))
    close(device, scan, first)
    second = next_scan(device, "academic-2")
    sync.finish_resource(
        device,
        second,
        key="101/assignments",
        finish_key="partial-end",
        outcome="partial",
        reason="provider_unavailable",
    )
    assert rows(device, "canvas_evidence_objects")[0]["missing_pending_confirmation"] is False


def test_two_resources_use_independent_cursors_and_cannot_switch_before_finish(device):
    scan = prepare(device, ["assignments", "syllabus"])
    first = upload(device, scan, body(device, scan, cursor="assignment-next"))
    scan["checkpoint"] = first["checkpoint"]
    syllabus = assignment()
    syllabus.update(
        kind="syllabus", fields={"page_id": None, "module_ids": [], "source_format": "text"}
    )
    syllabus_body = body(device, scan, [syllabus], key="syllabus-page", kind="syllabus")
    with pytest.raises(CanvasSyncConflict, match="finish_previous_resource"):
        upload(device, scan, syllabus_body)
    sync.finish_resource(
        device,
        scan,
        key="101/assignments",
        finish_key="assignments-partial",
        outcome="partial",
        reason="cursor_invalid",
    )
    receipt = upload(device, scan, syllabus_body)
    scan["checkpoint"] = receipt["checkpoint"]
    sync.finish_resource(device, scan, key="101/syllabus", finish_key="syllabus-done")
    assert sync.finish(device, scan)["coverage"] == "partial"


@pytest.mark.parametrize("empty_clock_minutes", [0, 4])
def test_empty_academic_scan_cannot_hide_newer_positive_observation(device, empty_clock_minutes):
    first = prepare(device)
    positive = body(device, first)
    positive["observed_at"] = (datetime.now(UTC) + timedelta(minutes=2)).isoformat()
    receipt = upload(device, first, positive)
    close(device, first, receipt)
    previous = rows(device, "canvas_evidence_objects")[0]
    second = next_scan(device, "older-empty")
    empty = body(device, second, [])
    empty["observed_at"] = (datetime.now(UTC) + timedelta(minutes=empty_clock_minutes)).isoformat()
    receipt = upload(device, second, empty)
    close(device, second, receipt)
    current = rows(device, "canvas_evidence_objects")[0]
    assert current["missing_pending_confirmation"] is False
    assert current["latest_observation_id"] == previous["latest_observation_id"]
    assert current["complete_version_id"] == previous["complete_version_id"]


@pytest.mark.parametrize("field", ["module_ids", "submission_types"])
@pytest.mark.parametrize("values", [["e\u0301", "\u00e9"], ["e\u0301", "f"], ["a\nb", "a\rb"]])
def test_identifier_lists_reject_collisions_or_disorder_after_normalization(field, values):
    from contracts.canvas_evidence import EvidenceItem

    value = assignment()
    kind = "assignment"
    if field == "module_ids":
        kind = value["kind"] = "page"
        value["fields"] = dict(page_id="17", module_ids=values, source_format="html")
    else:
        value["fields"][field] = values
    with pytest.raises(ValueError, match="Sorted unique"):
        EvidenceItem.model_validate(value).payload(kind)


@pytest.mark.parametrize("field", ["module_ids", "submission_types"])
def test_identifier_order_is_decided_by_canonical_values(field):
    from contracts.canvas_evidence import EvidenceItem

    value = assignment()
    kind = "assignment"
    if field == "module_ids":
        kind = value["kind"] = "page"
        value["fields"] = dict(page_id="17", module_ids=["f", "e\u0301"], source_format="html")
    else:
        value["fields"][field] = ["f", "e\u0301"]
    assert EvidenceItem.model_validate(value).payload(kind)["fields"][field] == ["f", "\u00e9"]
