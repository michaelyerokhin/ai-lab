import json

import pytest

from schemas import (
    SYSTEM_PROMPT,
    Category,
    Priority,
    TicketTriage,
    build_messages,
    validate_output,
)

GOOD = {
    "title": "Printer jam on floor 2",
    "category": "Hardware",
    "priority": "medium",
    "likely_cause": "Paper jam",
    "steps": ["Open tray 2", "Remove jammed paper"],
    "escalate": False,
}


def as_json(**changes):
    data = {**GOOD, **changes}
    return json.dumps({k: v for k, v in data.items() if v is not ...})


def test_good_json_is_valid():
    result = validate_output(as_json())

    assert result.valid and result.reason is None
    assert result.triage == TicketTriage(
        title="Printer jam on floor 2",
        category=Category.hardware,
        priority=Priority.medium,
        likely_cause="Paper jam",
        steps=["Open tray 2", "Remove jammed paper"],
        escalate=False,
    )


def test_surrounding_whitespace_is_fine():
    assert validate_output("\n  " + as_json() + "\n").valid


def test_missing_field_is_invalid_and_named():
    result = validate_output(as_json(likely_cause=...))

    assert not result.valid
    assert result.reason == "Field required: likely_cause"


def test_invalid_category_is_invalid_and_shows_value():
    result = validate_output(as_json(category="Printer"))

    assert not result.valid
    assert result.reason.startswith("category: Input should be 'Account'")
    assert "(got 'Printer')" in result.reason


def test_wrong_case_priority_is_invalid():
    result = validate_output(as_json(priority="High"))
    assert not result.valid and "priority" in result.reason


@pytest.mark.parametrize(
    "wrapped",
    [
        "Here is the triage:\n" + json.dumps(GOOD),
        json.dumps(GOOD) + "\nLet me know if you need anything else.",
        "```json\n" + json.dumps(GOOD) + "\n```",
    ],
    ids=["prose-before", "prose-after", "code-fence"],
)
def test_json_wrapped_in_extra_text_is_invalid(wrapped):
    result = validate_output(wrapped)

    assert not result.valid
    assert result.reason.startswith("Invalid JSON")


@pytest.mark.parametrize(
    "changes, field",
    [
        ({"escalate": "yes"}, "escalate"),
        ({"steps": "Restart it"}, "steps"),
        ({"title": 42}, "title"),
    ],
)
def test_wrong_types_are_invalid(changes, field):
    result = validate_output(as_json(**changes))
    assert not result.valid and result.reason.startswith(field)


def test_extra_field_is_invalid():
    result = validate_output(as_json(confidence=0.9))
    assert result.reason == "unexpected field: confidence"


def test_empty_output_is_invalid():
    assert not validate_output("").valid


def test_system_prompt_lists_every_field_and_allowed_value():
    for field in TicketTriage.model_fields:
        assert f"- {field}:" in SYSTEM_PROMPT
    for value in [c.value for c in Category] + [p.value for p in Priority]:
        assert f'"{value}"' in SYSTEM_PROMPT
    assert "JSON" in SYSTEM_PROMPT  # JSON mode requires the word in the prompt


def test_build_messages():
    assert build_messages("Printer jammed") == [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "Printer jammed"},
    ]
