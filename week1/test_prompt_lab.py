import textwrap
from datetime import datetime

import httpx
import openai
import pytest

import prompt_lab
from client import Completion, ModelConfig, Pricing, SetupError
from prompt_lab import Example, Experiment, ExperimentResult, RunResult

CONFIG = ModelConfig("https://example/openai/v1", "reasoning-model", "chat-model")
PRICING = {"reasoning-model": Pricing(0.25, 2.00), "chat-model": Pricing(0.40, 1.60)}
NOW = datetime(2026, 11, 16, 9, 30)

VALID_YAML = """
pricing:
  reasoning-model: {input: 0.25, output: 2.00}
  chat-model: {input: 0.40, output: 1.60}
experiments:
  - name: minimal
    user: "Hello?"
    runs: 1
  - name: full
    system: "Be terse."
    examples:
      - user: "Q1"
        assistant: "A1"
    user: "Q2"
    temperature: 0.7
    runs: 2
    deployment: chat-model
"""


def write_yaml(tmp_path, text):
    path = tmp_path / "experiments.yaml"
    path.write_text(textwrap.dedent(text))
    return path


class FakeModelClient:
    """Fake model client: scripted per-call outcomes, never touches Azure."""

    def __init__(self, outcomes=None, rejects_temperature=()):
        self.outcomes = list(outcomes or [])
        self.rejects_temperature = set(rejects_temperature)
        self.calls = []

    def complete(self, deployment, messages, temperature=None):
        self.calls.append((deployment, messages, temperature))
        if self.outcomes and isinstance(self.outcomes[0], Exception):
            raise self.outcomes.pop(0)
        n = len(self.calls)
        applied = None if temperature is None else deployment not in self.rejects_temperature
        return Completion(f"answer {n}", 100 * n, 10 * n, applied)


def api_error(status, message):
    response = httpx.Response(status, request=httpx.Request("POST", "https://example/responses"))
    cls = {404: openai.NotFoundError, 401: openai.AuthenticationError}[status]
    return cls(message, response=response, body=None)


# -------------------------------------------------------------- YAML loading


def test_load_valid_yaml_with_defaults(tmp_path):
    lab = prompt_lab.load_lab_config(write_yaml(tmp_path, VALID_YAML))

    minimal, full = lab.experiments
    assert minimal == Experiment(name="minimal", user="Hello?", runs=1)
    assert full == Experiment(
        name="full",
        user="Q2",
        runs=2,
        system="Be terse.",
        examples=(Example("Q1", "A1"),),
        temperature=0.7,
        deployment="chat-model",
    )
    assert lab.pricing == PRICING


@pytest.mark.parametrize(
    "experiment, message",
    [
        ("- name: x\n    runs: 1", "missing required field.*user"),
        ("- user: hi\n    runs: 1", "missing required field.*name"),
        ("- name: x\n    user: hi", "missing required field.*runs"),
        ("- name: x\n    user: hi\n    runs: 0", "'runs' must be a whole number"),
        ("- name: x\n    user: hi\n    runs: 1\n    temperature: hot", "'temperature' must be a number"),
        ("- name: x\n    user: hi\n    runs: 1\n    colour: red", "unknown field.*colour"),
        ("- name: x\n    user: hi\n    runs: 1\n    examples: [{user: q}]", "example 1 must have"),
    ],
)
def test_invalid_experiments_are_setup_errors(tmp_path, experiment, message):
    text = "pricing:\n  m: {input: 1, output: 1}\nexperiments:\n  " + experiment + "\n"
    path = tmp_path / "experiments.yaml"
    path.write_text(text)

    with pytest.raises(SetupError, match=message):
        prompt_lab.load_lab_config(path)


def test_malformed_yaml_is_setup_error(tmp_path):
    with pytest.raises(SetupError, match="Invalid YAML"):
        prompt_lab.load_lab_config(write_yaml(tmp_path, "experiments: [unclosed"))


def test_missing_pricing_block_is_setup_error(tmp_path):
    with pytest.raises(SetupError, match="no 'pricing' block"):
        prompt_lab.load_lab_config(write_yaml(tmp_path, "experiments:\n  - {name: x, user: y, runs: 1}\n"))


def test_duplicate_names_are_setup_error(tmp_path):
    text = """
    pricing: {m: {input: 1, output: 1}}
    experiments:
      - {name: same, user: a, runs: 1}
      - {name: same, user: b, runs: 1}
    """
    with pytest.raises(SetupError, match="Duplicate experiment name.*same"):
        prompt_lab.load_lab_config(write_yaml(tmp_path, text))


def test_build_messages_orders_system_examples_then_user():
    experiment = Experiment(
        name="x", user="Q2", runs=1, system="S", examples=(Example("Q1", "A1"),)
    )
    assert prompt_lab.build_messages(experiment) == [
        {"role": "system", "content": "S"},
        {"role": "user", "content": "Q1"},
        {"role": "assistant", "content": "A1"},
        {"role": "user", "content": "Q2"},
    ]


# ------------------------------------------------------ deployment selection


def test_resolve_deployments_uses_default_and_explicit(tmp_path):
    lab = prompt_lab.load_lab_config(write_yaml(tmp_path, VALID_YAML))
    resolved = prompt_lab.resolve_deployments(lab.experiments, CONFIG, lab.pricing)

    assert [e.deployment for e in resolved] == ["reasoning-model", "chat-model"]


def test_unknown_deployment_is_setup_error_naming_experiment():
    experiments = [Experiment(name="typo", user="hi", runs=1, deployment="gpt-9")]
    with pytest.raises(SetupError, match="experiment 'typo': Unknown deployment 'gpt-9'"):
        prompt_lab.resolve_deployments(experiments, CONFIG, PRICING)


def test_deployment_without_pricing_is_setup_error():
    experiments = [Experiment(name="x", user="hi", runs=1, deployment="chat-model")]
    with pytest.raises(SetupError, match="No pricing for deployment 'chat-model'"):
        prompt_lab.resolve_deployments(experiments, CONFIG, {"reasoning-model": Pricing(1, 1)})


def test_run_sends_each_experiment_to_its_deployment():
    experiments = [
        Experiment(name="a", user="hi", runs=1, deployment="reasoning-model"),
        Experiment(name="b", user="hi", runs=2, deployment="chat-model", temperature=0.5),
    ]
    fake = FakeModelClient()
    prompt_lab.run_experiments(experiments, fake)

    assert [(d, t) for d, _m, t in fake.calls] == [
        ("reasoning-model", None),
        ("chat-model", 0.5),
        ("chat-model", 0.5),
    ]


# ----------------------------------------------------- temperature fallback


def test_rejected_temperature_is_reported_as_not_applied():
    experiments = [
        Experiment(name="r", user="hi", runs=1, temperature=0.2, deployment="reasoning-model"),
        Experiment(name="c", user="hi", runs=1, temperature=0.2, deployment="chat-model"),
    ]
    fake = FakeModelClient(rejects_temperature={"reasoning-model"})
    report = prompt_lab.format_report(prompt_lab.run_experiments(experiments, fake), PRICING, NOW)

    assert "## 1. r\n" in report
    assert "| Temperature | 0.2 (not applied) |" in report.split("## 2. c")[0]
    assert "| Temperature | 0.2 |" in report.split("## 2. c")[1]


# ---------------------------------------------------------- error recording


def test_failed_run_is_recorded_and_run_continues():
    experiments = [
        Experiment(name="broken", user="hi", runs=2, deployment="chat-model"),
        Experiment(name="after", user="hi", runs=1, deployment="chat-model"),
    ]
    fake = FakeModelClient(outcomes=[api_error(404, "DeploymentNotFound")])
    results = prompt_lab.run_experiments(experiments, fake)

    assert len(fake.calls) == 3
    assert results[0].runs[0].error.startswith("NotFoundError: DeploymentNotFound")
    assert results[0].runs[1].completion is not None
    assert results[1].runs[0].completion is not None

    report = prompt_lab.format_report(results, PRICING, NOW)
    assert "**Error:** `NotFoundError: DeploymentNotFound`" in report
    assert "3 runs · 1 failed" in report


def test_auth_error_mid_run_stops_everything():
    experiments = [Experiment(name="x", user="hi", runs=3, deployment="chat-model")]
    fake = FakeModelClient(outcomes=[api_error(401, "token expired")])

    with pytest.raises(SetupError, match="Authentication failed"):
        prompt_lab.run_experiments(experiments, fake)
    assert len(fake.calls) == 1


# --------------------------------------------------------- report formatting


def test_report_shows_settings_answers_tokens_and_total_cost():
    results = [
        ExperimentResult(
            Experiment(
                name="few-shot",
                user="Classify:\n1. VPN down",
                runs=1,
                system="Label tickets.",
                examples=(Example("1. Laptop dead", "1. Hardware"),),
                deployment="reasoning-model",
            ),
            [RunResult(1, completion=Completion("1. Network", 1_000_000, 0, None))],
        ),
        ExperimentResult(
            Experiment(name="temp", user="Hi", runs=2, temperature=1.5, deployment="chat-model"),
            [
                RunResult(1, completion=Completion("Hello!\n\nSecond line", 0, 1_000_000, True)),
                RunResult(2, error="APITimeoutError: Request timed out."),
            ],
        ),
    ]

    report = prompt_lab.format_report(results, PRICING, NOW)

    assert report.startswith("# Prompt Lab Results\n\nGenerated 2026-11-16 09:30 · 2 experiments")
    # settings
    assert "| Deployment | `reasoning-model` |" in report
    assert "| Deployment | `chat-model` |" in report
    assert "| Temperature | default |" in report
    assert "| Temperature | 1.5 |" in report
    assert "| Few-shot examples | 1 |" in report
    assert "| Pricing (USD / 1M tokens) | $0.4 in · $1.6 out |" in report
    assert "> Label tickets." in report
    assert "> Classify:\n> 1. VPN down" in report
    assert "> 1. Laptop dead" in report and "> 1. Hardware" in report
    assert "**System message**\n\n_none_" in report
    # answers and tokens
    assert "> Hello!\n>\n> Second line" in report
    assert "Tokens: 1000000 in · 0 out · $0.250000" in report
    assert "Tokens: 0 in · 1000000 out · $1.600000" in report
    assert "**Error:** `APITimeoutError: Request timed out.`" in report
    # totals: 0.25 + 1.60, failed run not counted
    assert "| 2 | temp | `chat-model` | 1.5 | 2 (1) | 0 | 1000000 | $1.600000 |" in report
    assert report.rstrip().split("\n")[-3] == "**Total estimated cost: $1.850000 USD**"


# --------------------------------------------------------------------- main


def test_main_writes_report_and_returns_zero(tmp_path, monkeypatch):
    monkeypatch.setattr(prompt_lab, "load_config", lambda: CONFIG)
    config_path = write_yaml(tmp_path, VALID_YAML)
    out = tmp_path / "results.md"

    code = prompt_lab.main(["--config", str(config_path), "--out", str(out)], client=FakeModelClient())

    assert code == 0
    report = out.read_text()
    assert "## 1. minimal" in report and "## 2. full" in report
    assert "Total estimated cost" in report


def test_main_returns_one_when_a_run_failed(tmp_path, monkeypatch):
    monkeypatch.setattr(prompt_lab, "load_config", lambda: CONFIG)
    fake = FakeModelClient(outcomes=[api_error(404, "missing")])
    out = tmp_path / "results.md"

    code = prompt_lab.main(
        ["--config", str(write_yaml(tmp_path, VALID_YAML)), "--out", str(out)], client=fake
    )

    assert code == 1
    assert "1 failed" in out.read_text()


def test_main_setup_error_exits_two_without_writing(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(prompt_lab, "load_config", lambda: CONFIG)
    out = tmp_path / "results.md"

    code = prompt_lab.main(
        ["--config", str(write_yaml(tmp_path, "experiments: [")), "--out", str(out)],
        client=FakeModelClient(),
    )

    assert code == 2
    assert not out.exists()
    assert "Setup error: Invalid YAML" in capsys.readouterr().err
