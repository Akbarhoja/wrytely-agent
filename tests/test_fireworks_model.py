"""Mocked provider wire/replay checks; never calls an external inference endpoint."""

import json

import httpx
import pytest
from openai import OpenAI
from pydantic import ValidationError

from shared.budgeted_model import BudgetedMetaRouter, BudgetedModelClient
from shared.config import Settings
from shared.fireworks_model import MODEL, FireworksModelClient, chat_messages, chat_tools
from shared.model_budgets import ModelBudgetExceeded
from shared.model_client import MetaModelClient, ModelCallFailed

TOOL = {
    "type": "function",
    "name": "inspect",
    "description": "Read evidence",
    "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
    "strict": True,
}


def reply(*, finish="stop", content="A checked answer", calls=None, usage=True, **fields):
    return {
        "id": "chat_mock",
        "object": "chat.completion",
        "created": 1,
        "model": MODEL,
        "choices": [
            {
                "index": 0,
                "finish_reason": finish,
                "message": {"role": "assistant", "content": content, "tool_calls": calls, **fields},
            }
        ],
        "usage": {"prompt_tokens": 11, "completion_tokens": 17, "total_tokens": 28}
        if usage
        else None,
    }


def call(identifier="call_1", name="inspect"):
    return {"id": identifier, "type": "function", "function": {"name": name, "arguments": "{}"}}


@pytest.fixture
def mocked_client():
    clients = []

    def make(handler):
        model = FireworksModelClient(
            Settings(
                fireworks_api_key="test-placeholder",
                meta_max_output_tokens=8192,
                meta_reasoning_effort="low",
            )
        )
        model._client.close()
        model._client = OpenAI(
            api_key="test-placeholder",
            base_url="https://api.fireworks.ai/inference/v1",
            max_retries=0,
            http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        )
        clients.append(model)
        return model

    yield make
    for model in clients:
        model._client.close()


def test_wire_uses_meta_model_and_exact_configured_limit(mocked_client):
    requests = []

    def handle(request):
        requests.append(request)
        assert str(request.url) == "https://api.fireworks.ai/inference/v1/chat/completions"
        assert request.headers["authorization"] == "Bearer test-placeholder"
        body = json.loads(request.content)
        assert body["model"] == MODEL
        assert body["max_tokens"] == 8192 and body["n"] == 1
        assert body["reasoning_effort"] == "low"
        assert body["context_length_exceeded_behavior"] == "error"
        assert body["tools"] == [
            {
                "type": "function",
                "function": {
                    "name": "inspect",
                    "description": "Read evidence",
                    "parameters": TOOL["parameters"],
                    "strict": True,
                },
            }
        ]
        assert "include" not in body and "store" not in body
        return httpx.Response(200, json=reply())

    result = mocked_client(handle).turn([{"role": "user", "content": "Synthetic"}], [TOOL])
    assert result.text == "A checked answer" and result.usage_known
    assert result.input_tokens == 11 and result.output_tokens == 17
    assert len(requests) == 1


def test_parallel_tool_replay_keeps_ids_and_private_reasoning(mocked_client):
    requests = []

    def handle(request):
        body = json.loads(request.content)
        requests.append(body)
        if len(requests) == 1:
            return httpx.Response(
                200,
                json=reply(
                    finish="tool_calls",
                    content=None,
                    calls=[call(), call("call_2")],
                    reasoning_content="private provider replay",
                ),
            )
        assert body["messages"] == [
            {"role": "user", "content": "Synthetic"},
            {
                "role": "assistant",
                "content": "",
                "reasoning_content": "private provider replay",
                "tool_calls": [call(), call("call_2")],
            },
            {"role": "tool", "tool_call_id": "call_1", "content": "first evidence"},
            {"role": "tool", "tool_call_id": "call_2", "content": "second evidence"},
        ]
        return httpx.Response(200, json=reply())

    model = mocked_client(handle)
    history = [{"role": "user", "content": "Synthetic"}]
    first = model.turn(history, [TOOL])
    assert first.text == ""
    assert [x["call_id"] for x in first.output if x["type"] == "function_call"] == [
        "call_1",
        "call_2",
    ]
    history.extend(first.output)
    history.extend(
        [
            {"type": "function_call_output", "call_id": "call_1", "output": "first evidence"},
            {"type": "function_call_output", "call_id": "call_2", "output": "second evidence"},
        ]
    )
    assert model.turn(history, [TOOL]).text == "A checked answer"


@pytest.mark.parametrize(
    "extra",
    [
        {"type": "reasoning", "encrypted_content": "opaque Meta state"},
        {"type": "function_call_output", "call_id": "orphan", "output": "data"},
        {"type": "function_call", "call_id": "call_1", "name": "inspect", "arguments": "{}"},
        {"type": "unknown"},
        {"role": "user", "content": [{"type": "image_url", "image_url": "private"}]},
    ],
)
def test_untranslatable_history_fails_before_network(mocked_client, extra):
    requests = []
    model = mocked_client(lambda r: requests.append(r))
    with pytest.raises(ValueError):
        model.turn([{"role": "user", "content": "Synthetic"}, extra], [TOOL])
    assert requests == []


def test_duplicate_and_incomplete_tool_results_are_rejected():
    c = {"type": "function_call", "call_id": "call_1", "name": "inspect", "arguments": "{}"}
    output = {"type": "function_call_output", "call_id": "call_1", "output": "done"}
    with pytest.raises(ValueError, match="duplicate"):
        chat_messages([c, c, output])
    with pytest.raises(ValueError, match="duplicate"):
        chat_messages([c, output, output])
    with pytest.raises(ValueError, match="precede"):
        chat_messages([c, {"role": "user", "content": "next"}])
    with pytest.raises(ValueError):
        chat_tools([TOOL, TOOL])


@pytest.mark.parametrize(
    "payload",
    [
        reply(finish="length"),
        reply(finish="content_filter"),
        reply(finish="tool_calls", content=None, calls=[]),
        reply(content="<think>private</think>answer"),
        reply(content="", refusal="refused"),
        reply(finish="tool_calls", content=None, calls=[call(name="unoffered")]),
        reply(finish="tool_calls", content=None, calls=[call(), call()]),
    ],
)
def test_unsuccessful_or_unsafe_output_is_not_accepted(mocked_client, payload):
    model = mocked_client(lambda r: httpx.Response(200, json=payload))
    with pytest.raises(ModelCallFailed) as raised:
        model.turn([{"role": "user", "content": "Synthetic"}], [TOOL])
    assert raised.value.evidence()["input_tokens"] == 11
    assert "private" not in str(raised.value)


def test_missing_usage_is_unknown_not_zero_cost(mocked_client):
    model = mocked_client(lambda r: httpx.Response(200, json=reply(usage=False)))
    assert model.turn([{"role": "user", "content": "Synthetic"}], []).usage_known is False


def test_http_error_is_allowlisted_and_never_retried(mocked_client):
    requests = []

    def handle(r):
        requests.append(r)
        return httpx.Response(
            404,
            json={
                "error": {
                    "code": "private-provider-detail",
                    "message": "private body",
                    "type": "not_found",
                }
            },
        )

    with pytest.raises(ModelCallFailed) as raised:
        mocked_client(handle).turn([{"role": "user", "content": "Synthetic"}], [])
    assert len(requests) == 1
    assert raised.value.evidence()["code"] == "unknown"
    assert raised.value.evidence()["http_status"] == 404
    assert "private" not in str(raised.value)


def test_provider_selection_requires_its_own_key_and_preserves_meta_default():
    common = {
        "meta_api_key": "meta-test",
        "meta_budget_key": "original-budget",
        "meta_input_usd_per_million": "1.25",
        "meta_output_usd_per_million": "4.25",
    }
    default = Settings(**common)
    router = BudgetedMetaRouter(None, default)
    assert isinstance(router.model, MetaModelClient)
    router.model._client.close()
    selected = Settings(**common, meta_provider="fireworks")
    assert selected.readiness()["meta_model"] is False
    with pytest.raises(RuntimeError, match="FIREWORKS"):
        BudgetedMetaRouter(None, selected)
    selected = Settings(**common, meta_provider="fireworks", fireworks_api_key="fireworks-test")
    assert selected.readiness()["meta_model"] is True
    router = BudgetedMetaRouter(None, selected)
    assert isinstance(router.model, FireworksModelClient)
    router.model._client.close()
    with pytest.raises(ValidationError):
        Settings(meta_provider="arbitrary-endpoint")


def test_same_original_budget_blocks_before_fireworks_request(mocked_client):
    requests = []
    model = mocked_client(lambda r: requests.append(r))

    class ClosedBudget:
        def reserve_model_call(self, user, key, maximum):
            assert user == "verified-owner" and key == "original-budget"
            raise ModelBudgetExceeded("Disabled")

    wrapped = BudgetedModelClient(
        ClosedBudget(),
        model,
        "verified-owner",
        "original-budget",
        input_usd_per_million="1.25",
        output_usd_per_million="4.25",
    )
    with pytest.raises(ModelBudgetExceeded):
        wrapped.turn([{"role": "user", "content": "Synthetic"}], [])
    assert requests == []


@pytest.mark.parametrize("effort", ["minimal", "xhigh", "max"])
def test_unsupported_fireworks_effort_is_not_silently_remapped(effort):
    with pytest.raises(ValueError, match="reasoning"):
        FireworksModelClient(Settings(fireworks_api_key="test", meta_reasoning_effort=effort))


def test_runtime_startup_accepts_fireworks_key_without_a_meta_endpoint_key(monkeypatch):
    from runtime import worker

    settings = Settings(
        database_url="postgresql://disposable-no-connection",
        meta_provider="fireworks",
        fireworks_api_key="test",
        meta_api_key=None,
    )
    calls = []
    monkeypatch.setattr("sys.argv", ["worker", "--once"])
    monkeypatch.setattr(worker, "Settings", lambda: settings)
    monkeypatch.setattr(worker, "Store", lambda *a, **kw: "existing-store")
    monkeypatch.setattr(worker, "BudgetedMetaRouter", lambda *a: "budgeted-model")
    monkeypatch.setattr(worker, "run_once", lambda *args: calls.append(args) or False)
    worker.main()
    assert len(calls) == 1 and calls[0][:2] == ("existing-store", "budgeted-model")
