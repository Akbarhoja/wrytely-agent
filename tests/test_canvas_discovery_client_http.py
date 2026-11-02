"""Actual Node client -> loopback FastAPI -> disposable Store; never a live provider test."""

import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest
import uvicorn
from test_source_connection_api import ORIGIN, SessionVerifier
from test_source_connection_api import canvas_store as canvas_store

from app.main import create_app
from contracts.source_digest import source_digest
from shared.config import Settings

ROOT = Path(__file__).resolve().parents[1]
DRIVER = ROOT / "extension/canvas-pairing/http-interop.mjs"
SCENARIOS = (
    "lost_before",
    "lost_after",
    "resume_replaced",
    "expire_lease",
    "partial_finish",
    "scope_changed",
    "revoke",
    "cross_account",
    "collector_two_page",
    "collector_lost_after",
    "academic_complete",
    "academic_lost_before",
    "academic_lost_after",
    "academic_partial",
    "academic_scope_changed",
    "academic_revoke",
    "academic_cross_account",
    "assignment_collector_lifecycle",
    "assignment_collector_lost_after",
    "auto_documents_pdf",
    "auto_documents_all",
    "auto_documents_files",
    "auto_documents_modules",
    "auto_documents_replies",
    "auto_documents_replies_lost",
    "auto_documents_status",
    "auto_documents_restricted",
    "auto_documents_topics",
    "auto_documents_lifecycle",
    "auto_documents_lost_batch",
    "document_complete",
    "document_empty",
    "document_syllabus",
    "document_lost_begin",
    "document_lost_parts",
    "document_lost_finish",
    "document_lost_batch",
    "document_many_slots",
    "document_four",
    "document_pagination",
    "document_bad_receipt",
    "document_pending_tamper",
)
ENV_NAMES = {"PATH", "SYSTEMROOT", "WINDIR", "COMSPEC", "PATHEXT", "TEMP", "TMP", "LANG", "LC_ALL"}


def child_environment():
    return {name: value for name, value in os.environ.items() if name.upper() in ENV_NAMES}


@pytest.fixture
def interop_service(canvas_store, scenario, monkeypatch):
    # Settings otherwise reads process env even with _env_file=None. Isolate construction too.
    with monkeypatch.context() as isolated:
        for name in list(os.environ):
            if name.upper() not in ENV_NAMES:
                isolated.delenv(name, raising=False)
        settings = Settings(_env_file=None, canvas_origins=[ORIGIN])
        api = create_app(
            settings,
            store=canvas_store,
            verifier=SessionVerifier(),
            canvas_document_extractors=(
                "canvas.html.v1",
                "canvas.json.v1",
                "canvas.text.v1",
                "canvas.pdf.v1",
            )
            if scenario.startswith("auto_documents_")
            else ("fixture.v1",)
            if scenario.startswith("document_")
            else (),
        )
    injected = False
    snapshots = []

    @api.middleware("http")
    async def controlled_race(request, call_next):
        nonlocal injected
        if not injected and (
            request.url.path.endswith("/discovery/batch")
            and scenario in {"expire_lease", "scope_changed", "revoke"}
            or request.url.path.endswith("/academic/batch")
            and scenario in {"academic_scope_changed", "academic_revoke"}
        ):
            injected = True
            if scenario == "expire_lease":
                with canvas_store.connection() as conn:
                    conn.execute(
                        "UPDATE wrytely_agent.canvas_scans "
                        "SET lease_expires_at=clock_timestamp()-interval '1 second' "
                        "WHERE state='active'"
                    )
            else:
                with canvas_store.connection() as conn:
                    row = conn.execute(
                        "SELECT c.id,c.generation FROM wrytely_agent.source_connections c "
                        "JOIN wrytely_agent.agents a ON a.id=c.agent_id WHERE a.user_id=%s",
                        ("user_alice",),
                    ).fetchone()
                if scenario in {"revoke", "academic_revoke"}:
                    canvas_store.rotate_or_revoke("user_alice", str(row["id"]))
                else:
                    canvas_store.set_canvas_scope(
                        "user_alice",
                        str(row["id"]),
                        row["generation"],
                        mode="explicit_set",
                        course_ids=[],
                        resource_kinds=["assignments"],
                    )
        response = await call_next(request)
        if (
            scenario.startswith("assignment_collector_")
            and request.url.path.endswith("/discovery/finish")
            and response.status_code == 200
        ):
            snapshots.append(collector_snapshot(canvas_store))
        return response

    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    listener.listen(32)
    port = listener.getsockname()[1]
    server = uvicorn.Server(
        uvicorn.Config(
            api,
            host="127.0.0.1",
            port=port,
            loop="asyncio",
            log_config=None,
            access_log=False,
            lifespan="off",
            proxy_headers=False,
        )
    )
    errors = []

    def serve():
        try:
            server.run(sockets=[listener])
        except Exception as exc:  # Fixture startup failure; do not echo exception values.
            errors.append(type(exc).__name__)

    thread = threading.Thread(target=serve, name="canvas-test-http", daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 10
        while not server.started and thread.is_alive() and time.monotonic() < deadline:
            time.sleep(0.01)
        assert server.started and not errors, "Isolated test HTTP service failed to start"
        yield f"http://127.0.0.1:{port}", snapshots
    finally:
        server.should_exit = True
        thread.join(5)
        if thread.is_alive():
            server.force_exit = True
            thread.join(5)
        listener.close()
        assert not thread.is_alive(), "Owned test HTTP service failed to stop"


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_actual_client_http_contract(canvas_store, interop_service, scenario, monkeypatch):
    service_url, snapshots = interop_service
    node = shutil.which("node")
    assert node is not None, "Node is required for actual client interoperability; never skip"
    assert DRIVER.is_file(), "Actual Node client HTTP acceptance driver is not implemented"
    monkeypatch.setenv("WRYTELY_TEST_PARENT_CANARY", "synthetic-parent-only")
    environment = child_environment()
    assert "WRYTELY_TEST_PARENT_CANARY" not in environment
    completed = subprocess.run(
        [node, str(DRIVER)],
        input=json.dumps({"loopback": service_url, "scenario": scenario}),
        capture_output=True,
        text=True,
        # Automatic-document scenarios execute three complete scans, including
        # conversion/upload/publication and original transaction fences. Linux
        # CI's durable Postgres is materially slower than macOS pgserver. Keep
        # a finite four-phase allowance (setup plus three scans), not retries or
        # looser protocol/request deadlines; ordinary one-scan cases stay at45s.
        timeout=180 if scenario.startswith("auto_documents_") else 45,
        cwd=ROOT,
        env=environment,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        check=False,
    )
    assert len(completed.stdout) < 2048, "Child returned an oversized diagnostic"
    summary = json.loads(completed.stdout)
    assert set(summary) <= {"ok", "scenario", "phase", "code"}
    assert completed.returncode == 0 and summary.get("ok") is True, (
        f"Synthetic interop failed: {summary}; stderr_bytes={len(completed.stderr)}"
    )
    assert summary == {"ok": True, "scenario": scenario}
    with canvas_store.connection() as conn:
        catalog = conn.execute("SELECT count(*) AS n FROM wrytely_agent.canvas_catalog").fetchone()[
            "n"
        ]
        batches = conn.execute(
            "SELECT count(*) AS n FROM wrytely_agent.canvas_sync_receipts WHERE operation='batch'"
        ).fetchone()["n"]
        versions = conn.execute(
            "SELECT count(*) AS n FROM wrytely_agent.source_versions"
        ).fetchone()["n"]
        if scenario.startswith("auto_documents_"):
            assert (
                versions == 0
                and catalog == 2
                and batches
                == (
                    99
                    if scenario == "auto_documents_all"
                    else 33
                    if scenario in {"auto_documents_files", "auto_documents_pdf"}
                    else 63
                    if scenario.startswith("auto_documents_replies")
                    else 39
                    if scenario
                    in {"auto_documents_topics", "auto_documents_status", "auto_documents_modules"}
                    else 24
                    if scenario == "auto_documents_restricted"
                    else 27
                )
            )
            assert conn.execute(
                "SELECT count(*) AS n FROM wrytely_agent.canvas_evidence_observations"
            ).fetchone()["n"] == (
                156
                if scenario == "auto_documents_all"
                else 36
                if scenario in {"auto_documents_files", "auto_documents_pdf"}
                else 120
                if scenario.startswith("auto_documents_replies")
                else 42
                if scenario
                in {"auto_documents_topics", "auto_documents_status", "auto_documents_modules"}
                else 27
                if scenario == "auto_documents_restricted"
                else 30
            )
            assert conn.execute(
                "SELECT count(*) AS n FROM wrytely_agent.canvas_evidence_events"
            ).fetchone()["n"] == (
                57
                if scenario == "auto_documents_all"
                else 13
                if scenario == "auto_documents_pdf"
                else 15
                if scenario == "auto_documents_files"
                else 42
                if scenario.startswith("auto_documents_replies")
                else 16
                if scenario == "auto_documents_status"
                else 15
                if scenario in {"auto_documents_topics", "auto_documents_modules"}
                else 10
                if scenario == "auto_documents_restricted"
                else 11
            )
            assert conn.execute(
                "SELECT count(*) AS n FROM wrytely_agent.canvas_document_versions"
            ).fetchone()["n"] == (
                57
                if scenario == "auto_documents_all"
                else 13
                if scenario == "auto_documents_pdf"
                else 15
                if scenario == "auto_documents_files"
                else 42
                if scenario.startswith("auto_documents_replies")
                else 16
                if scenario == "auto_documents_status"
                else 15
                if scenario in {"auto_documents_topics", "auto_documents_modules"}
                else 10
                if scenario == "auto_documents_restricted"
                else 11
            )
            text = conn.execute(
                "SELECT text FROM wrytely_agent.canvas_document_sections "
                "ORDER BY length(text) DESC LIMIT 1"
            ).fetchone()["text"]
            assert "PRIVATE_SCRIPT" not in text
            long_root = conn.execute(
                "SELECT total_characters FROM wrytely_agent.canvas_document_versions "
                "ORDER BY total_characters DESC LIMIT 1"
            ).fetchone()["total_characters"]
            assert long_root > 24000
            rubric = conn.execute(
                "SELECT payload->'fields'->'object_fields'->'rubric' AS rubric "
                "FROM wrytely_agent.canvas_evidence_observations "
                "WHERE resource_key LIKE '%%/assignments' LIMIT 1"
            ).fetchone()["rubric"]
            assert rubric[0]["description"] == "Explain evidence"
            if scenario.startswith("auto_documents_replies"):
                entry_rows = conn.execute(
                    "SELECT payload FROM wrytely_agent.canvas_evidence_observations "
                    "WHERE payload->'fields'->>'owner_kind'='entry'"
                ).fetchall()
                assert len(entry_rows) == 84
                parents = [
                    row["payload"]["fields"]["object_fields"]["parent_entry_id"]
                    for row in entry_rows
                ]
                assert parents.count(None) == 12
                assert parents.count("1010") == 36 and parents.count("1020") == 36
                texts = conn.execute(
                    "SELECT text FROM wrytely_agent.canvas_document_sections"
                ).fetchall()
                assert "PRIVATE_RECENT_SAMPLE_ONLY" not in json.dumps(texts)
                assert any("Reply 10112" in row["text"] for row in texts)
                assert any("Reply 10101 changed" in row["text"] for row in texts)
            if scenario == "auto_documents_pdf":
                originals = conn.execute(
                    "SELECT text FROM wrytely_agent.canvas_document_sections"
                ).fetchall()
                assert "Synthetic syllabus." in json.dumps(originals)
                roots = conn.execute(
                    "SELECT count(*) AS n FROM wrytely_agent.canvas_document_versions "
                    "WHERE format='pdf_text'"
                ).fetchone()
                assert roots["n"] == 2
            if scenario in {"auto_documents_status", "auto_documents_all"}:
                rows = conn.execute(
                    "SELECT payload FROM wrytely_agent.canvas_evidence_observations "
                    "WHERE resource_key IN ('101/grades','102/grades',"
                    "'101/submissions','102/submissions')"
                ).fetchall()
                serialized = json.dumps(rows)
                assert (
                    "PRIVATE_SUBMISSION_BODY" not in serialized
                    and "PRIVATE_FEEDBACK" not in serialized
                )
                assert "user_id" not in serialized
                contents = json.dumps(
                    conn.execute(
                        "SELECT text FROM wrytely_agent.canvas_document_sections"
                    ).fetchall()
                )
                assert "OWN_SUBMISSION_BODY" in contents and "OWN_FEEDBACK" in contents
                assert "PRIVATE_SCRIPT" not in contents
                scores = [row["payload"]["fields"]["object_fields"].get("score") for row in rows]
                assert "12" in scores and "18" in scores
        elif scenario.startswith("document_"):
            assert versions == 0
            observations = conn.execute(
                "SELECT count(*) AS n FROM wrytely_agent.canvas_evidence_observations"
            ).fetchone()["n"]
            assert observations == (
                0
                if scenario in {"document_pending_tamper", "document_empty"}
                else 4
                if scenario == "document_four"
                else 5
                if scenario == "document_pagination"
                else 1
            )
            assert batches == (
                2
                if scenario == "document_pending_tamper"
                else 4
                if scenario == "document_pagination"
                else 3
            )
        elif scenario.startswith("assignment_collector_"):
            assert catalog == 2 and batches == 12 and versions == 3
            assert_collector_lifecycle(conn, snapshots)
        elif scenario.startswith("academic_"):
            assert_academic_state(conn, scenario, catalog, batches, versions)
        elif scenario.startswith("collector_"):
            assert catalog == batches == 2
            courses = conn.execute(
                "SELECT course_id,payload->>'coverage' AS coverage "
                "FROM wrytely_agent.canvas_catalog ORDER BY course_id"
            ).fetchall()
            assert [(row["course_id"], row["coverage"]) for row in courses] == [
                ("101", "complete"),
                ("102", "complete"),
            ]
            resources = conn.execute(
                "SELECT resource_key,coverage FROM wrytely_agent.canvas_resources "
                "ORDER BY resource_key"
            ).fetchall()
            assert [(row["resource_key"], row["coverage"]) for row in resources] == [
                ("101/assignments", "open"),
                ("102/assignments", "open"),
                ("courses", "complete"),
            ]
            scan = conn.execute(
                "SELECT state,checkpoint FROM wrytely_agent.canvas_scans"
            ).fetchone()
            assert scan["state"] == "active"
            assert scan["checkpoint"]["sequence"] == 2
            assert scan["checkpoint"]["next_cursor"] is None
            assert (
                conn.execute(
                    "SELECT count(*) AS n FROM wrytely_agent.canvas_sync_receipts "
                    "WHERE operation='finish'"
                ).fetchone()["n"]
                == 0
            )
        elif scenario in {"scope_changed", "revoke", "cross_account"}:
            assert catalog == batches == 0
        else:
            assert catalog == (2 if scenario == "partial_finish" else 1)
            assert (
                conn.execute(
                    "SELECT count(DISTINCT course_id) AS n FROM wrytely_agent.canvas_catalog"
                ).fetchone()["n"]
                == 1
            )
            assert batches == (2 if scenario == "partial_finish" else 1)
        if scenario == "partial_finish":
            rows = conn.execute(
                "SELECT coverage FROM wrytely_agent.canvas_resources "
                "WHERE resource_key='101/assignments'"
            ).fetchall()
            assert [row["coverage"] for row in rows] == ["unsupported"]
        if not scenario.startswith(("academic_", "assignment_collector_")):
            assert versions == 0


def collector_snapshot(store):
    """Read actual committed state after each successful finish, not child-reported counts."""
    with store.connection() as conn:
        result = {}
        for key, table in (
            ("versions", "source_versions"),
            ("events", "canvas_evidence_events"),
            ("observations", "canvas_evidence_observations"),
        ):
            result[key] = conn.execute(
                f"SELECT count(*) AS n FROM wrytely_agent.{table}"
            ).fetchone()["n"]
        result["version_ids"] = {
            row["id"]
            for row in conn.execute("SELECT id FROM wrytely_agent.source_versions").fetchall()
        }
        result["event_ids"] = {
            row["id"]
            for row in conn.execute(
                "SELECT id FROM wrytely_agent.canvas_evidence_events"
            ).fetchall()
        }
        result["object_count"] = conn.execute(
            "SELECT count(*) AS n FROM wrytely_agent.canvas_evidence_objects"
        ).fetchone()["n"]
        result["immutable"] = conn.execute(
            "SELECT v.id,v.external_revision,p.content_digest,p.payload FROM "
            "wrytely_agent.source_versions v LEFT JOIN "
            "wrytely_agent.canvas_evidence_payloads p ON p.version_id=v.id "
            "AND p.agent_id=v.agent_id"
        ).fetchall()
        result["objects"] = conn.execute(
            "SELECT o.id,o.course_id,o.provider_id,o.complete_version_id,"
            "obs.id AS observation_id,obs.version_id,obs.payload,"
            "obs.content_digest,v.reference,v.content,a.user_id,c.origin FROM "
            "wrytely_agent.canvas_evidence_objects o JOIN "
            "wrytely_agent.canvas_evidence_observations obs ON obs.id=o.latest_observation_id JOIN "
            "wrytely_agent.source_versions v ON v.id=obs.version_id AND v.agent_id=o.agent_id JOIN "
            "wrytely_agent.agents a ON a.id=o.agent_id JOIN "
            "wrytely_agent.source_connections c ON c.id=o.connection_id ORDER BY o.course_id"
        ).fetchall()
        result["promoted"] = conn.execute(
            "SELECT count(*) AS n FROM wrytely_agent.academic_sources "
            "WHERE latest_version_id IS NOT NULL"
        ).fetchone()["n"]
        return result


def assert_collector_lifecycle(conn, snapshots):
    assert len(snapshots) == 3
    assert [(s["versions"], s["events"], s["observations"]) for s in snapshots] == [
        (2, 2, 2),
        (2, 2, 4),
        (3, 3, 6),
    ]
    assert snapshots[0]["version_ids"] == snapshots[1]["version_ids"]
    assert snapshots[0]["event_ids"] == snapshots[1]["event_ids"]
    assert snapshots[1]["version_ids"] < snapshots[2]["version_ids"]
    assert snapshots[1]["event_ids"] < snapshots[2]["event_ids"]
    original_objects = [row["id"] for row in snapshots[0]["objects"]]
    expected_versions = {}
    for cycle, snapshot in enumerate(snapshots):
        assert snapshot["promoted"] == 0
        assert snapshot["object_count"] == 2
        assert [row["id"] for row in snapshot["objects"]] == original_objects
        assert len(snapshot["objects"]) == 2
        for index, row in enumerate(snapshot["objects"], 17):
            course = str(index + 84)
            due = (
                "2026-11-03T05:59:00.000000Z"
                if cycle == 2 and index == 17
                else "2026-11-02T05:59:00.000000Z"
            )
            payload = {
                "digest_version": 1,
                "kind": "assignment",
                "title": f"Synthetic collection assignment {index}",
                "content": f"Read carefully for course {course}\nReference",
                "fields": {
                    "due_at": due,
                    "unlock_at": None,
                    "lock_at": None,
                    "points_possible": "20",
                    "submission_types": ["online_upload"],
                    "rubric": [],
                    "published": True,
                },
                "coverage": "partial",
                "missing": ["html_text_only", "linked_content_unread", "nontext_content_unread"],
            }
            assert row["course_id"] == course and row["provider_id"] == str(index)
            assert row["payload"] == payload and row["content_digest"] == source_digest(payload)
            assert row["reference"] == f"{ORIGIN}/courses/{course}/assignments/{index}"
            assert row["content"] == payload["content"]
            assert row["user_id"] == "user_alice" and row["origin"] == ORIGIN
            assert row["complete_version_id"] is None
            if row["version_id"] in expected_versions:
                assert expected_versions[row["version_id"]] == payload
            else:
                expected_versions[row["version_id"]] = payload
        assert len(snapshot["immutable"]) == snapshot["versions"]
        assert {v["id"] for v in snapshot["immutable"]} == set(expected_versions)
        for version in snapshot["immutable"]:
            expected_payload = expected_versions[version["id"]]
            assert version["payload"] == expected_payload
            assert (
                version["external_revision"]
                == version["content_digest"]
                == source_digest(expected_payload)
            )
    for index in (0, 1):
        assert (
            snapshots[0]["objects"][index]["version_id"]
            == snapshots[1]["objects"][index]["version_id"]
        )
    assert snapshots[1]["objects"][0]["version_id"] != snapshots[2]["objects"][0]["version_id"]
    assert snapshots[1]["objects"][1]["version_id"] == snapshots[2]["objects"][1]["version_id"]
    events = conn.execute(
        "SELECT kind FROM wrytely_agent.canvas_evidence_events ORDER BY kind"
    ).fetchall()
    assert [row["kind"] for row in events] == [
        "source_changed",
        "source_observed",
        "source_observed",
    ]
    changed_events = conn.execute(
        "SELECT object_id,observation_id FROM wrytely_agent.canvas_evidence_events "
        "WHERE kind='source_changed'"
    ).fetchall()
    changed = snapshots[2]["objects"][0]
    assert len(changed_events) == 1
    assert changed_events[0]["object_id"] == changed["id"]
    assert changed_events[0]["observation_id"] == changed["observation_id"]
    resources = conn.execute(
        "SELECT resource_key,coverage,seen_count FROM wrytely_agent.canvas_resources "
        "ORDER BY resource_key"
    ).fetchall()
    assert [(r["resource_key"], r["coverage"], r["seen_count"]) for r in resources] == [
        ("101/assignments", "partial", 1)
    ] * 3 + [("102/assignments", "partial", 1)] * 3 + [("courses", "complete", 2)] * 3
    scans = conn.execute(
        "SELECT state,checkpoint FROM wrytely_agent.canvas_scans ORDER BY sequence"
    ).fetchall()
    assert len(scans) == 3
    for scan in scans:
        assert scan["state"] == "finished"
        assert (
            scan["checkpoint"]["sequence"] == 4
            and scan["checkpoint"]["resource"] == "102/assignments"
        )
        assert scan["checkpoint"]["next_cursor"] is None
    finishes = conn.execute(
        "SELECT response FROM wrytely_agent.canvas_sync_receipts WHERE operation='finish'"
    ).fetchall()
    assert len(finishes) == 3
    assert all(row["response"]["coverage"] == "partial" for row in finishes)


def assert_academic_state(conn, scenario, catalog, batches, versions):
    denied = scenario in {"academic_scope_changed", "academic_revoke"}
    # A scope revision copies the prior catalog into the new generation; preserve history.
    assert catalog == (2 if scenario == "academic_scope_changed" else 1)
    assert (
        conn.execute(
            "SELECT count(DISTINCT course_id) AS n FROM wrytely_agent.canvas_catalog"
        ).fetchone()["n"]
        == 1
    )
    assert batches == (1 if denied else 3)
    assert versions == (0 if denied else 2)
    observations = conn.execute(
        "SELECT obj.provider_id,obj.subject_digest,obs.coverage,obs.historical,obs.payload,"
        "obs.content_digest,obs.version_id,v.reference AS version_reference,"
        "v.content AS version_content,a.user_id,c.origin FROM "
        "wrytely_agent.canvas_evidence_observations obs JOIN "
        "wrytely_agent.canvas_evidence_objects obj ON obj.id=obs.object_id JOIN "
        "wrytely_agent.source_versions v ON v.id=obs.version_id AND v.agent_id=obs.agent_id JOIN "
        "wrytely_agent.source_connections c ON c.id=obj.connection_id AND c.agent_id=obj.agent_id "
        "JOIN wrytely_agent.agents a ON a.id=obj.agent_id ORDER BY obj.provider_id"
    ).fetchall()
    assert len(observations) == versions
    objects = conn.execute(
        "SELECT course_id,kind,provider_id FROM wrytely_agent.canvas_evidence_objects "
        "ORDER BY provider_id"
    ).fetchall()
    assert len(objects) == versions
    if denied:
        assert not observations and not objects
        assert (
            conn.execute("SELECT state FROM wrytely_agent.canvas_scans").fetchone()["state"]
            == "aborted"
        )
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM wrytely_agent.canvas_sync_receipts "
                "WHERE operation='finish'"
            ).fetchone()["n"]
            == 0
        )
        return
    assert [(row["course_id"], row["kind"], row["provider_id"]) for row in objects] == [
        ("101", "assignment", "17"),
        ("101", "assignment", "18"),
    ]
    expected_items = []
    for index, row in enumerate(observations, 17):
        assert row["provider_id"] == str(index)
        assert row["version_id"] is not None and row["historical"] is False
        payload = row["payload"]
        partial = scenario == "academic_partial" and index == 17
        expected_payload = {
            "digest_version": 1,
            "kind": "assignment",
            "title": f"Synthetic assignment {index}",
            "content": f"Synthetic extracted instructions {index}",
            "fields": {
                "due_at": "2026-11-02T05:59:00.000000Z",
                "unlock_at": None,
                "lock_at": None,
                "points_possible": "20",
                "submission_types": ["online_upload"],
                "rubric": None if partial else [],
                "published": True,
            },
            "coverage": "partial" if partial else "complete",
            "missing": ["rubric_not_observed"] if partial else [],
        }
        assert payload == expected_payload
        expected_digest = source_digest(expected_payload)
        assert row["content_digest"] == expected_digest
        assert row["version_reference"] == f"{ORIGIN}/courses/101/assignments/{index}"
        assert row["version_content"] == expected_payload["content"]
        assert row["user_id"] == "user_alice" and row["origin"] == ORIGIN
        assert row["subject_digest"] == hashlib.sha256(b"7").hexdigest()
        expected_items.append(
            {
                "kind": "assignment",
                "provider_id": str(index),
                "content_digest": expected_digest,
            }
        )
        assert "excluded raw HTML" not in json.dumps(payload)
        assert row["coverage"] == expected_payload["coverage"]
    assert (
        conn.execute(
            "SELECT count(*) AS n FROM wrytely_agent.academic_sources "
            "WHERE latest_version_id IS NOT NULL"
        ).fetchone()["n"]
        == 0
    )
    sources = conn.execute(
        "SELECT reference,content FROM wrytely_agent.source_versions ORDER BY reference"
    ).fetchall()
    assert [(row["reference"], row["content"]) for row in sources] == [
        (f"{ORIGIN}/courses/101/assignments/{index}", f"Synthetic extracted instructions {index}")
        for index in (17, 18)
    ]
    resources = conn.execute(
        "SELECT resource_key,coverage,seen_count FROM wrytely_agent.canvas_resources "
        "ORDER BY resource_key"
    ).fetchall()
    expected = "partial" if scenario == "academic_partial" else "complete"
    assert [(row["resource_key"], row["coverage"], row["seen_count"]) for row in resources] == [
        ("101/assignments", expected, 2),
        ("courses", "complete", 1),
    ]
    scan = conn.execute("SELECT state,checkpoint FROM wrytely_agent.canvas_scans").fetchone()
    assert scan["state"] == "finished"
    assert scan["checkpoint"]["resource"] == "101/assignments"
    assert scan["checkpoint"]["sequence"] == 3
    assert scan["checkpoint"]["next_cursor"] is None
    assert (
        conn.execute(
            "SELECT count(*) AS n FROM wrytely_agent.canvas_sync_receipts WHERE operation='finish'"
        ).fetchone()["n"]
        == 1
    )
    receipts = conn.execute(
        "SELECT response FROM wrytely_agent.canvas_sync_receipts WHERE operation='resource'"
    ).fetchall()
    assert len(receipts) == 2
    assignment_receipt = next(
        row["response"] for row in receipts if row["response"]["resource_key"] == "101/assignments"
    )
    manifest = assignment_receipt["source_manifest_digest"]
    assert assignment_receipt["coverage"] == expected
    if expected == "complete":
        items = conn.execute(
            "SELECT kind,provider_id,content_digest FROM wrytely_agent.canvas_resource_items "
            "WHERE resource_key='101/assignments' ORDER BY kind,provider_id"
        ).fetchall()
        assert items == expected_items
        expected_manifest = hashlib.sha256(
            json.dumps(
                expected_items, sort_keys=True, separators=(",", ":"), ensure_ascii=False
            ).encode()
        ).hexdigest()
        assert manifest == expected_manifest
    else:
        assert manifest is None
    done = conn.execute(
        "SELECT response FROM wrytely_agent.canvas_sync_receipts WHERE operation='finish'"
    ).fetchone()["response"]
    assert done["coverage"] == expected
