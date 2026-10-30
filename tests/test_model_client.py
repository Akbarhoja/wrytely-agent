import json

import httpx
import pytest
from openai import OpenAI

from shared.config import Settings
from shared.model_client import MetaModelClient


@pytest.mark.parametrize("status", ["completed", "incomplete"])
def test_meta_transport_and_incomplete_response(status):
    def handle(request):
        assert str(request.url) == "https://api.meta.ai/v1/responses"
        assert request.headers["authorization"] == "Bearer local-test-placeholder"
        body = json.loads(request.content)
        assert body["store"] is False
        assert body["include"] == ["reasoning.encrypted_content"]
        assert body["model"] == "muse-spark-1.3"
        return httpx.Response(
            200,
            json={
                "id": "resp_local",
                "object": "response",
                "created_at": 1,
                "status": status,
                "output": [
                    {
                        "type": "message",
                        "id": "msg_local",
                        "status": "completed",
                        "role": "assistant",
                        "content": [{"type": "output_text", "text": "Hello", "annotations": []}],
                    }
                ],
                "usage": {"input_tokens": 10, "output_tokens": 2, "total_tokens": 12},
            },
        )

    client = MetaModelClient(Settings(meta_api_key="local-test-placeholder"))
    client._client.close()
    with OpenAI(
        api_key="local-test-placeholder",
        base_url="https://api.meta.ai/v1",
        http_client=httpx.Client(transport=httpx.MockTransport(handle)),
    ) as transport:
        client._client = transport
        if status == "incomplete":
            with pytest.raises(RuntimeError, match="did not complete"):
                client.turn([{"role": "user", "content": "Hi"}], [])
        else:
            result = client.turn([{"role": "user", "content": "Hi"}], [])
            assert result.text == "Hello"
            assert result.input_tokens == 10
            assert result.output_tokens == 2


@pytest.mark.parametrize(
    "usage", [None, {"input_tokens": 10, "output_tokens": 7, "total_tokens": 17}]
)
def test_incomplete_response_retains_safe_usage_without_output(usage):
    from shared.model_client import ModelCallFailed

    payload = {
        "id": "private-response-id",
        "object": "response",
        "created_at": 1,
        "status": "incomplete",
        "output": [],
        "usage": usage,
        "incomplete_details": {"reason": "max_output_tokens"},
    }
    client = MetaModelClient(Settings(meta_api_key="local-test-placeholder"))
    client._client.close()
    with OpenAI(
        api_key="local-test-placeholder",
        base_url="https://api.meta.ai/v1",
        http_client=httpx.Client(
            transport=httpx.MockTransport(lambda request: httpx.Response(200, json=payload))
        ),
    ) as transport:
        client._client = transport
        with pytest.raises(ModelCallFailed) as raised:
            client.turn([], [])
    assert raised.value.evidence() == {
        "status": "incomplete",
        "http_status": None,
        "code": None,
        "input_tokens": 10 if usage else None,
        "output_tokens": 7 if usage else None,
    }
    assert "private-response-id" not in str(raised.value)


@pytest.mark.parametrize(
    "code,expected", [("model_not_found", "model_not_found"), ("secret-provider-text", "unknown")]
)
def test_http_failure_metadata_is_allowlisted_and_not_retried(code, expected):
    from shared.model_client import ModelCallFailed

    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(
            404,
            json={
                "error": {
                    "message": "secret-provider-text",
                    "type": "invalid_request_error",
                    "code": code,
                }
            },
        )

    client = MetaModelClient(Settings(meta_api_key="local-test-placeholder"))
    client._client.close()
    with OpenAI(
        api_key="local-test-placeholder",
        base_url="https://api.meta.ai/v1",
        max_retries=0,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    ) as transport:
        client._client = transport
        with pytest.raises(ModelCallFailed) as raised:
            client.turn([], [])
    assert len(calls) == 1
    assert raised.value.evidence() == {
        "status": "http_error",
        "http_status": 404,
        "code": expected,
        "input_tokens": None,
        "output_tokens": None,
    }
    assert "secret-provider-text" not in str(raised.value)
