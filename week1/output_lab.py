"""Run every test ticket through three levels of output control and compare them.

Levels (same system message, same scoring):
  prompt     the system message asks for JSON and lists the fields
  json_mode  the same, plus JSON mode turned on
  schema     structured outputs constrained to TicketTriage

Each output is scored the same way: load it into TicketTriage with Pydantic.
There are no retries: failures are what this lab measures.
"""

import argparse
import logging
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Sequence

import openai
import pydantic
import yaml
from azure.core.exceptions import ClientAuthenticationError

from client import (
    OUTPUT_MODES,
    Pricing,
    SetupError,
    create_model_client,
    estimate_cost_usd,
    load_config,
    load_pricing,
    pricing_for,
)
from schemas import Category, TicketTriage, build_messages, validate_output
from triage import TEMPERATURE, RespondingClient

WEEK1_DIR = Path(__file__).resolve().parent
DEFAULT_TICKETS = WEEK1_DIR / "config" / "tickets_list.yml"
DEFAULT_OUTPUT = WEEK1_DIR / "docs" / "ticket_output_results.md"
LEVELS = OUTPUT_MODES  # ("prompt", "json_mode", "schema")
LEVEL_DESCRIPTIONS = {
    "prompt": "system message asks for JSON and lists the fields",
    "json_mode": "same system message + JSON mode",
    "schema": "structured outputs with the TicketTriage model (`responses.parse`)",
}
TICKET_KEYS = {"id", "text", "expected_category"}

logger = logging.getLogger("output_lab")


@dataclass(frozen=True)
class Ticket:
    id: str
    text: str
    expected_category: Category


@dataclass(frozen=True)
class LevelResult:
    ticket_id: str
    level: str
    status: str  # "valid" | "invalid" | "refused" | "error"
    raw: str | None = None
    reason: str | None = None  # why invalid, the refusal message, or the error
    category: Category | None = None
    correct: bool = False
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass(frozen=True)
class LevelSummary:
    level: str
    total: int
    valid: int
    correct: int
    refused: int
    errors: int
    input_tokens: int
    output_tokens: int
    cost: float

    @property
    def pct_valid(self) -> float:
        return 100 * self.valid / self.total if self.total else 0.0

    @property
    def pct_correct(self) -> float:
        return 100 * self.correct / self.total if self.total else 0.0


# --------------------------------------------------------------- YAML loading


def load_tickets(path: Path) -> list[Ticket]:
    """Load and validate the ticket list. Any problem raises SetupError."""
    try:
        data = yaml.safe_load(Path(path).read_text())
    except OSError as error:
        raise SetupError(f"Could not read {path}: {error}") from error
    except yaml.YAMLError as error:
        raise SetupError(f"Invalid YAML in {path}: {error}") from error

    raw_tickets = data.get("tickets") if isinstance(data, dict) else None
    if not isinstance(raw_tickets, list) or not raw_tickets:
        raise SetupError(f"{path} must have a non-empty 'tickets' list.")

    allowed = ", ".join(c.value for c in Category)
    tickets = []
    for index, raw in enumerate(raw_tickets):
        label = f"tickets[{index}]"
        if not isinstance(raw, dict):
            raise SetupError(f"{label} must be a mapping.")
        if raw.get("id") is not None:
            label = f"ticket '{raw['id']}'"
        missing = TICKET_KEYS - raw.keys()
        if missing:
            raise SetupError(f"{label} is missing required field(s): {', '.join(sorted(missing))}.")
        unknown = raw.keys() - TICKET_KEYS
        if unknown:
            raise SetupError(f"{label} has unknown field(s): {', '.join(sorted(unknown))}.")
        for key in TICKET_KEYS:
            if not isinstance(raw[key], str) or not raw[key].strip():
                raise SetupError(f"{label}: '{key}' must be a non-empty string.")
        try:
            expected = Category(raw["expected_category"])
        except ValueError:
            raise SetupError(
                f"{label}: expected_category '{raw['expected_category']}' is not one of: {allowed}."
            ) from None
        tickets.append(Ticket(raw["id"], raw["text"], expected))

    ids = [t.id for t in tickets]
    duplicates = sorted({i for i in ids if ids.count(i) > 1})
    if duplicates:
        raise SetupError(f"Duplicate ticket id(s): {', '.join(duplicates)}.")
    return tickets


# -------------------------------------------------------------------- running


def _describe_error(error: Exception) -> str:
    return " ".join(f"{type(error).__name__}: {error}".split())


def score(ticket: Ticket, level: str, client: RespondingClient, deployment: str) -> LevelResult:
    """One call, no retries. Refusals and per-call errors become results."""
    try:
        raw = client.respond(
            deployment,
            build_messages(ticket.text),
            mode=level,
            schema=TicketTriage if level == "schema" else None,
            temperature=TEMPERATURE,
        )
    except (openai.AuthenticationError, openai.PermissionDeniedError, ClientAuthenticationError) as error:
        raise SetupError(f"Authentication failed mid-run: {_describe_error(error)}") from error
    # pydantic.ValidationError: responses.parse could not load the reply (e.g. truncated).
    except (openai.OpenAIError, pydantic.ValidationError, RuntimeError) as error:
        return LevelResult(ticket.id, level, "error", reason=_describe_error(error))

    tokens = {"input_tokens": raw.input_tokens, "output_tokens": raw.output_tokens}
    if raw.refusal:
        return LevelResult(ticket.id, level, "refused", raw=raw.text, reason=raw.refusal, **tokens)

    result = validate_output(raw.text)
    if not result.valid:
        return LevelResult(ticket.id, level, "invalid", raw=raw.text, reason=result.reason, **tokens)
    category = result.triage.category
    return LevelResult(
        ticket.id,
        level,
        "valid",
        raw=raw.text,
        category=category,
        correct=category == ticket.expected_category,
        **tokens,
    )


def run_lab(tickets: list[Ticket], client: RespondingClient, deployment: str) -> list[LevelResult]:
    total = len(tickets) * len(LEVELS)
    results = []
    for ticket in tickets:
        for level in LEVELS:
            result = score(ticket, level, client, deployment)
            results.append(result)
            logger.info("[%d/%d] %s %s: %s", len(results), total, ticket.id, level, result.status)
    return results


def summarize(results: list[LevelResult], pricing: Pricing) -> list[LevelSummary]:
    """Per-level totals. Percentages use every ticket as the denominator,
    so invalid, refused and errored outputs count against a level."""
    summaries = []
    for level in LEVELS:
        rows = [r for r in results if r.level == level]
        input_tokens = sum(r.input_tokens for r in rows)
        output_tokens = sum(r.output_tokens for r in rows)
        summaries.append(
            LevelSummary(
                level=level,
                total=len(rows),
                valid=sum(r.status == "valid" for r in rows),
                correct=sum(r.correct for r in rows),
                refused=sum(r.status == "refused" for r in rows),
                errors=sum(r.status == "error" for r in rows),
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost=estimate_cost_usd(input_tokens, output_tokens, pricing),
            )
        )
    return summaries


# --------------------------------------------------------------------- report


def _fenced(text: str) -> str:
    """Code block that survives raw output containing its own ``` fences."""
    longest = max((len(m) for m in re.findall(r"`+", text)), default=0)
    fence = "`" * max(3, longest + 1)
    return f"{fence}\n{text}\n{fence}"


def _verdict(result: LevelResult, expected: Category) -> str:
    if result.status == "valid":
        if result.correct:
            return f"✅ valid shape · ✅ category correct ({result.category.value})"
        return (
            f"✅ valid shape · ❌ category wrong: got {result.category.value}, "
            f"expected {expected.value}"
        )
    if result.status == "invalid":
        return f"❌ invalid shape: {result.reason}"
    if result.status == "refused":
        return f"⚠️ refused: {result.reason}"
    return f"⚠️ error: `{result.reason}`"


def format_report(
    tickets: list[Ticket],
    results: list[LevelResult],
    summaries: list[LevelSummary],
    deployment: str,
    generated_at: datetime,
) -> str:
    lines = [
        "# Ticket Output Lab",
        "",
        f"Generated {generated_at:%Y-%m-%d %H:%M} · deployment `{deployment}` · "
        f"temperature {TEMPERATURE} · {len(tickets)} tickets × {len(LEVELS)} levels · no retries",
        "",
        "## Summary",
        "",
        "| Level | Valid shape | Correct category | Refusals | Errors "
        "| Input tokens | Output tokens | Est. cost (USD) |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for s in summaries:
        lines.append(
            f"| `{s.level}` | {s.pct_valid:.0f}% ({s.valid}/{s.total}) "
            f"| {s.pct_correct:.0f}% ({s.correct}/{s.total}) | {s.refused} | {s.errors} "
            f"| {s.input_tokens} | {s.output_tokens} | ${s.cost:.6f} |"
        )
    total_cost = sum(s.cost for s in summaries)
    lines += [
        "",
        f"**Total estimated cost: ${total_cost:.6f} USD**",
        "",
        "Percentages are out of all tickets: invalid, refused and errored outputs count as "
        "not valid and not correct.",
        "",
        "Levels:",
        "",
        *[f"- `{level}`: {LEVEL_DESCRIPTIONS[level]}" for level in LEVELS],
        "",
        "## Results by ticket",
        "",
    ]

    by_key = {(r.ticket_id, r.level): r for r in results}
    for ticket in tickets:
        lines += [
            f"### {ticket.id} · expected {ticket.expected_category.value}",
            "",
            f"> {ticket.text}",
            "",
        ]
        for level in LEVELS:
            result = by_key[(ticket.id, level)]
            lines += [f"**`{level}`**: {_verdict(result, ticket.expected_category)}", ""]
            if result.raw:
                lines += [_fenced(result.raw), ""]
            elif result.status != "error":
                lines += ["_(empty output)_", ""]
    return "\n".join(lines)


# ----------------------------------------------------------------------- main


def main(argv: Sequence[str] | None = None, client: RespondingClient | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compare three levels of output control.")
    parser.add_argument("--tickets", type=Path, default=DEFAULT_TICKETS, help="tickets YAML")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT, help="Markdown report path")
    args = parser.parse_args(argv)
    # WARNING for everything (keeps Azure/HTTP chatter out), INFO for our progress lines.
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    logger.setLevel(logging.INFO)
    # Show the SDK's own transport retries (rate limits, timeouts). They never
    # retry a bad *output*, but they explain slow runs.
    logging.getLogger("openai").setLevel(logging.INFO)

    try:
        config = load_config()
        deployment = config.nonreasoning_deployment
        pricing = pricing_for(load_pricing(), deployment)
        tickets = load_tickets(args.tickets)
        if client is None:
            client = create_model_client(config)
        results = run_lab(tickets, client, deployment)
    except SetupError as error:
        print(f"Setup error: {error}", file=sys.stderr)
        return 2

    summaries = summarize(results, pricing)
    args.out.write_text(format_report(tickets, results, summaries, deployment, datetime.now()))
    print(f"Wrote {args.out}")
    for s in summaries:
        print(
            f"  {s.level:<9} valid {s.pct_valid:3.0f}%  correct {s.pct_correct:3.0f}%  "
            f"refused {s.refused}  errors {s.errors}  ${s.cost:.6f}"
        )
    return 1 if any(s.errors for s in summaries) else 0


if __name__ == "__main__":
    raise SystemExit(main())
