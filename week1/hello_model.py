"""Send one question to an Azure Foundry model and report token usage."""

import argparse
import sys
from typing import Sequence

from client import (
    SetupError,
    create_model_client,
    estimate_cost_usd,
    load_config,
    load_pricing,
    pricing_for,
)

""" Ask the configured Azure Foundry model.

    - argv (argument vector): optional list of command-line arguments
      * if argv is none, it is used instead of sys.argv[1:] (will read the CLI)
      * if argv is provided, is ignores the CLI and uses the provided list of arguments instead
"""

def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ask the configured Azure Foundry model.")
    parser.add_argument("question", help="Question to send to the model")
    args = parser.parse_args(argv)

    try:
        config = load_config()
        deployment = config.default_deployment
        pricing = pricing_for(load_pricing(), deployment)
        client = create_model_client(config)
    except SetupError as error:
        print(f"Setup error: {error}", file=sys.stderr)
        return 2

    completion = client.complete(deployment, [{"role": "user", "content": args.question}])
    cost = estimate_cost_usd(completion.input_tokens, completion.output_tokens, pricing)

    print(completion.text)
    print(
        f"Input tokens: {completion.input_tokens} | Output tokens: {completion.output_tokens} | "
        f"Estimated cost: ${cost:.6f} USD"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
