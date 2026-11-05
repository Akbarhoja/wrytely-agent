import json

import httpx
import pytest
from openai import OpenAI
from test_fireworks_model import TOOL, reply

from shared.config import Settings
from shared.fireworks_model import FireworksModelClient
from shared.json_actions import parse_actions
from shared.model_client import ModelCallFailed


@pytest.mark.parametrize(
    "content",
    [
        '{"text":"ok","text":"changed","actions":[]}',
        '{"text":"ok","actions":[],"user_id":"other"}',
        '{"text":"","actions":[{"name":"send_anywhere","arguments":{}}]}',
        '{"text":"","actions":[{"name":"inspect","arguments":{"x":NaN}}]}',
        '{"text":"","actions":[{"name":"inspect","arguments":{},"call_id":"fake"}]}',
        '{"text":"","actions":[]}',
        '{"text":"<think>private</think>","actions":[]}',
        '```json\n{"text":"ok","actions":[]}\n```',
        '{"text":123,"actions":[]}',
        json.dumps({"text": "", "actions": [{"name": "inspect", "arguments": {}}] * 7}),
    ],
)
def test_untrusted_json_cannot_expand_the_action_protocol(content):
    with pytest.raises(ValueError):
        parse_actions(content, {"inspect"})


def test_action_ids_are_runtime_assigned_and_not_arguments():
    text, output = parse_actions(
        '{"text":"","actions":[{"name":"inspect","arguments":{}}]}', {"inspect"}
    )
    assert text == "" and output[0]["name"] == "inspect"
    assert output[0]["call_id"].startswith("json_") and output[0]["arguments"] == "{}"


def test_text_is_retained_in_canonical_history_separate_from_actions():
    text, output = parse_actions(
        '{"text":"Checking the source","actions":[{"name":"inspect","arguments":{}}]}', {"inspect"}
    )
    assert text == "Checking the source"
    assert output[0]["type"] == "message" and output[1]["type"] == "function_call"
    assert output[0]["content"][0]["text"] == text


def test_json_action_mode_is_explicit_default_off_and_invalid_modes_reject():
    assert Settings(_env_file=None).fireworks_action_mode == "native"
    with pytest.raises(ValueError):
        Settings(_env_file=None, fireworks_action_mode="automatic")


def client(handler):
    model = FireworksModelClient(
        Settings(fireworks_api_key="synthetic", fireworks_action_mode="json")
    )
    model._client.close()
    model._client = OpenAI(
        api_key="synthetic",
        base_url="https://api.fireworks.ai/inference/v1",
        max_retries=0,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    return model


def test_json_mode_replays_results_with_exact_ids_and_uses_no_native_tools():
    requests = []

    def handler(request):
        body = json.loads(request.content)
        requests.append(body)
        assert "tools" not in body and "context_length_exceeded_behavior" not in body
        assert body["response_format"] == {"type": "json_object"}
        assert '"name": "inspect"' in body["messages"][0]["content"]
        if len(requests) == 1:
            return httpx.Response(
                200, json=reply(content='{"text":"","actions":[{"name":"inspect","arguments":{}}]}')
            )
        prior = json.loads(body["messages"][-2]["content"])["recorded_actions"][0]
        result = json.loads(body["messages"][-1]["content"])["action_result"]
        assert prior["call_id"] == result["call_id"]
        assert result["output"] == "untrusted source text"
        return httpx.Response(200, json=reply(content='{"text":"Checked response","actions":[]}'))

    model = client(handler)
    try:
        history = [{"role": "user", "content": "Inspect my bound evidence"}]
        turn = model.turn(history, [TOOL])
        assert turn.usage_known and turn.input_tokens == 11
        history += turn.output + [
            {
                "type": "function_call_output",
                "call_id": turn.output[0]["call_id"],
                "output": "untrusted source text",
            }
        ]
        assert model.turn(history, [TOOL]).text == "Checked response"
        assert len(requests) == 2
    finally:
        model._client.close()


@pytest.mark.parametrize("mode", ["malformed", "native_call", "length", "http503"])
def test_failed_json_attempt_preserves_safe_usage_and_never_retries(mode):
    requests = []

    def handler(request):
        requests.append(request)
        if mode == "http503":
            return httpx.Response(
                503, json={"error": {"code": "invalid_request_error", "message": "PRIVATE"}}
            )
        from test_fireworks_model import call

        return httpx.Response(
            200,
            json=reply(
                content="PRIVATE" if mode == "malformed" else '{"text":"ok","actions":[]}',
                finish="length" if mode == "length" else "stop",
                calls=[call()] if mode == "native_call" else None,
            ),
        )

    model = client(handler)
    try:
        with pytest.raises(ModelCallFailed) as failure:
            model.turn([{"role": "user", "content": "synthetic"}], [TOOL])
        assert len(requests) == 1 and "PRIVATE" not in str(failure.value)
        assert failure.value.evidence()["input_tokens"] == (None if mode == "http503" else 11)
    finally:
        model._client.close()
