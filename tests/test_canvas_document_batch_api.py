"""Document publication HTTP boundaries using real disposable staging/Store."""

from copy import deepcopy

import pytest
import test_canvas_evidence as evidence
import test_canvas_sync as sync
from test_canvas_document_publication import page, ready
from test_canvas_document_upload_api import ROOT, checked, client_for, post
from test_canvas_document_uploads import count
from test_canvas_sync import device as device


def publication(device):
    scan = evidence.prepare(device)
    body, upload, _ = ready(device, scan)
    envelope = page(device, scan, body, upload)
    return {
        "scan_id": scan["scan_id"],
        "generation": body["generation"],
        "lease_token": scan["lease_token"],
        "batch_key": envelope["batch_key"],
        "expected_checkpoint": scan["checkpoint"],
        "envelope": envelope,
    }


@pytest.mark.parametrize("credential", [None, "Basic alice", "Bearer alice", "Bearer bob"])
def test_publication_requires_device_not_session_credential(device, credential):
    body = publication(device)
    checked(
        client_for(device).post(
            ROOT + "/batch",
            json=body,
            headers={} if credential is None else {"Authorization": credential},
        ),
        401,
    )
    assert count(device, "canvas_evidence_observations") == 0


@pytest.mark.parametrize("mutation", ["extra", "schema1", "boolean", "type", "missing"])
def test_publication_exact_versioned_wrapper(device, mutation):
    body = publication(device)
    if mutation == "extra":
        body["user_id"] = "private-owner"
    elif mutation == "missing":
        del body["expected_checkpoint"]
    elif mutation == "type":
        body["envelope"]["batch_type"] = "canvas_academic"
    else:
        body["envelope"]["schema_version"] = True if mutation == "boolean" else 1
    response = post(client_for(device), device, "/batch", body)
    checked(response, 400)
    assert "private-owner" not in response.text
    assert count(device, "canvas_evidence_observations") == 0


@pytest.mark.parametrize("disabled", ["origins", "extractors", "query"])
def test_publication_configuration_and_query_boundary(device, disabled):
    body = publication(device)
    options = {"origins": ()} if disabled == "origins" else {"versions": ()}
    client = client_for(device, **({} if disabled == "query" else options))
    checked(
        post(client, device, "/batch?owner=private" if disabled == "query" else "/batch", body),
        400 if disabled == "query" else 503,
    )
    assert count(device, "canvas_evidence_observations") == 0


@pytest.mark.parametrize("control", ["revoke", "scope", "lease"])
def test_publication_replay_rechecks_current_authority(device, control):
    body = publication(device)
    client = client_for(device)
    original = checked(post(client, device, "/batch", body))
    assert checked(post(client_for(device), device, "/batch", body)) == {
        **original,
        "replayed": True,
    }
    if control == "revoke":
        device[0].rotate_or_revoke("user_alice", body["envelope"]["connection_id"])
    elif control == "scope":
        sync.set_scope(device, [], kinds=[])
    else:
        with device[0].connection() as conn:
            conn.execute(
                "UPDATE wrytely_agent.canvas_scans SET "
                "lease_expires_at=clock_timestamp()-interval '1 second' WHERE id=%s",
                (body["scan_id"],),
            )
    checked(post(client, device, "/batch", body), 401 if control == "revoke" else 409)
    assert count(device, "canvas_evidence_observations") == 1


def test_publication_unknown_commit_is_replayed_not_retried_in_request(device, monkeypatch):
    body = publication(device)
    original = device[0].commit_sync_batch
    receipts = []

    def lost(*args, **kwargs):
        receipts.append(original(*args, **kwargs))
        raise RuntimeError("private source text")

    monkeypatch.setattr(device[0], "commit_sync_batch", lost)
    response = post(client_for(device), device, "/batch", body)
    assert checked(response, 500) == {"detail": {"code": "document_operation_failed"}}
    assert len(receipts) == 1 and "private source text" not in response.text
    monkeypatch.setattr(device[0], "commit_sync_batch", original)
    assert checked(post(client_for(device), device, "/batch", body)) == {
        **receipts[0],
        "replayed": True,
    }
    changed = deepcopy(body)
    changed["envelope"]["items"][0]["title"] = "Different request"
    checked(post(client_for(device), device, "/batch", changed), 409)
    assert count(device, "canvas_evidence_observations") == 1
