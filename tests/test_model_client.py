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
