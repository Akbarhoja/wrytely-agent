from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime

import httpx
import pytest
from test_canvas_sync import device as device

from integrations.whatsapp import WhatsAppAdapter, WhatsAppText
from shared.db import Store

ACCOUNT = {"business_id": "456", "phone_number_id": "123"}


@pytest.mark.parametrize(
    "mode", ["success", "upload_timeout", "send_timeout", "pause_after_upload"]
)
def test_checked_file_upload_rechecks_control_and_never_retries(device, mode):
    import json

    from test_artifact_delivery import ACCOUNT as file_account
    from test_artifact_delivery import prepared_file

    from integrations.whatsapp_delivery import run_once
    from runtime.artifact_rendering import render_private_artifact_docx

    db, saved = prepared_file(device)
    file_account = {**file_account, "phone_number_id": "123"}
    expected = render_private_artifact_docx(db, "user_alice", saved["id"]).content
    db.enqueue_checked_artifact_delivery("user_alice", saved["id"])
    calls = []

    def handle(request):
        calls.append(request)
        if request.url.path.endswith("/media"):
            assert expected in request.content
            assert request.headers["content-type"].startswith("multipart/form-data;")
            if mode == "upload_timeout":
                raise httpx.ReadTimeout("Lost upload", request=request)
            if mode == "pause_after_upload":
                db.set_paused("user_alice", True)
            return httpx.Response(200, json={"id": "media_one"})
        payload = json.loads(request.content)
        assert payload["type"] == "document"
        assert payload["document"] == {"id": "media_one", "filename": f"wrytely-{saved['id']}.docx"}
        assert "link" not in payload["document"]
        if mode == "send_timeout":
            raise httpx.ReadTimeout("Lost send", request=request)
        return httpx.Response(200, json={"messages": [{"id": "wamid.file"}]})

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        adapter = WhatsAppAdapter(
            client=client,
            token="test",
            phone_number_id=file_account["phone_number_id"],
            api_version="v23.0",
        )
        args = dict(worker_id="file-one", **file_account)
        assert run_once(db, adapter, **args) == ("accepted" if mode == "success" else "unknown")
        assert run_once(db, adapter, **args) == "idle"
    assert len(calls) == (1 if mode in {"upload_timeout", "pause_after_upload"} else 2)


@pytest.mark.parametrize("lost", [False, True])
def test_reply_template_uses_typed_payload_and_never_resends(store, ready_reply, lost):
    import json

    from contracts.templates import ApprovedTemplate
    from integrations.whatsapp_delivery import run_once

    with store.connection() as conn:
        conn.execute(
            "UPDATE wrytely_agent.channel_links SET last_event_at=now()-interval '25 hours'"
        )
    approved = ApprovedTemplate(
        key="reply",
        name="reply",
        language="en_US",
        **ACCOUNT,
        provider_approved=True,
        body_parameters=[{"source": "reply_text", "max_length": 1024}],
    )
    calls = []

    def send(request):
        calls.append(json.loads(request.content))
        if lost:
            raise httpx.ReadTimeout("Ambiguous dispatch", request=request)
        return httpx.Response(200, json={"messages": [{"id": "wamid.template"}]})

    with httpx.Client(transport=httpx.MockTransport(send)) as client:
        adapter = WhatsAppAdapter(
            client=client, token="test", phone_number_id="123", api_version="v23.0"
        )
        args = dict(
            worker_id="one", **ACCOUNT, approved_templates=[approved], reply_template_key="reply"
        )
        assert run_once(store, adapter, **args) == ("unknown" if lost else "accepted")
        assert run_once(store, adapter, **args) == "idle"
    assert len(calls) == 1 and calls[0]["type"] == "template"
    assert calls[0]["template"]["components"][0]["parameters"] == [
        {"type": "text", "text": "Checked reply"}
    ]


def test_offer_transport_uses_separate_template_and_original_queue(device):
    import json

    from test_course_offer_delivery import ACCOUNT as offer_account
    from test_course_offer_delivery import prepared, queue, template

    from integrations.whatsapp_delivery import run_once

    db, monitor, offer = prepared(device)
    offer_account = {**offer_account, "phone_number_id": "123"}
    approved = template().model_copy(update={"phone_number_id": "123"})
    queue(db, monitor, offer)
    with db.connection() as conn:
        conn.execute(
            "UPDATE wrytely_agent.channel_links SET last_event_at=now()-interval '25 hours'"
        )
    calls = []

    def send(request):
        calls.append(json.loads(request.content))
        return httpx.Response(200, json={"messages": [{"id": "wamid.offer"}]})

    with httpx.Client(transport=httpx.MockTransport(send)) as client:
        adapter = WhatsAppAdapter(
            client=client,
            token="test",
            phone_number_id=offer_account["phone_number_id"],
            api_version="v23.0",
        )
        args = dict(
            worker_id="one",
            **offer_account,
            approved_offer_templates=[approved],
            offer_template_key="test_offer",
        )
        assert run_once(db, adapter, **args) == "accepted"
        assert run_once(db, adapter, **args) == "idle"
    assert len(calls) == 1 and calls[0]["type"] == "template"
    assert calls[0]["template"]["components"][0]["parameters"][0]["text"] == offer["message"]


def test_worker_startup_rejects_missing_delivery_configuration(monkeypatch, capsys):
    from app.whatsapp_worker import main
    from shared.config import Settings

    monkeypatch.setattr("app.whatsapp_worker.Settings", lambda: Settings())
    with pytest.raises(SystemExit) as error:
        main(["--once"])
    assert error.value.code == 2
    assert "Configure" in capsys.readouterr().err


def test_worker_once_on_empty_database_exits_without_external_request(
    store, database_url, monkeypatch
):
    from app.whatsapp_worker import main
    from shared.config import Settings

    settings = Settings(
        database_url=database_url,
        whatsapp_access_token="synthetic-test-token",
        whatsapp_api_version="v23.0",
        whatsapp_business_account_id="456",
        whatsapp_phone_number_id="123",
    )
    monkeypatch.setattr("app.whatsapp_worker.Settings", lambda: settings)
    assert main(["--once"]) is None


@pytest.fixture
def ready_reply(store, alice):
    phone = "15555550123"
    challenge = store.create_whatsapp_challenge("user_alice")["message"]
    store.ingest_whatsapp(WhatsAppText("link-worker", phone, challenge))
    store.ingest_whatsapp(WhatsAppText("inbound-worker", phone, "Help with my assignment"))
    store.record_whatsapp_inbound_time("inbound-worker", phone, datetime.now(UTC))
    store.set_communication_preferences(
        "user_alice", consent=True, timezone="UTC", quiet_start=0, quiet_end=0
    )
    store.complete(store.claim(), "Checked reply")


def outbound(store):
    with store.connection() as conn:
        return conn.execute("SELECT * FROM wrytely_agent.whatsapp_outbound").fetchone()


@pytest.mark.parametrize("lost_response", [False, True])
def test_delivery_records_one_attempt_and_restart_does_not_resend(
    store, ready_reply, lost_response, database_url
):
    from integrations.whatsapp_delivery import run_once

    requests = []

    def handle(request):
        requests.append(request)
        if lost_response:
            raise httpx.ReadTimeout("Response lost", request=request)
        return httpx.Response(200, json={"messages": [{"id": "wamid.reply"}]})

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        adapter = WhatsAppAdapter(
            client=client, token="test", phone_number_id="123", api_version="v23.0"
        )
        expected = "unknown" if lost_response else "accepted"
        assert run_once(store, adapter, worker_id="one", **ACCOUNT) == expected
        assert run_once(Store(database_url), adapter, worker_id="restart", **ACCOUNT) == "idle"
    assert len(requests) == 1
    assert outbound(store)["state"] == expected


@pytest.mark.parametrize("control", ["paused", "unlinked", "expired"])
def test_delivery_controls_prevent_network_request(store, ready_reply, control):
    from integrations.whatsapp_delivery import run_once

    if control == "paused":
        store.set_paused("user_alice", True)
    elif control == "unlinked":
        store.unlink_whatsapp("user_alice")
    else:
        with store.connection() as conn:
            conn.execute(
                "UPDATE wrytely_agent.channel_links SET last_event_at=now()-interval '25 hours'"
            )
    requests = []

    def handle(request):
        requests.append(request)
        return httpx.Response(200, json={"messages": [{"id": "must-not-send"}]})

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        adapter = WhatsAppAdapter(
            client=client, token="test", phone_number_id="123", api_version="v23.0"
        )
        assert run_once(store, adapter, worker_id="one", **ACCOUNT) in ("held", "idle")
    assert requests == []
    assert outbound(store)["state"] == ("cancelled" if control == "unlinked" else "deferred")


def test_crash_after_dispatch_does_not_resend_on_restart(store, ready_reply, database_url):
    from integrations.whatsapp_delivery import run_once

    requests = []

    def handle(request):
        requests.append(request)
        raise SystemExit("Simulated abrupt process termination after dispatch")

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        adapter = WhatsAppAdapter(
            client=client, token="test", phone_number_id="123", api_version="v23.0"
        )
        with pytest.raises(SystemExit):
            run_once(store, adapter, worker_id="first", **ACCOUNT)
        with store.connection() as conn:
            conn.execute(
                "UPDATE wrytely_agent.whatsapp_outbound SET lease_until=now()-interval '1 second'"
            )
        assert run_once(Store(database_url), adapter, worker_id="second", **ACCOUNT) == "idle"
    assert len(requests) == 1
    assert outbound(store)["state"] == "unknown"


def test_persistence_failure_after_send_is_not_retried(
    store, ready_reply, database_url, monkeypatch
):
    from integrations.whatsapp_delivery import run_once

    requests = []

    def handle(request):
        requests.append(request)
        return httpx.Response(200, json={"messages": [{"id": "wamid.persist-failed"}]})

    def failed_checkpoint(*args):
        raise RuntimeError("Simulated storage outage")

    monkeypatch.setattr(store, "record_whatsapp_result", failed_checkpoint)
    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        adapter = WhatsAppAdapter(
            client=client, token="test", phone_number_id="123", api_version="v23.0"
        )
        with pytest.raises(RuntimeError, match="storage outage"):
            run_once(store, adapter, worker_id="first", **ACCOUNT)
        assert outbound(store)["state"] == "sending"
        with store.connection() as conn:
            conn.execute(
                "UPDATE wrytely_agent.whatsapp_outbound SET lease_until=now()-interval '1 second'"
            )
        assert run_once(Store(database_url), adapter, worker_id="restart", **ACCOUNT) == "idle"
    assert len(requests) == 1
    assert outbound(store)["state"] == "unknown"


def test_concurrent_workers_dispatch_only_authoritative_payload_once(
    store, ready_reply, monkeypatch
):
    import json

    from integrations.whatsapp_delivery import run_once

    claim_next = store.claim_whatsapp_delivery

    def stale_claim(worker_id):
        claim = claim_next(worker_id)
        return replace(claim, content="Stale text", recipient="15555550999") if claim else None

    monkeypatch.setattr(store, "claim_whatsapp_delivery", stale_claim)
    requests = []

    def handle(request):
        requests.append(request)
        return httpx.Response(200, json={"messages": [{"id": "wamid.concurrent"}]})

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        adapter = WhatsAppAdapter(
            client=client, token="test", phone_number_id="123", api_version="v23.0"
        )
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(
                pool.map(lambda i: run_once(store, adapter, worker_id=str(i), **ACCOUNT), range(4))
            )
    assert results.count("accepted") == 1
    assert len(requests) == 1
    assert json.loads(requests[0].content)["to"] == "15555550123"
    assert json.loads(requests[0].content)["text"]["body"] == "Checked reply"
