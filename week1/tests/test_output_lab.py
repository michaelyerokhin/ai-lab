import json
import textwrap
from datetime import datetime

import httpx
import openai
import pytest

import output_lab
from client import ModelConfig, Pricing, RawResponse, SetupError
from output_lab import LevelResult, Ticket
from schemas import Category, TicketTriage

CONFIG = ModelConfig("https://example/openai/v1", "reasoning-model", "chat-model")
PRICING = Pricing(0.40, 1.60)
NOW = datetime(2026, 11, 19, 10, 0)


def triage_json(category="Hardware", **changes):
    data = {
        "title": "t",
        "category": category,
        "priority": "low",
        "likely_cause": "c",
        "steps": ["s"],
        "escalate": False,
        **changes,
    }
    return json.dumps(data)


def write_tickets(tmp_path, text):
    path = tmp_path / "tickets.yml"
    path.write_text(textwrap.dedent(text))
    return path


class FakeClient:
    """Fake model client: replies are scripted per (ticket text, level)."""

    def __init__(self, replies, default=None):
        self.replies = replies
        self.default = default
        self.calls = []

    def respond(self, deployment, messages, *, mode, schema, temperature):
        self.calls.append((deployment, messages[-1]["content"], mode, schema, temperature))
        reply = self.replies.get((messages[-1]["content"], mode), self.default)
        if isinstance(reply, Exception):
            raise reply
        return reply


def api_error(cls, status, message):
    response = httpx.Response(status, request=httpx.Request("POST", "https://example"))
    return cls(message, response=response, body=None)


# ------------------------------------------------------------- YAML loading

VALID_TICKETS = """
tickets:
  - id: T01
    text: "Laptop won't turn on."
    expected_category: Hardware
  - id: T02
    text: "Order more coffee."
    expected_category: Other
"""


def test_load_tickets(tmp_path):
    tickets = output_lab.load_tickets(write_tickets(tmp_path, VALID_TICKETS))

    assert tickets == [
        Ticket("T01", "Laptop won't turn on.", Category.hardware),
        Ticket("T02", "Order more coffee.", Category.other),
    ]


def test_real_ticket_file_loads():
    tickets = output_lab.load_tickets(output_lab.DEFAULT_TICKETS)
    assert len(tickets) == 10


@pytest.mark.parametrize(
    "ticket, message",
    [
        ("{text: hi, expected_category: Other}", "tickets\\[0\\] is missing required field.*id"),
        ("{id: T1, expected_category: Other}", "ticket 'T1' is missing required field.*text"),
        ("{id: T1, text: hi}", "ticket 'T1' is missing required field.*expected_category"),
        ("{id: T1, text: hi, expected_category: Printer}", "'Printer' is not one of: Account"),
        ("{id: T1, text: '', expected_category: Other}", "'text' must be a non-empty string"),
        ("{id: T1, text: hi, expected_category: Other, note: x}", "unknown field.*note"),
    ],
)
def test_bad_tickets_are_setup_errors(tmp_path, ticket, message):
    path = write_tickets(tmp_path, f"tickets:\n  - {ticket}\n")
    with pytest.raises(SetupError, match=message):
        output_lab.load_tickets(path)


def test_duplicate_ids_are_setup_error(tmp_path):
    text = "tickets:\n  - {id: T1, text: a, expected_category: Other}\n" \
           "  - {id: T1, text: b, expected_category: Other}\n"
    with pytest.raises(SetupError, match="Duplicate ticket id.*T1"):
        output_lab.load_tickets(write_tickets(tmp_path, text))


@pytest.mark.parametrize("text", ["tickets: [", "tickets: []", "nothing: here"])
def test_bad_files_are_setup_errors(tmp_path, text):
    with pytest.raises(SetupError):
        output_lab.load_tickets(write_tickets(tmp_path, text))


# ---------------------------------------------------------------- running

TICKET = Ticket("T01", "Laptop dead", Category.hardware)


def test_each_ticket_runs_all_three_levels_once_at_temperature_zero():
    fake = FakeClient({}, default=RawResponse(triage_json(), None, 1, 1))

    output_lab.run_lab([TICKET], fake, "chat-model")

    assert fake.calls == [
        ("chat-model", "Laptop dead", "prompt", None, 0),
        ("chat-model", "Laptop dead", "json_mode", None, 0),
        ("chat-model", "Laptop dead", "schema", TicketTriage, 0),
    ]


def test_scoring_valid_wrong_and_invalid():
    fake = FakeClient(
        {
            ("Laptop dead", "prompt"): RawResponse("```json\n" + triage_json() + "\n```", None, 1, 1),
            ("Laptop dead", "json_mode"): RawResponse(triage_json("Network"), None, 1, 1),
            ("Laptop dead", "schema"): RawResponse(triage_json(), None, 1, 1),
        }
    )
    prompt, json_mode, schema = output_lab.run_lab([TICKET], fake, "chat-model")

    assert (prompt.status, prompt.reason[:12]) == ("invalid", "Invalid JSON")
    assert (json_mode.status, json_mode.category, json_mode.correct) == ("valid", Category.network, False)
    assert (schema.status, schema.correct) == ("valid", True)


# ------------------------------------------------------ refusals and errors


def test_refusal_is_recorded_counted_and_run_continues():
    tickets = [TICKET, Ticket("T02", "Other ticket", Category.other)]
    fake = FakeClient(
        {("Laptop dead", "schema"): RawResponse("", "I can't assist with that.", 7, 2)},
        default=RawResponse(triage_json("Other"), None, 1, 1),
    )

    results = output_lab.run_lab(tickets, fake, "chat-model")

    assert len(results) == 6  # nothing skipped after the refusal
    refused = results[2]
    assert (refused.status, refused.reason, refused.correct) == ("refused", "I can't assist with that.", False)
    assert (refused.input_tokens, refused.output_tokens) == (7, 2)
    schema_summary = output_lab.summarize(results, PRICING)[2]
    assert (schema_summary.refused, schema_summary.valid, schema_summary.errors) == (1, 1, 0)

    report = output_lab.format_report(tickets, results, output_lab.summarize(results, PRICING), "chat-model", NOW)
    assert "**`schema`**: ⚠️ refused: I can't assist with that." in report


def test_single_call_error_is_recorded_and_run_continues():
    fake = FakeClient(
        {("Laptop dead", "prompt"): api_error(openai.InternalServerError, 500, "Server blew up")},
        default=RawResponse(triage_json(), None, 1, 1),
    )

    results = output_lab.run_lab([TICKET], fake, "chat-model")

    assert [r.status for r in results] == ["error", "valid", "valid"]
    assert results[0].reason.startswith("InternalServerError: Server blew up")


def test_auth_error_stops_the_run():
    fake = FakeClient({("Laptop dead", "prompt"): api_error(openai.AuthenticationError, 401, "expired")})

    with pytest.raises(SetupError, match="Authentication failed"):
        output_lab.run_lab([TICKET], fake, "chat-model")
    assert len(fake.calls) == 1


# ------------------------------------------------------- summary percentages


def make_results(level, outcomes):
    """outcomes: list of 'correct' | 'wrong' | 'invalid' | 'refused' | 'error'."""
    results = []
    for n, outcome in enumerate(outcomes):
        status = {"correct": "valid", "wrong": "valid"}.get(outcome, outcome)
        tokens = (0, 0) if outcome == "error" else (100_000, 50_000)
        category = {"correct": Category.other, "wrong": Category.hardware}.get(outcome)
        results.append(
            LevelResult(f"T{n}", level, status, category=category, correct=outcome == "correct",
                        input_tokens=tokens[0], output_tokens=tokens[1])
        )
    return results


def test_summary_percentages_use_all_tickets_as_denominator():
    results = (
        make_results("prompt", ["correct"] * 5 + ["wrong"] * 2 + ["invalid"] * 2 + ["refused"])
        + make_results("json_mode", ["correct"] * 8 + ["wrong", "error"])
        + make_results("schema", ["correct"] * 10)
    )

    prompt, json_mode, schema = output_lab.summarize(results, PRICING)

    assert (prompt.total, prompt.valid, prompt.correct, prompt.refused, prompt.errors) == (10, 7, 5, 1, 0)
    assert (prompt.pct_valid, prompt.pct_correct) == (70.0, 50.0)
    assert (json_mode.pct_valid, json_mode.pct_correct, json_mode.errors) == (90.0, 80.0, 1)
    assert (schema.pct_valid, schema.pct_correct) == (100.0, 100.0)
    # 10 calls x (100k in, 50k out) at $0.40 / $1.60 per 1M = 10 x $0.12
    assert prompt.input_tokens == 1_000_000 and prompt.output_tokens == 500_000
    assert prompt.cost == pytest.approx(1.20)
    assert json_mode.cost == pytest.approx(1.08)  # the errored call used no tokens


def test_summary_table_in_report():
    results = make_results("prompt", ["correct", "invalid"]) + make_results(
        "json_mode", ["correct", "wrong"]) + make_results("schema", ["correct", "refused"])
    tickets = [Ticket("T0", "a", Category.other), Ticket("T1", "b", Category.other)]

    report = output_lab.format_report(
        tickets, results, output_lab.summarize(results, PRICING), "chat-model", NOW
    )

    assert "| `prompt` | 50% (1/2) | 50% (1/2) | 0 | 0 | 200000 | 100000 | $0.240000 |" in report
    assert "| `json_mode` | 100% (2/2) | 50% (1/2) | 0 | 0 |" in report
    assert "| `schema` | 50% (1/2) | 50% (1/2) | 1 | 0 |" in report
    assert "**Total estimated cost: $0.720000 USD**" in report


# ------------------------------------------------------------------- report


def test_report_shows_raw_output_validity_and_category():
    fake = FakeClient(
        {
            ("Laptop dead", "prompt"): RawResponse("```json\n" + triage_json() + "\n```", None, 1, 1),
            ("Laptop dead", "json_mode"): RawResponse(triage_json("Network"), None, 1, 1),
            ("Laptop dead", "schema"): RawResponse(triage_json(), None, 1, 1),
        }
    )
    results = output_lab.run_lab([TICKET], fake, "chat-model")
    report = output_lab.format_report(
        [TICKET], results, output_lab.summarize(results, PRICING), "chat-model", NOW
    )

    assert "### T01 · expected Hardware\n\n> Laptop dead" in report
    assert "**`prompt`**: ❌ invalid shape: Invalid JSON" in report
    assert "````\n```json\n" in report  # raw output with its own fence stays intact
    assert "**`json_mode`**: ✅ valid shape · ❌ category wrong: got Network, expected Hardware" in report
    assert "**`schema`**: ✅ valid shape · ✅ category correct (Hardware)" in report
    assert "deployment `chat-model` · temperature 0" in report


# --------------------------------------------------------------------- main


def test_main_writes_report(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(output_lab, "load_config", lambda: CONFIG)
    monkeypatch.setattr(output_lab, "load_pricing", lambda: {"chat-model": PRICING})
    out = tmp_path / "report.md"
    fake = FakeClient({}, default=RawResponse(triage_json(), None, 1, 1))

    code = output_lab.main(
        ["--tickets", str(write_tickets(tmp_path, VALID_TICKETS)), "--out", str(out)], client=fake
    )

    assert code == 0
    assert "### T02 · expected Other" in out.read_text()
    assert {call[0] for call in fake.calls} == {"chat-model"}


def test_main_setup_error_exits_two(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(output_lab, "load_config", lambda: CONFIG)
    monkeypatch.setattr(output_lab, "load_pricing", lambda: {"reasoning-model": PRICING})

    code = output_lab.main(["--out", str(tmp_path / "r.md")], client=FakeClient({}))

    assert code == 2
    assert "No pricing for deployment 'chat-model'" in capsys.readouterr().err
