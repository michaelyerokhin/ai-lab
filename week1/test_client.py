import logging
from types import SimpleNamespace

import httpx
import openai
import pytest
from azure.core.exceptions import ClientAuthenticationError

import client
from client import ModelClient, ModelConfig, Pricing, SetupError

CONFIG = ModelConfig("https://example/openai/v1", "reasoning-model", "chat-model")


def bad_request(message, param=None):
    response = httpx.Response(400, request=httpx.Request("POST", "https://example/responses"))
    return openai.BadRequestError(
        message, response=response, body={"message": message, "param": param}
    )


def fake_response(text="answer", input_tokens=10, output_tokens=20):
    return SimpleNamespace(
        output_text=text,
        usage=SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens),
    )


class FakeSDK:
    """Stands in for openai.OpenAI: records calls and replays scripted outcomes."""

    def __init__(self, *outcomes):
        self.outcomes = list(outcomes)
        self.calls = []
        self.responses = SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


# ------------------------------------------------------------ configuration


def test_load_config_reports_missing_environment_variables(monkeypatch):
    monkeypatch.setattr(client, "load_dotenv", lambda *_args: None)
    for name in ("AZURE_ENDPOINT", "DEPLOYMENT_NAME", "NONREASONING_DEPLOYMENT"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("AZURE_ENDPOINT", "https://example")

    with pytest.raises(SetupError, match="DEPLOYMENT_NAME, NONREASONING_DEPLOYMENT"):
        client.load_config()


def test_load_config_reads_both_deployments(monkeypatch):
    monkeypatch.setattr(client, "load_dotenv", lambda *_args: None)
    monkeypatch.setenv("AZURE_ENDPOINT", "https://example")
    monkeypatch.setenv("DEPLOYMENT_NAME", "reasoning-model")
    monkeypatch.setenv("NONREASONING_DEPLOYMENT", "chat-model")

    assert client.load_config() == ModelConfig("https://example", "reasoning-model", "chat-model")


# ----------------------------------------------------- deployment selection


def test_resolve_deployment_defaults_when_omitted():
    assert CONFIG.resolve_deployment(None) == "reasoning-model"


def test_resolve_deployment_accepts_nonreasoning_deployment():
    assert CONFIG.resolve_deployment("chat-model") == "chat-model"


def test_resolve_deployment_rejects_unknown_name():
    with pytest.raises(SetupError, match="Unknown deployment 'gpt-typo'"):
        CONFIG.resolve_deployment("gpt-typo")


# ------------------------------------------------------------------ pricing


def test_estimate_cost_uses_deployment_rates():
    assert client.estimate_cost_usd(1_000_000, 1_000_000, Pricing(0.25, 2.0)) == pytest.approx(2.25)


def test_pricing_for_missing_deployment_is_setup_error():
    with pytest.raises(SetupError, match="No pricing for deployment 'chat-model'"):
        client.pricing_for({"reasoning-model": Pricing(1, 1)}, "chat-model")


@pytest.mark.parametrize(
    "raw",
    [None, {}, {"m": {"input": 1}}, {"m": {"input": -1, "output": 1}}, {"m": {"input": "x", "output": 1}}],
)
def test_parse_pricing_rejects_bad_values(raw):
    with pytest.raises(SetupError):
        client.parse_pricing(raw)


# ----------------------------------------------------- temperature fallback


def test_temperature_is_sent_when_model_accepts_it():
    sdk = FakeSDK(fake_response())
    completion = ModelClient(sdk).complete("chat-model", [{"role": "user", "content": "hi"}], 0.7)

    assert completion.temperature_applied is True
    assert sdk.calls[0]["temperature"] == 0.7


def test_temperature_rejection_logs_warning_and_retries_without_it(caplog):
    sdk = FakeSDK(
        bad_request("Unsupported value: 'temperature' does not support 0.2", param="temperature"),
        fake_response("fallback answer", 5, 7),
    )
    messages = [{"role": "user", "content": "hi"}]

    with caplog.at_level(logging.WARNING):
        completion = ModelClient(sdk).complete("reasoning-model", messages, 0.2)

    assert completion.text == "fallback answer"
    assert completion.temperature_applied is False
    assert (completion.input_tokens, completion.output_tokens) == (5, 7)
    assert sdk.calls == [
        {"model": "reasoning-model", "input": messages, "temperature": 0.2},
        {"model": "reasoning-model", "input": messages},
    ]
    assert "rejected temperature=0.2" in caplog.text


def test_other_bad_requests_are_not_swallowed():
    sdk = FakeSDK(bad_request("Invalid prompt: content filtered"))

    with pytest.raises(openai.BadRequestError):
        ModelClient(sdk).complete("chat-model", [{"role": "user", "content": "hi"}], 0.5)
    assert len(sdk.calls) == 1


def test_no_temperature_requested_means_none_applied():
    sdk = FakeSDK(fake_response())
    completion = ModelClient(sdk).complete("chat-model", [{"role": "user", "content": "hi"}])

    assert completion.temperature_applied is None
    assert "temperature" not in sdk.calls[0]


def test_missing_usage_raises_runtime_error():
    sdk = FakeSDK(SimpleNamespace(output_text="x", usage=None))
    with pytest.raises(RuntimeError, match="token usage"):
        ModelClient(sdk).complete("chat-model", [{"role": "user", "content": "hi"}])


# ----------------------------------------------------------- authentication


def test_auth_failure_is_setup_error(monkeypatch):
    def provider():
        raise ClientAuthenticationError("DefaultAzureCredential failed to retrieve a token")

    monkeypatch.setattr(client, "DefaultAzureCredential", lambda: object())
    monkeypatch.setattr(client, "get_bearer_token_provider", lambda cred, scope: provider)

    with pytest.raises(SetupError, match="Azure authentication failed.*az login"):
        client.create_model_client(CONFIG)


def test_create_model_client_uses_foundry_endpoint_and_token(monkeypatch):
    created = {}
    monkeypatch.setattr(client, "DefaultAzureCredential", lambda: object())
    monkeypatch.setattr(client, "get_bearer_token_provider", lambda cred, scope: lambda: "token")
    monkeypatch.setattr(client.openai, "OpenAI", lambda **kwargs: created.update(kwargs) or "sdk")

    assert isinstance(client.create_model_client(CONFIG), ModelClient)
    assert created["base_url"] == CONFIG.endpoint
    assert created["api_key"]() == "token"
