from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import hello_model


def test_load_config_reports_missing_environment_variables(monkeypatch):
    monkeypatch.setattr(hello_model, "load_dotenv", lambda *_args: None)
    monkeypatch.delenv("AZURE_ENDPOINT", raising=False)
    monkeypatch.delenv("DEPLOYMENT_NAME", raising=False)

    with pytest.raises(
        ValueError,
        match="Missing required environment variable\\(s\\): AZURE_ENDPOINT, DEPLOYMENT_NAME",
    ):
        hello_model.load_config()


def test_estimate_cost_usd_uses_input_and_output_rates():
    assert hello_model.estimate_cost_usd(1_000_000, 1_000_000) == pytest.approx(2.25)


def test_main_prints_answer_usage_and_estimated_cost(monkeypatch, capsys):
    config = hello_model.ModelConfig(
        endpoint="https://example.services.ai.azure.com/openai/v1",
        deployment_name="gpt-5-mini",
    )
    monkeypatch.setattr(hello_model, "load_config", lambda: config)
    credential = object()
    monkeypatch.setattr(hello_model, "DefaultAzureCredential", lambda: credential)

    def create_token_provider(actual_credential, scope):
        assert actual_credential is credential
        assert scope == "https://ai.azure.com/.default"
        return "bearer-token"

    monkeypatch.setattr(hello_model, "get_bearer_token_provider", create_token_provider)

    client = Mock()
    client.responses.create.return_value = SimpleNamespace(
        output_text="A managed service provider.",
        usage=SimpleNamespace(input_tokens=1000, output_tokens=2000),
    )

    def create_client(**kwargs):
        assert kwargs == {
            "base_url": config.endpoint,
            "api_key": "bearer-token",
        }
        return client

    monkeypatch.setattr(
        hello_model,
        "import_module",
        lambda module_name: SimpleNamespace(OpenAI=create_client)
        if module_name == "openai"
        else None,
    )

    assert hello_model.main(["What is an MSP?"]) == 0

    assert capsys.readouterr().out == (
        "A managed service provider.\n"
        "Input tokens: 1000 | Output tokens: 2000 | Estimated cost: $0.004250 USD\n"
    )
    client.responses.create.assert_called_once_with(
        model="gpt-5-mini",
        input="What is an MSP?",
    )
