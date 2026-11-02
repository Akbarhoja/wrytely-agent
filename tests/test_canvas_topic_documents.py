"""Real topic document staging/publication without live source calls or inference."""

from copy import deepcopy

import pytest
import test_canvas_evidence as evidence
from test_canvas_document_publication import page
from test_canvas_document_upload_api import checked, client_for, post
from test_canvas_document_uploads import begin_body, count, finish_body, put_body
from test_canvas_sync import device as device


@pytest.mark.parametrize(
    "resource,kind", [("announcements", "announcement"), ("discussions", "discussion")]
)
def test_topic_originals_keep_resource_identity_gaps_replay_and_access_controls(
    device, resource, kind
):
    scan = evidence.prepare(device, kinds=[resource])
    body = begin_body(device, scan)
    body["resource"]["kind"] = resource
    body["owner_object"] = {"kind": kind, "provider_id": "50"}
    body["object_fields"] = (
        {"author_role": None, "posted_at": "2026-11-01T00:00:00Z", "announcement_id": "50"}
        if kind == "announcement"
        else {
            "topic_id": "50",
            "parent_entry_id": None,
            "author_role": None,
            "required_initial_post": True,
            "due_at": None,
        }
    )
    body["metadata"].update(coverage="partial", missing=["linked_content_unread"])
    api = client_for(device)
    upload = checked(post(api, device, "/begin", body))
    checked(post(api, device, "/parts", put_body(body, upload["upload_id"])))
    root = checked(post(api, device, "/finish", finish_body(body, upload["upload_id"])))
    value = page(device, scan, body, upload)
    value["resource"]["kind"] = resource
    value["coverage"].update(state="partial", reason="extraction_failed")
    value["items"][0]["reference"] = "https://canvas.example.edu/courses/101/discussion_topics/50"
    wrapper = {
        "scan_id": scan["scan_id"],
        "generation": body["generation"],
        "lease_token": scan["lease_token"],
        "batch_key": value["batch_key"],
        "expected_checkpoint": scan["checkpoint"],
        "envelope": value,
    }
    published = checked(post(api, device, "/batch", wrapper))
    assert published["observations"][0]["kind"] == kind
    assert published["observations"][0]["document_version_id"] == root["document_version_id"]
    assert checked(post(api, device, "/batch", wrapper)) == {**published, "replayed": True}
    assert count(device, "source_versions") == 0
    assert count(device, "canvas_evidence_observations") == 1
    evidence.close(device, scan, published, partial=True, kind=resource)
    observed = published["observations"][0]
    original = device[0].read_canvas_document_sections(
        "user_alice",
        observed["object_id"],
        observation_id=observed["observation_id"],
        document_version_id=root["document_version_id"],
    )
    assert original["sections"][0]["text"] == "Café\n📚"
    assert not original["freshness"]["usable"]
    device[0].provision("user_bob")
    with pytest.raises(LookupError):
        device[0].read_canvas_document_sections(
            "user_bob",
            observed["object_id"],
            observation_id=observed["observation_id"],
            document_version_id=root["document_version_id"],
        )


def test_new_topic_kind_cannot_be_staged_under_assignment_scope(device):
    scan = evidence.prepare(device)
    body = begin_body(device, scan)
    body["resource"]["kind"] = "discussions"
    body["owner_object"] = {"kind": "discussion", "provider_id": "50"}
    body["object_fields"] = {
        "topic_id": "50",
        "parent_entry_id": None,
        "author_role": None,
        "required_initial_post": True,
        "due_at": None,
    }
    checked(post(client_for(device), device, "/begin", body), 409)
    assert count(device, "canvas_document_uploads") == 0
    wrong = deepcopy(body)
    wrong["resource"]["kind"] = "assignments"
    checked(post(client_for(device), device, "/begin", wrong), 400)
