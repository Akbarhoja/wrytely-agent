"""Actual Node client -> loopback FastAPI -> disposable Store; never a live provider test."""

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
        api = create_app(settings, store=canvas_store, verifier=SessionVerifier())
    injected = False

    @api.middleware("http")
    async def controlled_race(request, call_next):
        nonlocal injected
        if (
            not injected
            and request.url.path.endswith("/discovery/batch")
            and scenario in {"expire_lease", "scope_changed", "revoke"}
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
                if scenario == "revoke":
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
        return await call_next(request)

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
        yield f"http://127.0.0.1:{port}"
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
    node = shutil.which("node")
    assert node is not None, "Node is required for actual client interoperability; never skip"
    assert DRIVER.is_file(), "Actual Node client HTTP acceptance driver is not implemented"
    monkeypatch.setenv("WRYTELY_TEST_PARENT_CANARY", "synthetic-parent-only")
    environment = child_environment()
    assert "WRYTELY_TEST_PARENT_CANARY" not in environment
    completed = subprocess.run(
        [node, str(DRIVER)],
        input=json.dumps({"loopback": interop_service, "scenario": scenario}),
        capture_output=True,
        text=True,
        timeout=45,
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
        assert (
            conn.execute("SELECT count(*) AS n FROM wrytely_agent.source_versions").fetchone()["n"]
            == 0
        )
        if scenario in {"scope_changed", "revoke", "cross_account"}:
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
