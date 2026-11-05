"""Real Store/worker/JSON SDK wire and checks; all model responses are synthetic."""

import json
from copy import deepcopy
from decimal import Decimal
from io import BytesIO
from zipfile import ZipFile

import httpx
import pytest
from openai import OpenAI
from test_artifacts import assessment
from test_canvas_sync import device as device
from test_drafting import permitted, structured
from test_fireworks_model import reply
from test_typed_document_drafting import planner_stage, prepared

from runtime.artifact_rendering import ArtifactNotReady, render_private_artifact_docx
from runtime.worker import run_once
from shared.budgeted_model import BudgetedModelClient
from shared.canvas_reads import SourceRefreshRequired
from shared.config import Settings
from shared.db import Store
from shared.fireworks_model import FireworksModelClient


def json_provider(turns):
    responses = iter(turns)
    requests = []

    def provider(request):
        body = json.loads(request.content)
        requests.append(body)
        assert body["response_format"] == {"type": "json_object"}
        assert "tools" not in body
        assert '"name"' in body["messages"][0]["content"]
        result = next(responses)
        if isinstance(result, str):
            content = result
        else:
            content = json.dumps(
                {
                    "text": result.text,
                    "actions": [
                        {"name": c["name"], "arguments": json.loads(c["arguments"])}
                        for c in result.output
                        if c["type"] == "function_call"
                    ],
                }
            )
        return httpx.Response(200, json=reply(content=content))

    model = FireworksModelClient(
        Settings(
            fireworks_api_key="synthetic-not-a-real-key",
            fireworks_action_mode="json",
            meta_reasoning_effort="low",
        )
    )
    model._client.close()
    model._client = OpenAI(
        api_key="synthetic-not-a-real-key",
        base_url="https://example.test/v1",
        max_retries=0,
        http_client=httpx.Client(transport=httpx.MockTransport(provider)),
    )
    return model, requests


def budgeted(db, model):
    db.configure_model_budget("json-draft-test", ceiling_usd="2", opening_liability_usd="1.32")
    db.grant_model_budget("json-draft-test", "user_alice", ceiling_usd="0.50")
    return BudgetedModelClient(
        db,
        model,
        "user_alice",
        "json-draft-test",
        input_usd_per_million="1.25",
        output_usd_per_million="4.25",
    )


def text(file):
    with ZipFile(BytesIO(file.content)) as archive:
        return archive.read("word/document.xml").decode()


def test_json_draft_checked_revision_and_private_word_bytes_share_original_runtime(device):
    db = device[0]
    data = prepared(device)
    planner_stage(device, data)
    revised = deepcopy(data[3])
    revised["title"] = "Revised synthetic comparison"
    provider, requests = json_provider(
        [
            permitted(),
            structured("save_review_draft", data[3]),
            assessment(),
            permitted(),
            structured("save_review_draft", revised),
            assessment(),
        ]
    )
    wrapped = budgeted(db, provider)
    try:
        assert run_once(db, wrapped, Settings())
        artifacts = db.list_private_artifacts_v2("user_alice", data[0]["id"])["artifacts"]
        assert len(artifacts) == 1
        parent = artifacts[0]["id"]
        first = render_private_artifact_docx(db, "user_alice", parent)
        assert "Private review" in text(first)
        revision = db.request_private_artifact_revision(
            "user_alice", parent, "Use a clearer title", "json-revision-one"
        )
        assert (
            db.request_private_artifact_revision(
                "user_alice", parent, "Use a clearer title", "json-revision-one"
            )
            == revision
        )
        restarted = Store(db._url, canvas_origins=tuple(db._canvas_origins))
        assert run_once(restarted, wrapped, Settings())
        with db.connection() as conn:
            child = conn.execute(
                "SELECT id,state FROM wrytely_agent.artifacts WHERE task_id=%s",
                (revision["task_id"],),
            ).fetchone()
            reservations = conn.execute(
                "SELECT state,liability_usd FROM wrytely_agent.model_call_reservations "
                "WHERE budget_id='json-draft-test'"
            ).fetchall()
        assert child["state"] == "ready" and str(child["id"]) != parent
        second = render_private_artifact_docx(db, "user_alice", child["id"])
        assert "Revised synthetic comparison" in text(second)
        assert second.content != first.content
        assert render_private_artifact_docx(db, "user_alice", parent).content == first.content
        assert len(requests) == 6 and len(reservations) == 6
        assert all(row["state"] == "settled" for row in reservations)
        assert sum(row["liability_usd"] for row in reservations) < Decimal("0.50")
        assert not run_once(restarted, wrapped, Settings())
        db.provision("user_bob")
        with pytest.raises(LookupError):
            render_private_artifact_docx(db, "user_bob", child["id"])
        db.set_paused("user_alice", True)
        with pytest.raises((SourceRefreshRequired, ArtifactNotReady)):
            render_private_artifact_docx(db, "user_alice", child["id"])
    finally:
        provider._client.close()


def test_invalid_json_action_blocks_real_work_and_keeps_unknown_cost_without_draft(device):
    db = device[0]
    data = prepared(device)
    planner_stage(device, data)
    provider, requests = json_provider(
        ['{"text":"","actions":[{"name":"send_arbitrary_file","arguments":{}}]}']
    )
    wrapped = budgeted(db, provider)
    try:
        assert run_once(db, wrapped, Settings())
        assert db.list_private_artifacts_v2("user_alice", data[0]["id"])["artifacts"] == []
        with db.connection() as conn:
            reservation = conn.execute(
                "SELECT state,liability_usd FROM wrytely_agent.model_call_reservations "
                "WHERE budget_id='json-draft-test'"
            ).fetchone()
            task = conn.execute(
                "SELECT status FROM wrytely_agent.tasks WHERE kind='academic'"
            ).fetchone()
        assert reservation["state"] == "unknown" and reservation["liability_usd"] > 0
        assert task["status"] == "blocked"
        assert not run_once(db, wrapped, Settings()) and len(requests) == 1
    finally:
        provider._client.close()
