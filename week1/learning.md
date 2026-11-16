# Week 1 — What I Learned

## 1. Prompt engineering as part of my workflow

I started using structured prompts (specs) to drive AI-assisted coding instead of ad-hoc requests. My first spec was for this week's project:

```text
Read this spec and propose a plan before coding.

GOAL: A Python script week1/hello_model.py that sends a question
to my Azure Foundry model and prints the answer.
INPUTS: A question passed on the command line.
OUTPUTS: The answer, then a line showing input tokens,
output tokens, and estimated cost.
CONSTRAINTS: Use the official openai Python package with
Entra ID auth (DefaultAzureCredential), no API keys.
Endpoint and deployment name come from .env:
  AZURE_ENDPOINT=<paste>
  DEPLOYMENT_NAME=<paste>
Match the code sample in my deployment's Code tab, pasted below:
<paste the sample>
NOT IN SCOPE: chat history, UI, streaming.
DONE WHEN: `python week1/hello_model.py "What is an MSP?"`
prints an answer and token counts, and a pytest test checks
that a missing .env variable gives a clear error message.
```

**Key idea: this is a *declarative* approach.** I describe *what* I want, not *how* to build it:

- **I define** the goal, inputs, outputs, constraints, what's out of scope, and a concrete "done when" check. These are the guardrails and specifications for the result.
- **The AI defines** the line-by-line implementation within those guardrails.
- Asking for a **plan before coding** lets me review the approach before any code is written.

## 2. Microsoft Foundry

Microsoft Foundry is a Microsoft service that provides access to LLMs and other AI models. I can deploy a model there, then connect to it and send it prompts from my own code (in this project, via the `openai` Python package using Entra ID auth instead of API keys).

## 3. Prompt experiments

I ran prompt experiments with `week1/prompt_lab.py` (settings in `experiments.yaml`, results in `results.md`) and compared the answers, token counts and costs.

- **System messages** control tone, length and format, but vague words like "terse" get ignored. Use specific limits.
- **Few-shot examples** enforce format. They improve accuracy only where the model would otherwise struggle.
- **Temperature** works on non-reasoning models. Its effect is small on common questions and larger on open-ended ones.
- **Reasoning models** bill hidden thinking tokens. Use cheaper non-reasoning models for simple tasks.
