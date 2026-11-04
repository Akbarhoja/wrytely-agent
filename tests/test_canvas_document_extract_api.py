"""Scoped full-document HTML conversion; no provider IO or stored course content."""

from copy import deepcopy

import pytest
import test_canvas_evidence as evidence
import test_canvas_sync as sync
from test_canvas_document_upload_api import checked, client_for, post
from test_canvas_document_uploads import count
from test_canvas_sync import device as device

import app.canvas_document_api as module


def body(device):
    evidence.prepare(device)
    context = device[0].canvas_connection_context(device[1]["ingestion_bearer"], sync.ORIGIN)
    return {
        "schema_version": 2,
        "operation": "extract_document",
        "origin": sync.ORIGIN,
        "connection_id": context["connection_id"],
        "generation": context["generation"],
        "scope_revision": context["scope_revision"],
        "resource": {"course_id": "101", "kind": "assignments"},
        "items": [{"provider_id": "17", "html": "<p>Full instructions.</p>"}],
    }


def client(device):
    return client_for(device, versions=("canvas.html.v1",))


def test_long_html_is_not_shortened_and_never_executed_or_stored(device):
    request = body(device)
    request["items"][0]["html"] = "<p>" + "x" * 30000 + "</p><script>PRIVATE_SCRIPT</script>"
    response = checked(post(client(device), device, "/extract", request))
    assert len(response["items"][0]["text"]) == 30000
    assert response["extractor_version"] == "canvas.html.v1"
    assert response["items"][0]["coverage"] == "partial"
    assert "PRIVATE_SCRIPT" not in str(response)
    assert "nontext_content_unread" in response["items"][0]["missing"]
    assert (
        count(device, "canvas_document_uploads")
        == count(device, "canvas_evidence_observations")
        == 0
    )


@pytest.mark.parametrize(
    "change", ["course", "kind", "duplicate", "extra", "bool", "items", "origin", "html"]
)
def test_rejects_unsupported_scope_and_invalid_shape(device, change):
    request = body(device)
    status = 400
    if change == "course":
        request["resource"]["course_id"] = "102"
        status = 409
    elif change == "kind":
        request["resource"]["kind"] = "files"
    elif change == "duplicate":
        request["items"] *= 2
    elif change == "extra":
        request["extractor_version"] = "attacker"
    elif change == "bool":
        request["schema_version"] = True
    elif change == "items":
        request["items"] = []
    elif change == "origin":
        request["origin"] = "https://other.example.edu"
        status = 401
    else:
        request["items"][0]["html"] = {"private": "content"}
    response = post(client(device), device, "/extract", request)
    checked(response, status)
    assert "attacker" not in response.text


def test_actual_extractor_version_must_be_configured(device):
    request = body(device)
    checked(post(client_for(device), device, "/extract", request), 503)


@pytest.mark.parametrize("control", ["revoke", "scope"])
def test_current_authority_checked_after_conversion(device, monkeypatch, control):
    request = body(device)
    original = module.extract_html

    def changed(*args, **kwargs):
        result = original(*args, **kwargs)
        if control == "revoke":
            device[0].rotate_or_revoke("user_alice", request["connection_id"])
        else:
            sync.set_scope(device, [], kinds=[])
        return result

    monkeypatch.setattr(module, "extract_html", changed)
    response = post(client(device), device, "/extract", request)
    checked(response, 401 if control == "revoke" else 409)
    assert "Full instructions" not in response.text


def test_missing_and_malformed_body_return_explicit_gaps_not_fabricated_text(device):
    request = body(device)
    request["items"] = [
        {"provider_id": "17", "html": None},
        {"provider_id": "18", "html": "<p><b>broken</p>"},
    ]
    response = checked(post(client(device), device, "/extract", deepcopy(request)))
    assert all(item["text"] == "" and item["coverage"] == "partial" for item in response["items"])
    assert response["items"][1]["missing"] == ["malformed_markup"]


@pytest.mark.parametrize(
    "versions,expected",
    [
        (("canvas.html.v1",), "partial"),
        (("canvas.html.v2",), "complete"),
        (("canvas.html.v1", "canvas.html.v2"), "complete"),
    ],
)
def test_opt_in_v2_is_versioned_without_promoting_v1_or_storing_evidence(
    device, versions, expected
):
    request = body(device)
    result = checked(post(client_for(device, versions=versions), device, "/extract", request))
    item = result["items"][0]
    assert item["coverage"] == expected
    assert item["text"] == "Full instructions."
    assert result["extractor_version"] == (
        "canvas.html.v2" if expected == "complete" else "canvas.html.v1"
    )
    assert item["missing"] == ([] if expected == "complete" else ["html_text_only"])
    assert (
        count(device, "canvas_evidence_observations")
        == count(device, "canvas_document_uploads")
        == 0
    )


@pytest.mark.parametrize(
    "html",
    [
        None,
        '<p>Read <a href="/files/1">attachment</a></p>',
        "<table><tr><td>Required</td></tr></table>",
    ],
)
def test_v2_does_not_certify_missing_linked_or_structural_requirements(device, html):
    request = body(device)
    request["items"][0]["html"] = html
    item = checked(
        post(client_for(device, versions=("canvas.html.v2",)), device, "/extract", request)
    )["items"][0]
    assert item["coverage"] == "partial" and item["missing"]


def test_v2_rechecks_scope_after_conversion(device, monkeypatch):
    request = body(device)
    original = module.extract_html_v2

    def revoke(*args, **kwargs):
        result = original(*args, **kwargs)
        device[0].rotate_or_revoke("user_alice", request["connection_id"])
        return result

    monkeypatch.setattr(module, "extract_html_v2", revoke)
    response = post(client_for(device, versions=("canvas.html.v2",)), device, "/extract", request)
    checked(response, 401)
    assert "Full instructions" not in response.text
