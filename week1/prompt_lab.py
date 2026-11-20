"""Run prompt experiments from experiments.yaml and write a Markdown comparison report."""

import argparse
import dataclasses
import logging
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol, Sequence

import openai
import yaml
from azure.core.exceptions import ClientAuthenticationError

from client import (
    Completion,
    ModelConfig,
    Pricing,
    SetupError,
    create_model_client,
    estimate_cost_usd,
    load_config,
    parse_pricing,
    pricing_for,
)

WEEK1_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG = WEEK1_DIR / "config" / "experiments.yaml"
DEFAULT_OUTPUT = WEEK1_DIR / "docs" / "results.md"

REQUIRED_KEYS = {"name", "user", "runs"}
OPTIONAL_KEYS = {"system", "examples", "temperature", "deployment"}

logger = logging.getLogger("prompt_lab")


class CompletionClient(Protocol):
    def complete(
        self, deployment: str, messages: list[dict[str, str]], temperature: float | None = None
    ) -> Completion: ...


@dataclass(frozen=True)
class Example:
    user: str
    assistant: str


@dataclass(frozen=True)
class Experiment:
    name: str
    user: str
    runs: int
    system: str | None = None
    examples: tuple[Example, ...] = ()
    temperature: float | None = None
    deployment: str | None = None  # None means "use the default deployment"


@dataclass(frozen=True)
class LabConfig:
    experiments: list[Experiment]
    pricing: dict[str, Pricing]


@dataclass(frozen=True)
class RunResult:
    run: int
    completion: Completion | None = None
    error: str | None = None


@dataclass
class ExperimentResult:
    experiment: Experiment  # deployment is always resolved here
    runs: list[RunResult] = field(default_factory=list)


# ---------------------------------------------------------------- YAML loading


def _require_str(value: Any, where: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SetupError(f"{where} must be a non-empty string.")
    return value


def _parse_experiment(raw: Any, index: int) -> Experiment:
    label = f"experiments[{index}]"
    if not isinstance(raw, dict):
        raise SetupError(f"{label} must be a mapping.")
    if isinstance(raw.get("name"), str):
        label = f"experiment '{raw['name']}'"

    missing = REQUIRED_KEYS - raw.keys()
    if missing:
        raise SetupError(f"{label} is missing required field(s): {', '.join(sorted(missing))}.")
    unknown = raw.keys() - REQUIRED_KEYS - OPTIONAL_KEYS
    if unknown:
        raise SetupError(f"{label} has unknown field(s): {', '.join(sorted(unknown))}.")

    runs = raw["runs"]
    if isinstance(runs, bool) or not isinstance(runs, int) or runs < 1:
        raise SetupError(f"{label}: 'runs' must be a whole number of at least 1.")

    temperature = raw.get("temperature")
    if temperature is not None and (
        isinstance(temperature, bool) or not isinstance(temperature, (int, float))
    ):
        raise SetupError(f"{label}: 'temperature' must be a number.")

    examples_raw = raw.get("examples") or []
    if not isinstance(examples_raw, list):
        raise SetupError(f"{label}: 'examples' must be a list of user/assistant pairs.")
    examples = []
    for n, example in enumerate(examples_raw, start=1):
        if not isinstance(example, dict) or set(example) != {"user", "assistant"}:
            raise SetupError(f"{label}: example {n} must have exactly 'user' and 'assistant'.")
        examples.append(
            Example(
                user=_require_str(example["user"], f"{label}: example {n} user"),
                assistant=_require_str(example["assistant"], f"{label}: example {n} assistant"),
            )
        )

    system = raw.get("system")
    deployment = raw.get("deployment")
    return Experiment(
        name=_require_str(raw["name"], f"{label}: 'name'"),
        user=_require_str(raw["user"], f"{label}: 'user'"),
        runs=runs,
        system=None if system is None else _require_str(system, f"{label}: 'system'"),
        examples=tuple(examples),
        temperature=None if temperature is None else float(temperature),
        deployment=None if deployment is None else _require_str(deployment, f"{label}: 'deployment'"),
    )


def load_lab_config(path: Path) -> LabConfig:
    """Load and validate experiments.yaml. Any problem raises SetupError."""
    try:
        data = yaml.safe_load(Path(path).read_text())
    except OSError as error:
        raise SetupError(f"Could not read {path}: {error}") from error
    except yaml.YAMLError as error:
        raise SetupError(f"Invalid YAML in {path}: {error}") from error

    if not isinstance(data, dict):
        raise SetupError(f"{path} must contain a mapping with 'experiments' and 'pricing'.")
    unknown = data.keys() - {"experiments", "pricing"}
    if unknown:
        raise SetupError(f"{path} has unknown top-level key(s): {', '.join(sorted(unknown))}.")
    if "pricing" not in data:
        raise SetupError(f"{path} has no 'pricing' block.")
    raw_experiments = data.get("experiments")
    if not isinstance(raw_experiments, list) or not raw_experiments:
        raise SetupError(f"{path} must have a non-empty 'experiments' list.")

    experiments = [_parse_experiment(raw, i) for i, raw in enumerate(raw_experiments)]
    names = [e.name for e in experiments]
    duplicates = sorted({n for n in names if names.count(n) > 1})
    if duplicates:
        raise SetupError(f"Duplicate experiment name(s): {', '.join(duplicates)}.")

    return LabConfig(experiments=experiments, pricing=parse_pricing(data["pricing"]))


def resolve_deployments(
    experiments: list[Experiment], config: ModelConfig, pricing: dict[str, Pricing]
) -> list[Experiment]:
    """Fill in each experiment's deployment and check it has pricing, before any API call."""
    resolved = []
    for experiment in experiments:
        try:
            deployment = config.resolve_deployment(experiment.deployment)
            pricing_for(pricing, deployment)
        except SetupError as error:
            raise SetupError(f"experiment '{experiment.name}': {error}") from error
        resolved.append(dataclasses.replace(experiment, deployment=deployment))
    return resolved


# ------------------------------------------------------------------- running


def build_messages(experiment: Experiment) -> list[dict[str, str]]:
    messages = []
    if experiment.system:
        messages.append({"role": "system", "content": experiment.system})
    for example in experiment.examples:
        messages.append({"role": "user", "content": example.user})
        messages.append({"role": "assistant", "content": example.assistant})
    messages.append({"role": "user", "content": experiment.user})
    return messages


def _describe_error(error: Exception) -> str:
    return " ".join(f"{type(error).__name__}: {error}".split())


def run_experiments(
    experiments: list[Experiment], client: CompletionClient
) -> list[ExperimentResult]:
    """Run every experiment in order. Per-run API errors are recorded, not raised."""
    total = sum(e.runs for e in experiments)
    done = 0
    results = []
    for experiment in experiments:
        result = ExperimentResult(experiment)
        messages = build_messages(experiment)
        for run in range(1, experiment.runs + 1):
            done += 1
            try:
                completion = client.complete(
                    experiment.deployment, messages, experiment.temperature
                )
                result.runs.append(RunResult(run, completion=completion))
                status = "ok"
            except (
                openai.AuthenticationError,
                openai.PermissionDeniedError,
                ClientAuthenticationError,
            ) as error:
                raise SetupError(f"Authentication failed mid-run: {_describe_error(error)}") from error
            except (openai.OpenAIError, RuntimeError) as error:
                result.runs.append(RunResult(run, error=_describe_error(error)))
                status = "FAILED"
            logger.info("[%d/%d] %s run %d: %s", done, total, experiment.name, run, status)
        results.append(result)
    return results


# ------------------------------------------------------------------- report


def _quote(text: str) -> str:
    return "\n".join(f"> {line}" if line.strip() else ">" for line in text.strip().splitlines())


def _cell(text: str) -> str:
    return text.replace("|", "\\|")


def _temperature_label(result: ExperimentResult) -> str:
    requested = result.experiment.temperature
    if requested is None:
        return "default"
    flags = [r.completion.temperature_applied for r in result.runs if r.completion]
    if flags and not all(flags):
        return f"{requested:g} (not applied)"
    if not flags:
        return f"{requested:g} (unknown: all runs failed)"
    return f"{requested:g}"


def _totals(result: ExperimentResult, pricing: dict[str, Pricing]) -> tuple[int, int, float]:
    completions = [r.completion for r in result.runs if r.completion]
    input_tokens = sum(c.input_tokens for c in completions)
    output_tokens = sum(c.output_tokens for c in completions)
    rate = pricing[result.experiment.deployment]
    return input_tokens, output_tokens, estimate_cost_usd(input_tokens, output_tokens, rate)


def format_report(
    results: list[ExperimentResult],
    pricing: dict[str, Pricing],
    generated_at: datetime,
) -> str:
    run_count = sum(len(r.runs) for r in results)
    failed = sum(1 for r in results for run in r.runs if run.error)
    lines = [
        "# Prompt Lab Results",
        "",
        f"Generated {generated_at:%Y-%m-%d %H:%M} · {len(results)} experiments · "
        f"{run_count} runs · {failed} failed",
        "",
    ]

    for number, result in enumerate(results, start=1):
        exp = result.experiment
        rate = pricing[exp.deployment]
        lines += [
            f"## {number}. {exp.name}",
            "",
            "| Setting | Value |",
            "|---|---|",
            f"| Deployment | `{exp.deployment}` |",
            f"| Temperature | {_temperature_label(result)} |",
            f"| Runs | {exp.runs} |",
            f"| Few-shot examples | {len(exp.examples)} |",
            f"| Pricing (USD / 1M tokens) | ${rate.input_per_million:g} in · "
            f"${rate.output_per_million:g} out |",
            "",
            "**System message**",
            "",
            _quote(exp.system) if exp.system else "_none_",
            "",
        ]
        if exp.examples:
            lines += ["<details><summary>Few-shot examples</summary>", ""]
            for n, example in enumerate(exp.examples, start=1):
                lines += [
                    f"Example {n}, user:",
                    "",
                    _quote(example.user),
                    "",
                    f"Example {n}, assistant:",
                    "",
                    _quote(example.assistant),
                    "",
                ]
            lines += ["</details>", ""]
        lines += ["**User message**", "", _quote(exp.user), ""]

        for run in result.runs:
            lines += [f"### Run {run.run}", ""]
            if run.error:
                lines += [f"**Error:** `{run.error}`", ""]
                continue
            c = run.completion
            cost = estimate_cost_usd(c.input_tokens, c.output_tokens, rate)
            lines += [
                _quote(c.text) if c.text.strip() else "_(empty answer)_",
                "",
                f"Tokens: {c.input_tokens} in · {c.output_tokens} out · ${cost:.6f}",
                "",
            ]

        input_tokens, output_tokens, cost = _totals(result, pricing)
        lines += [
            f"**Experiment total:** {input_tokens} in · {output_tokens} out · ${cost:.6f}",
            "",
        ]

    lines += [
        "## Summary",
        "",
        "| # | Experiment | Deployment | Temperature | Runs (failed) | Input tokens "
        "| Output tokens | Est. cost (USD) |",
        "|---|---|---|---|---|---|---|---|",
    ]
    grand_in = grand_out = 0
    grand_cost = 0.0
    for number, result in enumerate(results, start=1):
        input_tokens, output_tokens, cost = _totals(result, pricing)
        grand_in += input_tokens
        grand_out += output_tokens
        grand_cost += cost
        failed_runs = sum(1 for r in result.runs if r.error)
        lines.append(
            f"| {number} | {_cell(result.experiment.name)} | `{result.experiment.deployment}` "
            f"| {_temperature_label(result)} | {len(result.runs)} ({failed_runs}) "
            f"| {input_tokens} | {output_tokens} | ${cost:.6f} |"
        )
    lines += [
        f"| | **Total** | | | {run_count} ({failed}) | **{grand_in}** | **{grand_out}** "
        f"| **${grand_cost:.6f}** |",
        "",
        f"**Total estimated cost: ${grand_cost:.6f} USD**",
        "",
        "_Estimates use the rates in the `pricing:` block of experiments.yaml; "
        "failed runs are not counted._",
        "",
    ]
    return "\n".join(lines)


# --------------------------------------------------------------------- main


def main(argv: Sequence[str] | None = None, client: CompletionClient | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run prompt experiments against Foundry models.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG, help="experiments YAML")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT, help="Markdown report path")
    args = parser.parse_args(argv)
    # WARNING for everything (keeps Azure/HTTP chatter out), INFO for our progress lines.
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    logger.setLevel(logging.INFO)

    try:
        model_config = load_config()
        lab = load_lab_config(args.config)
        experiments = resolve_deployments(lab.experiments, model_config, lab.pricing)
        if client is None:
            client = create_model_client(model_config)
        results = run_experiments(experiments, client)
    except SetupError as error:
        print(f"Setup error: {error}", file=sys.stderr)
        return 2

    args.out.write_text(format_report(results, lab.pricing, datetime.now()))
    failed = sum(1 for r in results for run in r.runs if run.error)
    print(f"Wrote {args.out} ({len(results)} experiments, {failed} failed runs).")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
