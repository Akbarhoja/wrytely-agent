"""Actual private HTML adapter, synthetic HTML and disposable Store only."""

import json

import pytest
from test_canvas_academic_sync_api import prepared
from test_source_connection_api import CANVAS, ORIGIN, auth
from test_source_connection_api import canvas_store as canvas_store

PATH = CANVAS + "/academic/extract"


def extraction(linked):
    return {
        "origin": ORIGIN,
        "connection_id": linked["connection_id"],
        "generation": linked["generation"],
        "scope_revision": linked["scope_revision"],
        "course_id": "101",
        "items": [{"assignment_id": "17", "html": "<p>Read <strong>carefully</strong></p>"}],
    }


def test_private_extraction_reuses_inert_parser_and_never_writes_sources(canvas_store):
    client, linked, _ = prepared(canvas_store)
    result = client.post(PATH, headers=auth(linked["ingestion_bearer"]), json=extraction(linked))
    assert result.status_code == 200
    assert result.headers["cache-control"] == "no-store"
    assert result.json() == {
        "course_id": "101",
        "items": [
            {
                "assignment_id": "17",
                "text": "Read carefully",
                "coverage": "partial",
                "missing": ["html_text_only"],
            }
        ],
    }
    with canvas_store.connection() as conn:
        assert (
            conn.execute("SELECT count(*) AS n FROM wrytely_agent.source_versions").fetchone()["n"]
            == 0
        )
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM wrytely_agent.canvas_evidence_observations"
            ).fetchone()["n"]
            == 0
        )


@pytest.mark.parametrize(
    "field,value,status",
    [
        ("course_id", "102", 409),
        ("generation", 999, 409),
        ("scope_revision", 999, 409),
        ("origin", "https://evil.example", 401),
        ("course_id", 101, 422),
    ],
)
def test_extraction_fences_posted_context(canvas_store, field, value, status):
    client, linked, _ = prepared(canvas_store)
    body = extraction(linked)
    body[field] = value
    result = client.post(PATH, headers=auth(linked["ingestion_bearer"]), json=body)
    assert result.status_code == status
    assert "carefully" not in result.text


@pytest.mark.parametrize(
    "html,text,reason",
    [
        ("<p>Visible</p><script>PRIVATE_SCRIPT</script>", "Visible", "nontext_content_unread"),
        ("<p><a href='/private'>Read</a></p>", "Read", "linked_content_unread"),
        ("<p hidden>PRIVATE_HIDDEN</p><p>Visible</p>", "Visible", "hidden_content_omitted"),
        ("<p><b>broken</p>", "", "malformed_markup"),
        (None, "", "description_not_observed"),
        ("x" * 24001, "", "resource_limit"),
    ],
)
def test_extraction_preserves_coverage_gaps(canvas_store, html, text, reason):
    client, linked, _ = prepared(canvas_store)
    body = extraction(linked)
    body["items"][0]["html"] = html
    result = client.post(PATH, headers=auth(linked["ingestion_bearer"]), json=body)
    assert result.status_code == 200
    item = result.json()["items"][0]
    assert item["text"] == text and item["coverage"] == "partial"
    assert reason in item["missing"]
    assert "PRIVATE_" not in result.text


def test_extraction_rejects_wrong_credential_duplicate_items_and_limits(canvas_store):
    client, linked, _ = prepared(canvas_store)
    body = extraction(linked)
    assert client.post(PATH, headers=auth("alice"), json=body).status_code == 401
    body["items"] *= 2
    assert client.post(PATH, headers=auth(linked["ingestion_bearer"]), json=body).status_code == 422
    body = extraction(linked)
    body["items"][0]["html"] = "x" * (1024 * 1024 + 1)
    assert client.post(PATH, headers=auth(linked["ingestion_bearer"]), json=body).status_code == 422
    body = extraction(linked)
    body["items"][0]["html"] = "\ud800"
    assert (
        client.post(
            PATH,
            headers={**auth(linked["ingestion_bearer"]), "Content-Type": "application/json"},
            content=json.dumps(body),
        ).status_code
        == 422
    )


def test_extraction_rechecks_scope_after_conversion(canvas_store, monkeypatch):
    from app import canvas_sync_api

    client, linked, _ = prepared(canvas_store)
    original = canvas_sync_api.extract_html

    def changed(*args, **kwargs):
        result = original(*args, **kwargs)
        canvas_store.set_canvas_scope(
            "user_alice",
            linked["connection_id"],
            linked["generation"],
            mode="explicit_set",
            course_ids=[],
            resource_kinds=["assignments"],
        )
        return result

    monkeypatch.setattr(canvas_sync_api, "extract_html", changed)
    result = client.post(PATH, headers=auth(linked["ingestion_bearer"]), json=extraction(linked))
    assert result.status_code == 409 and "carefully" not in result.text
