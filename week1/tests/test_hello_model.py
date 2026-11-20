import hello_model
from client import Completion, ModelConfig, Pricing, SetupError


class FakeClient:
    def __init__(self):
        self.calls = []

    def complete(self, deployment, messages, temperature=None):
        self.calls.append((deployment, messages, temperature))
        return Completion("A managed service provider.", 1000, 2000, None)


def test_main_prints_answer_usage_and_estimated_cost(monkeypatch, capsys):
    config = ModelConfig("https://example/openai/v1", "default-model", "other-model")
    fake = FakeClient()
    monkeypatch.setattr(hello_model, "load_config", lambda: config)
    monkeypatch.setattr(
        hello_model, "load_pricing", lambda: {"default-model": Pricing(0.25, 2.00)}
    )
    monkeypatch.setattr(hello_model, "create_model_client", lambda cfg: fake)

    assert hello_model.main(["What is an MSP?"]) == 0

    assert capsys.readouterr().out == (
        "A managed service provider.\n"
        "Input tokens: 1000 | Output tokens: 2000 | Estimated cost: $0.004250 USD\n"
    )
    assert fake.calls == [
        ("default-model", [{"role": "user", "content": "What is an MSP?"}], None)
    ]


def test_main_reports_setup_error(monkeypatch, capsys):
    def fail():
        raise SetupError("Missing required environment variable(s): AZURE_ENDPOINT.")

    monkeypatch.setattr(hello_model, "load_config", fail)

    assert hello_model.main(["hi"]) == 2
    assert "Setup error: Missing required" in capsys.readouterr().err
