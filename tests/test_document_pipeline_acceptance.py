"""Combined actual synthetic JS→private HTTP staging/publication→scoped runtime.

No claim of installed Chrome, live sources or real model inference.
"""

import unicodedata

import pytest
import test_canvas_evidence as evidence
from test_artifacts import TEXT, assessment
from test_canvas_document_parts import produce
from test_canvas_document_publication import page
from test_canvas_document_upload_api import checked, client_for, post
from test_canvas_document_uploads import begin_body, count, finish_body, put_body
from test_canvas_sync import device as device
from test_drafting import permitted, structured
from test_typed_document_drafting import CLAIM, DISCLOSURE, POLICY, RUBRIC, planner_stage, ref
from test_worker import ScriptedModel

from runtime.worker import run_once
from shared.config import Settings


def stage(device, *, scan=None, raw=None, key="pipeline", partial=False, due=None):
    scan = evidence.prepare(device) if scan is None else scan
    raw = {"text": TEXT + "\r\nCafe\u0301 📚"} if raw is None else raw
    produced = produce([raw])[0]
    body = begin_body(device, scan, key="begin-" + key)
    body["manifest"] = produced["manifest"]
    body["metadata"].update(
        total_characters=produced["total_characters"],
        total_pages=produced["total_pages"],
        format="pdf_text" if "pages" in raw else "text",
        coverage="partial" if partial else "complete",
        missing=["linked_content_unread"] if partial else [],
    )
    if due is not None:
        body["object_fields"]["due_at"] = due
    client = client_for(device)
    upload = checked(post(client, device, "/begin", body))
    parts = put_body(body, upload["upload_id"], key="put-" + key, parts=produced["parts"])
    saved = checked(post(client, device, "/parts", parts))
    finish = finish_body(body, upload["upload_id"], key="finish-" + key)
    ready = checked(post(client, device, "/finish", finish))
    return (
        scan,
        body,
        upload,
        produced,
        [("/begin", body, upload), ("/parts", parts, saved), ("/finish", finish, ready)],
    )


def publish(device, data, *, partial=False):
    scan, body, upload, *_ = data
    envelope = page(device, scan, body, upload)
    receipt = checked(
        post(
            client_for(device),
            device,
            "/batch",
            {
                "scan_id": scan["scan_id"],
                "generation": body["generation"],
                "lease_token": scan["lease_token"],
                "batch_key": envelope["batch_key"],
                "expected_checkpoint": scan["checkpoint"],
                "envelope": envelope,
            },
        )
    )
    evidence.close(device, scan, receipt, partial=partial)
    return receipt["observations"][0]


def read(device, observed, user="user_alice"):
    return device[0].read_canvas_document_sections(
        user,
        observed["object_id"],
        observation_id=observed["observation_id"],
        document_version_id=observed["document_version_id"],
    )


def test_actual_producer_http_publication_to_checked_private_draft(device):
    data = stage(device)
    assert count(device, "canvas_evidence_observations") == 0
    observed = publish(device, data)
    original = read(device, observed)
    assert "".join(s["text"] for s in original["sections"]) == unicodedata.normalize(
        "NFC", TEXT + "\nCafe\u0301 📚"
    )
    db = device[0]
    duty = db.create_canvas_draft_responsibility(
        "user_alice",
        "Compare evidence privately",
        "pipeline-duty",
        object_ids=[observed["object_id"]],
    )
    policy = dict(status="disclosure_required", evidence=ref(device, observed, POLICY))
    rubric = [dict(evidence=ref(device, observed, RUBRIC))]
    draft = dict(
        schema_version=2,
        title="Private comparison",
        body=CLAIM + "\n" + DISCLOSURE,
        disclosure=DISCLOSURE,
        citations=[dict(claim=CLAIM, evidence=ref(device, observed, CLAIM))],
    )
    planner_stage(device, (duty, policy, rubric, draft, observed, None))
    model = ScriptedModel([permitted(), structured("save_review_draft", draft), assessment()])
    assert run_once(db, model, Settings())
    with db.connection() as conn:
        artifact = conn.execute("SELECT * FROM wrytely_agent.artifacts").fetchone()
        check = conn.execute("SELECT report FROM wrytely_agent.artifact_checks").fetchone()[
            "report"
        ]
    assert artifact["state"] == "ready" and artifact["evidence_schema"] == 2
    assert check["passed"] and len(model.histories) == 3
    assert count(device, "source_versions") == 0
    assert db.artifact_review("user_alice", artifact["id"]) is None
    assert db.responsibility_artifacts("user_alice", duty["id"]) == []


@pytest.mark.parametrize("operation", ["begin", "parts", "finish"])
def test_lost_http_response_resumes_exact_actual_producer_request(device, monkeypatch, operation):
    # Simulate server commit followed by response loss through the actual HTTP route.
    scan = evidence.prepare(device)
    output = produce([{"text": "📚 Cafe\u0301\r\n"}])[0]
    body = begin_body(device, scan)
    body["manifest"] = output["manifest"]
    body["metadata"].update(total_characters=output["total_characters"], total_pages=None)
    client = client_for(device)
    request = body
    if operation != "begin":
        upload = checked(post(client, device, "/begin", body))
        request = put_body(body, upload["upload_id"], parts=output["parts"])
        if operation == "finish":
            checked(post(client, device, "/parts", request))
            request = finish_body(body, upload["upload_id"])
    name = {
        "begin": "begin_document_upload",
        "parts": "put_document_parts",
        "finish": "finish_document_upload",
    }[operation]
    method, receipts = getattr(device[0], name), []

    def lost(*a, **kw):
        receipts.append(method(*a, **kw))
        raise RuntimeError("synthetic lost response")

    monkeypatch.setattr(device[0], name, lost)
    checked(post(client, device, "/" + operation, request), 500)
    monkeypatch.setattr(device[0], name, method)
    assert checked(post(client_for(device), device, "/" + operation, request)) == {
        **receipts[0],
        "replayed": True,
    }
    assert len(receipts) == 1 and count(device, "canvas_document_uploads") == 1
    assert count(device, "canvas_evidence_observations") == 0


def test_pdf_gaps_from_actual_producer_are_partial_original_evidence(device):
    data = stage(device, raw={"pages": ["", "📚 policy", "", "rubric"]}, partial=True)
    observed = publish(device, data, partial=True)
    result = read(device, observed)
    assert data[3]["unrepresented_pages"] == [1, 3]
    assert [s["page"] for s in result["sections"]] == [2, 4]
    assert result["coverage"] == "partial" and not result["freshness"]["usable"]


def test_partial_pipeline_cannot_start_drafting_model(device):
    observed = publish(device, stage(device, partial=True), partial=True)
    db = device[0]
    duty = db.create_canvas_draft_responsibility(
        "user_alice",
        "Prepare private draft",
        "partial-pipeline",
        object_ids=[observed["object_id"]],
    )
    model = ScriptedModel([])
    assert run_once(db, model, Settings()) and model.histories == []
    assert db.draft_responsibility_status("user_alice", duty["id"])["status"] == "blocked"


def test_unchanged_then_changed_due_date_preserves_document_event_semantics(device):
    roots = []
    for index, due in enumerate(
        ["2026-11-02T00:00:00Z", "2026-11-02T00:00:00Z", "2026-11-03T00:00:00Z"]
    ):
        scan = None if index == 0 else evidence.next_scan(device, "cycle-" + str(index))
        data = stage(device, scan=scan, key=str(index), due=due)
        roots.append(publish(device, data)["document_version_id"])
        assert len(evidence.rows(device, "canvas_evidence_events")) == [1, 1, 2][index]
    assert roots[0] == roots[1] != roots[2]
    assert count(device, "source_versions") == 0


def test_revoke_after_staging_prevents_publication(device):
    data = stage(device)
    device[0].rotate_or_revoke("user_alice", device[1]["connection_id"])
    scan, body, upload, *_ = data
    from shared.source_connections import SourceCredentialRejected

    with pytest.raises(SourceCredentialRejected):
        evidence.upload(device, scan, page(device, scan, body, upload))
    assert count(device, "canvas_evidence_observations") == 0


def test_other_account_cannot_read_published_actual_producer_original(device):
    observed = publish(device, stage(device))
    device[0].provision("user_bob")
    with pytest.raises(LookupError):
        read(device, observed, user="user_bob")
