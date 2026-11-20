import json

import httpx
import openai
import pytest

import triage
from client import ModelConfig, RawResponse
from schemas import Category, TicketTriage

CONFIG = ModelConfig("https://example/openai/v1", "reasoning-model", "chat-model")
VALID = json.dumps(
    {
        "title": "Printer jam",
        "category": "Hardware",
        "priority": "medium",
        "likely_cause": "Paper jam",
        "steps": ["Clear the jam"],
        "escalate": False,
    }
)


class FakeClient:
    def __init__(self, reply=None, error=None):
        self.reply = reply
        self.error = error
        self.calls = []

    def respond(self, deployment, messages, **kwargs):
        self.calls.append((deployment, messages, kwargs))
        if self.error:
            raise self.error
        return self.reply


def test_triage_ticket_uses_schema_mode_at_temperature_zero():
    fake = FakeClient(RawResponse(VALID, None, 10, 20))

    result = triage.triage_ticket("Printer on floor 2 is jammed", fake, "chat-model")

    assert result.category is Category.hardware
    deployment, messages, kwargs = fake.calls[0]
    assert deployment == "chat-model"
    assert messages[-1] == {"role": "user", "content": "Printer on floor 2 is jammed"}
    assert kwargs == {"mode": "schema", "schema": TicketTriage, "temperature": 0}


def test_triage_ticket_raises_on_refusal():
    fake = FakeClient(RawResponse("", "I can't help with that.", 5, 0))
    with pytest.raises(triage.TriageRefused, match="can't help"):
        triage.triage_ticket("...", fake, "chat-model")


def test_triage_ticket_raises_on_invalid_output():
    fake = FakeClient(RawResponse('{"title": "x"}', None, 5, 5))
    with pytest.raises(triage.TriageInvalid, match="Field required"):
        triage.triage_ticket("...", fake, "chat-model")


def test_cli_prints_valid_triage_json(monkeypatch, capsys):
    monkeypatch.setattr(triage, "load_config", lambda: CONFIG)
    fake = FakeClient(RawResponse(VALID, None, 10, 20))

    assert triage.main(["Printer on floor 2 is jammed"], client=fake) == 0

    printed = capsys.readouterr().out
    assert TicketTriage.model_validate_json(printed).category is Category.hardware
    assert fake.calls[0][0] == "chat-model"  # NONREASONING_DEPLOYMENT


def test_cli_refusal_exits_one(monkeypatch, capsys):
    monkeypatch.setattr(triage, "load_config", lambda: CONFIG)
    fake = FakeClient(RawResponse("", "I can't help with that.", 5, 0))

    assert triage.main(["..."], client=fake) == 1
    assert "Refused: I can't help with that." in capsys.readouterr().err


def test_cli_api_error_exits_one(monkeypatch, capsys):
    monkeypatch.setattr(triage, "load_config", lambda: CONFIG)
    response = httpx.Response(404, request=httpx.Request("POST", "https://example"))
    fake = FakeClient(error=openai.NotFoundError("DeploymentNotFound", response=response, body=None))

    assert triage.main(["..."], client=fake) == 1
    assert "API error: NotFoundError" in capsys.readouterr().err
