"""Shared connection code for Azure Foundry model deployments.

Both hello_model.py and prompt_lab.py use this module, so authentication,
deployment selection, the temperature fallback and cost estimates live in
one place.
"""

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import openai
import yaml
from azure.core.exceptions import ClientAuthenticationError
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from dotenv import load_dotenv

WEEK1_DIR = Path(__file__).resolve().parent
ENV_FILE = WEEK1_DIR / ".env"
PRICING_FILE = WEEK1_DIR / "experiments.yaml"
TOKENS_PER_MILLION = 1_000_000
# Entra ID scope for Azure AI Foundry. Foundry exposes deployed models through an
# OpenAI-compatible /openai/v1 endpoint, so the standard OpenAI SDK works as-is
# and we authenticate with Entra ID tokens instead of an API key.
FOUNDRY_TOKEN_SCOPE = "https://ai.azure.com/.default"

logger = logging.getLogger(__name__)


class SetupError(Exception):
    """A problem that stops the whole run: config, YAML, or authentication."""


@dataclass(frozen=True)
class ModelConfig:
    endpoint: str
    default_deployment: str
    nonreasoning_deployment: str

    @property
    def deployments(self) -> tuple[str, ...]:
        return (self.default_deployment, self.nonreasoning_deployment)

    def resolve_deployment(self, requested: str | None) -> str:
        """Return the deployment to use: the requested one, or the default."""
        if requested is None:
            return self.default_deployment
        if requested not in self.deployments:
            allowed = ", ".join(self.deployments)
            raise SetupError(
                f"Unknown deployment '{requested}'. Configured deployments: {allowed}."
            )
        return requested


@dataclass(frozen=True)
class Pricing:
    """USD per million tokens."""

    input_per_million: float
    output_per_million: float


@dataclass(frozen=True)
class Completion:
    text: str
    input_tokens: int
    output_tokens: int
    # None when no temperature was requested; False when the model rejected it.
    temperature_applied: bool | None


def load_config() -> ModelConfig:
    """Load the endpoint and deployment names from week1/.env or the environment."""
    load_dotenv(ENV_FILE)
    names = ("AZURE_ENDPOINT", "DEPLOYMENT_NAME", "NONREASONING_DEPLOYMENT")
    values = {name: os.getenv(name) for name in names}
    missing = [name for name, value in values.items() if not value]
    if missing:
        raise SetupError(
            f"Missing required environment variable(s): {', '.join(missing)}. "
            f"Set them in {ENV_FILE} or the environment."
        )
    return ModelConfig(
        endpoint=values["AZURE_ENDPOINT"],
        default_deployment=values["DEPLOYMENT_NAME"],
        nonreasoning_deployment=values["NONREASONING_DEPLOYMENT"],
    )


def parse_pricing(raw: Any) -> dict[str, Pricing]:
    """Validate a `pricing:` mapping of deployment -> {input, output}."""
    if not isinstance(raw, dict) or not raw:
        raise SetupError("'pricing' must be a mapping of deployment name to {input, output}.")
    pricing = {}
    for deployment, rates in raw.items():
        if not isinstance(rates, dict) or set(rates) != {"input", "output"}:
            raise SetupError(
                f"pricing.{deployment} must have exactly 'input' and 'output' "
                "(USD per million tokens)."
            )
        for key in ("input", "output"):
            value = rates[key]
            if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
                raise SetupError(f"pricing.{deployment}.{key} must be a non-negative number.")
        pricing[str(deployment)] = Pricing(float(rates["input"]), float(rates["output"]))
    return pricing


def load_pricing(path: Path = PRICING_FILE) -> dict[str, Pricing]:
    """Read only the `pricing:` block from a YAML file."""
    try:
        data = yaml.safe_load(Path(path).read_text())
    except (OSError, yaml.YAMLError) as error:
        raise SetupError(f"Could not read pricing from {path}: {error}") from error
    if not isinstance(data, dict) or "pricing" not in data:
        raise SetupError(f"{path} has no top-level 'pricing' block.")
    return parse_pricing(data["pricing"])


def pricing_for(pricing: dict[str, Pricing], deployment: str) -> Pricing:
    if deployment not in pricing:
        raise SetupError(
            f"No pricing for deployment '{deployment}'. Add it under 'pricing:' "
            f"in {PRICING_FILE.name}."
        )
    return pricing[deployment]


def estimate_cost_usd(input_tokens: int, output_tokens: int, pricing: Pricing) -> float:
    return (
        input_tokens * pricing.input_per_million
        + output_tokens * pricing.output_per_million
    ) / TOKENS_PER_MILLION


def is_temperature_rejection(error: openai.BadRequestError) -> bool:
    """True when a 400 error is about the temperature parameter."""
    return getattr(error, "param", None) == "temperature" or "temperature" in str(error).lower()


class ModelClient:
    """Thin wrapper over the OpenAI SDK's Responses API.

    Tests replace this with a fake, or pass a fake SDK object to it, so nothing
    here needs Azure to be exercised.
    """

    def __init__(self, sdk_client: Any):
        self._sdk = sdk_client

    def complete(
        self,
        deployment: str,
        messages: list[dict[str, str]],
        temperature: float | None = None,
    ) -> Completion:
        request = {"model": deployment, "input": messages}
        applied: bool | None = None
        if temperature is None:
            response = self._sdk.responses.create(**request)
        else:
            try:
                response = self._sdk.responses.create(**request, temperature=temperature)
                applied = True
            except openai.BadRequestError as error:
                if not is_temperature_rejection(error):
                    raise
                logger.warning(
                    "Deployment '%s' rejected temperature=%s; retrying without it.",
                    deployment,
                    temperature,
                )
                response = self._sdk.responses.create(**request)
                applied = False

        if response.usage is None:
            raise RuntimeError("The model response did not include token usage.")
        return Completion(
            text=response.output_text,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            temperature_applied=applied,
        )


def create_model_client(config: ModelConfig) -> ModelClient:
    """Authenticate with Entra ID and return a ready-to-use client.

    A token is fetched up front so a sign-in problem stops the run before any
    experiment starts.
    """
    token_provider = get_bearer_token_provider(DefaultAzureCredential(), FOUNDRY_TOKEN_SCOPE)
    try:
        token_provider()
    except ClientAuthenticationError as error:
        first_line = str(error).strip().splitlines()[0] if str(error).strip() else type(error).__name__
        raise SetupError(
            f"Azure authentication failed ({first_line}). Sign in with 'az login' and retry."
        ) from error
    return ModelClient(openai.OpenAI(base_url=config.endpoint, api_key=token_provider))
