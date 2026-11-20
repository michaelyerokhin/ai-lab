from dataclasses import dataclass
from enum import Enum
from typing import get_args, get_origin

from pydantic import BaseModel, ConfigDict, ValidationError

class Category(str, Enum):
    account = "Account"
    email = "Email"
    hardware = "Hardware"
    network = "Network"
    security = "Security"
    other = "Other"   # non-IT or unclear requests

class Priority(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"

class TicketTriage(BaseModel):
    # Unknown keys are a schema mismatch, matching what structured outputs enforce.
    model_config = ConfigDict(extra="forbid")

    title: str
    category: Category
    priority: Priority
    likely_cause: str
    steps: list[str]
    escalate: bool


# --------------------------------------------------------------------------
# Shared prompt and validator, used by triage.py and output_lab.py.
# The field list is generated from TicketTriage, so it never drifts from it.


def _describe_type(annotation) -> str:
    if isinstance(annotation, type) and issubclass(annotation, Enum):
        return "one of " + ", ".join(f'"{member.value}"' for member in annotation)
    if annotation is str:
        return "string"
    if annotation is bool:
        return "true or false"
    if get_origin(annotation) is list and get_args(annotation) == (str,):
        return "list of strings"
    return getattr(annotation, "__name__", str(annotation))


def describe_fields(model: type[BaseModel] = TicketTriage) -> str:
    return "\n".join(
        f"- {name}: {_describe_type(field.annotation)}"
        for name, field in model.model_fields.items()
    )


SYSTEM_PROMPT = f"""You are an IT help desk triage assistant.
Read the support ticket and reply with a JSON object with exactly these fields:
{describe_fields()}
Use "Other" for requests that are not IT problems or are too vague to classify.
Reply with the JSON object only."""


def build_messages(ticket_text: str) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": ticket_text},
    ]


@dataclass(frozen=True)
class ValidationResult:
    triage: TicketTriage | None
    reason: str | None  # why it failed; None when valid

    @property
    def valid(self) -> bool:
        return self.triage is not None


def _format_error(error: dict) -> str:
    location = ".".join(str(part) for part in error["loc"])
    message = error["msg"]
    if error["type"] in ("missing", "json_invalid"):
        return f"{message}: {location}" if location else message
    detail = f"{location}: {message}" if location else message
    if error["type"] == "extra_forbidden":
        return f"unexpected field: {location}"
    return f"{detail} (got {error['input']!r})"


def validate_output(text: str) -> ValidationResult:
    """Load raw model output into TicketTriage exactly as given.

    Strict on purpose: JSON wrapped in prose or code fences, wrong types
    (e.g. escalate: "yes") and unknown keys all count as a mismatch.
    """
    try:
        triage = TicketTriage.model_validate_json(text, strict=True)
    except ValidationError as error:
        reason = "; ".join(_format_error(e) for e in error.errors(include_url=False))
        return ValidationResult(None, reason)
    return ValidationResult(triage, None)
