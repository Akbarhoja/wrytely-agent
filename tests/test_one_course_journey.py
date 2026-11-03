"""Synthetic course + scripted models + simulated receipts; no live provider proof.

Exercise one connected journey through the real Store/HTTP/runtime/renderer rather
than treating separate component tests as an end-to-end student experience.
"""

from copy import deepcopy
from datetime import UTC, datetime, timedelta
from uuid import UUID

import httpx
import pytest
from test_artifacts import assessment
from test_canvas_sync import device as device
from test_course_supervision import Model, decision
from test_course_supervision_api import ROOT, checked, client
from test_delivery_store import ACCOUNT, PHONE, status
from test_drafting import permitted, structured
from test_planner import plan
from test_source_connection_api import auth
from test_typed_document_drafting import (
    CLAIM,
    DISCLOSURE,
    POLICY,
    RUBRIC,
    TEXT,
    publish,
    ref,
    requirements,
)
from test_worker import ScriptedModel

from integrations.whatsapp import WhatsAppAdapter, WhatsAppText
from integrations.whatsapp_delivery import run_once as dispatch_once
from runtime.artifact_rendering import ArtifactNotReady, render_private_artifact_docx
from runtime.supervisor import run_course_supervision_once
from runtime.worker import run_once
from shared.budgeted_model import BudgetedModelClient
from shared.canvas_reads import SourceRefreshRequired
from shared.config import Settings


def bound(db, model):
    return BudgetedModelClient(
        db, model, "user_alice", "journey", input_usd_per_million="1", output_usd_per_million="2"
    )


def test_one_course_offer_accept_checked_file_revision_and_new_deadline(device):
    db = device[0]
    deadline = datetime.now(UTC) + timedelta(days=1)
    observed, _ = publish(device, due=deadline.isoformat())
    api = client(device)
    monitor = checked(
        api.post(
            ROOT,
            headers=auth(),
            json={
                "connection_id": str(device[1]["connection_id"]),
                "course_id": "101",
                "call_limit": 12,
            },
        )
    )
    token = db.create_whatsapp_challenge("user_alice")["message"]
    db.ingest_whatsapp(WhatsAppText("link-journey", PHONE, token))
    # Synthetic trusted timestamp fixture; actual signature/ingress tested separately.
    with db.connection() as conn:
        conn.execute("UPDATE wrytely_agent.channel_links SET last_event_at=now()")
    db.set_communication_preferences(
        "user_alice", consent=True, timezone="UTC", quiet_start=0, quiet_end=0
    )
    checked(
        api.post(f"{ROOT}/{monitor['id']}/notifications", headers=auth(), json={"consent": True})
    )
    db.configure_model_budget("journey", ceiling_usd="1", opening_liability_usd="0")
    db.grant_model_budget("journey", "user_alice", ceiling_usd="1")
    run_course_supervision_once(
        db,
        bound(db, Model(decision("inspect", observed["object_id"]))),
        "user_alice",
        monitor["id"],
    )
    run_course_supervision_once(
        db,
        bound(
            db,
            Model(
                decision(
                    "offer",
                    observed["object_id"],
                    "This comparison is due tomorrow. Prepare a checked draft?",
                )
            ),
        ),
        "user_alice",
        monitor["id"],
    )
    offer = checked(api.get(f"{ROOT}/{monitor['id']}", headers=auth()))["offers"][0]
    recovery = db.pending_course_offer_deliveries(limit=1)[0]
    action = db.enqueue_course_offer(
        recovery["user_id"], recovery["supervision_id"], recovery["offer_id"]
    )
    assert db.pending_course_offer_deliveries() == []
    # Exercise the real typed transport assembler with simulated HTTP only.
    requests = []
    transport_account = {**ACCOUNT, "phone_number_id": "123"}

    def simulated_send(request):
        requests.append(request)
        return httpx.Response(200, json={"messages": [{"id": "wamid.one"}]})

    with httpx.Client(transport=httpx.MockTransport(simulated_send)) as transport:
        adapter = WhatsAppAdapter(
            client=transport,
            token="synthetic-token",
            phone_number_id=transport_account["phone_number_id"],
            api_version="v23.0",
        )
        assert (
            dispatch_once(db, adapter, worker_id="simulated-transport", **transport_account)
            == "accepted"
        )
        assert dispatch_once(db, adapter, worker_id="restart", **transport_account) == "idle"
    assert len(requests) == 1
    assert db.record_whatsapp_status(
        status().model_copy(update=transport_account), **transport_account
    )["matched"]
    path = f"{ROOT}/{monitor['id']}/offers/{offer['id']}/decision"
    accepted = checked(api.post(path, headers=auth(), json={"accept": True}))
    assert checked(api.post(path, headers=auth(), json={"accept": True})) == accepted
    policy = dict(status="disclosure_required", evidence=ref(device, observed, POLICY))
    rubric = [dict(evidence=ref(device, observed, RUBRIC))]
    draft = dict(
        schema_version=2,
        title="Private comparison",
        body=CLAIM + "\n" + DISCLOSURE,
        citations=[dict(claim=CLAIM, evidence=ref(device, observed, CLAIM))],
        disclosure=DISCLOSURE,
    )
    model = bound(
        db,
        ScriptedModel(
            [
                requirements(policy, rubric),
                plan("draft", "comparison", "Prepare the requested comparison"),
                permitted(),
                structured("save_review_draft", draft),
                assessment(),
            ]
        ),
    )
    assert run_once(db, model, Settings()) and run_once(db, model, Settings())
    saved = db.list_private_artifacts_v2("user_alice", accepted["responsibility_id"])["artifacts"][
        0
    ]
    first_file = render_private_artifact_docx(db, "user_alice", saved["id"])
    download = api.get(f"/v2/artifacts/{saved['id']}/file", headers=auth())
    assert download.status_code == 200 and download.headers["cache-control"] == "no-store"
    assert download.content == first_file.content
    assert download.headers["x-artifact-sha256"] == first_file.sha256
    revision_path = f"/v2/artifacts/{saved['id']}/revisions"
    revision_request = {"instructions": "Use a clearer title", "request_key": "student-r1"}
    revision = checked(api.post(revision_path, headers=auth(), json=revision_request))
    assert checked(api.post(revision_path, headers=auth(), json=revision_request)) == revision
    revised = deepcopy(draft)
    revised["title"] = "Clearer private comparison"
    model = bound(
        db, ScriptedModel([permitted(), structured("save_review_draft", revised), assessment()])
    )
    assert run_once(db, model, Settings())
    latest = db.list_private_artifacts_v2("user_alice", accepted["responsibility_id"])["artifacts"]
    assert len(latest) == 2 and latest[0]["task_id"] == str(revision["task_id"])
    second_file = render_private_artifact_docx(db, "user_alice", latest[0]["id"])
    assert (
        api.get(f"/v2/artifacts/{latest[0]['id']}/file", headers=auth()).content
        == second_file.content
    )
    assert first_file.sha256 != second_file.sha256
    assert first_file.content == render_private_artifact_docx(db, "user_alice", saved["id"]).content
    assert db.due_course_supervisions() == []
    import test_canvas_evidence as evidence

    scan = evidence.next_scan(device, "deadline-extension")
    publish(device, text=TEXT, scan=scan, due=(deadline + timedelta(days=1)).isoformat())
    assert db.due_course_supervisions() == [{"id": UUID(monitor["id"]), "user_id": "user_alice"}]
    with pytest.raises((SourceRefreshRequired, ArtifactNotReady)):
        render_private_artifact_docx(db, "user_alice", saved["id"])
    stale_download = api.get(f"/v2/artifacts/{saved['id']}/file", headers=auth())
    assert stale_download.status_code == 409 and not stale_download.content.startswith(b"PK")
    run_course_supervision_once(db, bound(db, Model(decision("wait"))), "user_alice", monitor["id"])
    assert db.due_course_supervisions() == []
    with db.connection() as conn:
        assert (
            conn.execute(
                "SELECT state FROM wrytely_agent.whatsapp_outbound WHERE id=%s", (action["id"],)
            ).fetchone()["state"]
            == "delivered"
        )
        reservations = conn.execute(
            "SELECT state FROM wrytely_agent.model_call_reservations"
        ).fetchall()
    assert len(reservations) == 11 and all(row["state"] == "settled" for row in reservations)
