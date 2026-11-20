"""Triage one help desk ticket into a TicketTriage result using structured outputs.

Use it from the command line:
    python week1/triage.py "Printer on floor 2 is jammed"

or from code:
    from triage import triage_ticket
    result = triage_ticket(text, client, deployment)
"""

import argparse
import sys
from typing import Protocol, Sequence

import openai
import pydantic

from client import RawResponse, SetupError, create_model_client, load_config
from schemas import TicketTriage, build_messages, validate_output

TEMPERATURE = 0

'''
    * RespondingClient(Protocol) is inheritance:
        RespondingClient inherits from Protocol, which is a special base class in Python's typing module. 
        This means that RespondingClient is a protocol, which defines a set of methods and attributes that a class must implement to be considered a subtype of the protocol. 
        In this case, any class that implements the respond method with the specified signature can be considered a subtype of RespondingClient, even if it doesn't explicitly inherit from it. 
        This allows for more flexible and dynamic type checking, as classes can be considered compatible with the protocol based on their behavior rather than their explicit inheritance hierarchy.
    * respond(self, deployment: str, messages: list[dict[str, str]], **kwargs) -> RawResponse: ... is a method signature:
        This line defines a method signature for the respond method in the RespondingClient protocol. 
        It specifies that any class implementing this protocol must have a respond method that takes three parameters: 
        - deployment: a string representing the deployment name or identifier
        - messages: a list of dictionaries, where each dictionary has string keys and string values, representing the messages to be sent to the model
        - **kwargs: a variable-length keyword argument list, allowing for additional optional parameters to be passed to the method
'''

class RespondingClient(Protocol):
    def respond(self, deployment: str, messages: list[dict[str, str]], **kwargs) -> RawResponse: ...

'''
    * TriageRefused(Exception) is inheritance: 
        TriageRefused inherits from Exception, so it is a 
        subclass of Exception. This means that 
        TriageRefused is a specialized type of Exception 
        that can be used to represent a specific kind 
        of error or exceptional condition in the code. 
'''
class TriageRefused(Exception):
    """The model declined to triage the ticket."""


class TriageInvalid(Exception):
    """The model's reply did not match TicketTriage."""


def triage_ticket(text: str, client: RespondingClient, deployment: str) -> TicketTriage:
    """Classify one ticket. Raises TriageRefused or TriageInvalid instead of guessing."""
    raw = client.respond(
        deployment,
        build_messages(text),
        mode="schema",
        schema=TicketTriage,
        temperature=TEMPERATURE,
    )
    if raw.refusal:
        raise TriageRefused(raw.refusal)
    result = validate_output(raw.text)
    if not result.valid:
        raise TriageInvalid(result.reason)
    return result.triage


def main(argv: Sequence[str] | None = None, client: RespondingClient | None = None) -> int:
    parser = argparse.ArgumentParser(description="Triage one help desk ticket.")
    parser.add_argument("ticket", help="Ticket text, in quotes")
    args = parser.parse_args(argv)

    try:
        config = load_config()
        if client is None:
            client = create_model_client(config)
    except SetupError as error:
        print(f"Setup error: {error}", file=sys.stderr)
        return 2

    try:
        result = triage_ticket(args.ticket, client, config.nonreasoning_deployment)
    except TriageRefused as refusal:
        print(f"Refused: {refusal}", file=sys.stderr)
        return 1
    except TriageInvalid as invalid:
        print(f"Invalid model output: {invalid}", file=sys.stderr)
        return 1
    # pydantic.ValidationError: responses.parse could not load the reply (e.g. truncated).
    except (openai.OpenAIError, pydantic.ValidationError, RuntimeError) as error:
        print(f"API error: {type(error).__name__}: {error}", file=sys.stderr)
        return 1

    print(result.model_dump_json(indent=2))
    return 0


"""
    main() is empty here because it is a placeholder 
    for the main function that will be executed 
    when the script is run directly. It will also listen
    to what is being passed in on the CLI.

"""
if __name__ == "__main__":
    raise SystemExit(main())
