import httpx
import pytest
from openai import OpenAI
from test_model_output_limits import Budget

from shared.budgeted_model import BudgetedModelCallFailed, BudgetedModelClient
from shared.config import Settings
from shared.fireworks_model import FireworksModelClient
from shared.model_client import MetaModelClient


@pytest.mark.parametrize("model_type", [MetaModelClient, FireworksModelClient])
def test_timeout_default_preserved_and_explicit_limit_is_applied(model_type):
    for timeout in (30, 90, 120):
        model = model_type(
            Settings(
                meta_api_key="synthetic",
                fireworks_api_key="synthetic",
                meta_request_timeout_seconds=timeout,
            )
        )
        try:
            assert model._client.timeout == timeout
            assert model._client.max_retries == 0
        finally:
            model._client.close()
    assert Settings(_env_file=None).meta_request_timeout_seconds == 30


@pytest.mark.parametrize("value", [0, 4, 121, True, "unbounded", 5.5])
def test_unsafe_timeout_configuration_is_rejected(value):
    with pytest.raises(ValueError):
        Settings(_env_file=None, meta_request_timeout_seconds=value)


@pytest.mark.parametrize("model_type", [MetaModelClient, FireworksModelClient])
@pytest.mark.parametrize("timeout", [True, False])
def test_transport_failure_keeps_cost_hold_safe_evidence_and_single_attempt(model_type, timeout):
    calls = []

    def handler(request):
        calls.append(request)
        error = httpx.ReadTimeout if timeout else httpx.ConnectError
        raise error("PRIVATE URL credential/body", request=request)

    model = model_type(Settings(meta_api_key="synthetic", fireworks_api_key="synthetic"))
    model._client.close()
    model._client = OpenAI(
        api_key="synthetic",
        base_url="https://example.test/v1",
        max_retries=0,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    budget = Budget("1")
    wrapped = BudgetedModelClient(
        budget,
        model,
        "verified-owner",
        "approved",
        input_usd_per_million="1.25",
        output_usd_per_million="4.25",
    )
    try:
        with pytest.raises(BudgetedModelCallFailed) as failure:
            wrapped.turn([{"role": "user", "content": "synthetic"}], [])
        evidence = failure.value.evidence()
        assert evidence["status"] == "transport_error"
        assert evidence["code"] == ("request_timeout" if timeout else "connection_error")
        assert evidence["http_status"] is None and evidence["input_tokens"] is None
        assert budget.settlements == [{}] and len(calls) == 1
        assert "PRIVATE" not in str(failure.value) + str(evidence)
    finally:
        model._client.close()
