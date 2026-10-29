from openai import OpenAI

from contracts.models import ModelTurn
from shared.config import Settings


class MetaModelClient:
    """Meta Responses API; SDK is transport, inference is performed by Meta."""

    def __init__(self, settings: Settings):
        if not settings.meta_api_key:
            raise RuntimeError("AGENT_META_API_KEY is not configured")
        self._model = settings.meta_model
        self._client = OpenAI(
            api_key=settings.meta_api_key.get_secret_value(),
            base_url="https://api.meta.ai/v1",
            timeout=30,
            max_retries=0,  # Task retries are managed durably by the worker.
        )

    def turn(self, history: list[dict], tools: list[dict]) -> ModelTurn:
        response = self._client.responses.create(
            model=self._model,
            input=history,
            tools=tools,
            store=False,
            include=["reasoning.encrypted_content"],
            max_output_tokens=2048,
        )
        if response.status != "completed":
            raise RuntimeError("Model response did not complete")
        usage = response.usage
        return ModelTurn(
            output=[item.model_dump(exclude_none=True) for item in response.output],
            text=response.output_text,
            input_tokens=usage.input_tokens if usage else 0,
            output_tokens=usage.output_tokens if usage else 0,
        )
