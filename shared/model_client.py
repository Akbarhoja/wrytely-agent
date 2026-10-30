from openai import APIStatusError, OpenAI

from contracts.models import ModelTurn
from shared.config import Settings


class ModelCallFailed(RuntimeError):
    """Safe unsuccessful-call metadata; never provider text, output or credentials."""

    def __init__(self, *, status, http_status=None, code=None, usage=None):
        super().__init__("Model response did not complete")
        statuses = {"incomplete", "failed", "cancelled", "in_progress", "queued", "http_error"}
        codes = {
            "model_not_found",
            "insufficient_quota",
            "rate_limit_exceeded",
            "invalid_api_key",
            "invalid_request_error",
            "server_error",
        }
        self._evidence = {
            "status": status if isinstance(status, str) and status in statuses else "unknown",
            "http_status": http_status
            if type(http_status) is int and 400 <= http_status <= 599
            else None,
            "code": code
            if isinstance(code, str) and code in codes
            else ("unknown" if code is not None else None),
            "input_tokens": None,
            "output_tokens": None,
        }
        if usage is not None:
            for key in ("input_tokens", "output_tokens"):
                value = getattr(usage, key, None)
                if type(value) is int and value >= 0:
                    self._evidence[key] = value

    def evidence(self):
        return dict(self._evidence)


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
        try:
            response = self._client.responses.create(
                model=self._model,
                input=history,
                tools=tools,
                store=False,
                include=["reasoning.encrypted_content"],
                max_output_tokens=2048,
            )
        except APIStatusError as exc:
            raise ModelCallFailed(
                status="http_error", http_status=exc.status_code, code=exc.code
            ) from None
        if response.status != "completed":
            raise ModelCallFailed(status=response.status, usage=response.usage)
        usage = response.usage
        return ModelTurn(
            output=[item.model_dump(exclude_none=True) for item in response.output],
            text=response.output_text,
            input_tokens=usage.input_tokens if usage else 0,
            output_tokens=usage.output_tokens if usage else 0,
        )
