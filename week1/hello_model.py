"""Send one question to an Azure Foundry model and report token usage."""

import argparse
from importlib import import_module
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TOKENS_PER_MILLION = 1_000_000
INPUT_USD_PER_MILLION_TOKENS = 0.25
OUTPUT_USD_PER_MILLION_TOKENS = 2.00


@dataclass(frozen=True)
class ModelConfig:
    endpoint: str
    deployment_name: str


def load_config() -> ModelConfig:
    """Load endpoint and deployment settings from the project .env or environment."""
    load_dotenv(PROJECT_ROOT / "week1" / ".env")
    endpoint = os.getenv("AZURE_ENDPOINT")
    deployment_name = os.getenv("DEPLOYMENT_NAME")
    missing = [
        name
        for name, value in (
            ("AZURE_ENDPOINT", endpoint),
            ("DEPLOYMENT_NAME", deployment_name),
        )
        if not value
    ]
    if not endpoint or not deployment_name:
        names = ", ".join(missing)
        raise ValueError(
            f"Missing required environment variable(s): {names}. "
            "Set them in the project .env file or environment."
        )

    return ModelConfig(
        endpoint=endpoint,
        deployment_name=deployment_name,
    )


def estimate_cost_usd(input_tokens: int, output_tokens: int) -> float:
    """Estimate cost using published GPT-5 mini USD per-million-token rates."""
    input_cost = input_tokens * INPUT_USD_PER_MILLION_TOKENS / TOKENS_PER_MILLION
    output_cost = output_tokens * OUTPUT_USD_PER_MILLION_TOKENS / TOKENS_PER_MILLION
    return input_cost + output_cost


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ask the configured Azure Foundry model.")
    parser.add_argument("question", help="Question to send to the model")
    args = parser.parse_args(argv)

    try:
        config = load_config()
    except ValueError as error:
        print(f"Configuration error: {error}", file=sys.stderr)
        return 2

    try:
        OpenAI = import_module("openai").OpenAI
    except ModuleNotFoundError:
        print(
            "Dependency error: install the OpenAI SDK with 'python -m pip install openai'.",
            file=sys.stderr,
        )
        return 2

    # Foundry accepts Entra ID bearer tokens for this OpenAI-compatible endpoint.
    token_provider = get_bearer_token_provider(
        DefaultAzureCredential(),
        "https://ai.azure.com/.default",
    )
    client = OpenAI(base_url=config.endpoint, api_key=token_provider)
    response = client.responses.create(
        model=config.deployment_name,
        input=args.question,
    )

    if response.usage is None:
        raise RuntimeError("The model response did not include token usage.")

    input_tokens = response.usage.input_tokens
    output_tokens = response.usage.output_tokens
    estimated_cost = estimate_cost_usd(input_tokens, output_tokens)

    print(response.output_text)
    print(
        f"Input tokens: {input_tokens} | Output tokens: {output_tokens} | "
        f"Estimated cost: ${estimated_cost:.6f} USD"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
