# Week 1: Hello Foundry Model + Prompt Lab

## Layout

```
week1/
├── *.py        # the code: client, hello_model, prompt_lab, triage, output_lab, schemas
├── config/     # YAML inputs: experiments.yaml, tickets_list.yml
├── docs/       # notes (learning.md) and generated reports (results.md, ticket_output_results.md)
└── tests/      # pytest tests; conftest.py lets them import the modules above
```

## Setup

```bash
python -m pip install -r requirements.txt
cp week1/.env.example week1/.env   # then fill in your endpoint
az login                           # DefaultAzureCredential picks this up
```

`week1/.env` needs three values:

| Variable | Meaning |
|---|---|
| `AZURE_ENDPOINT` | Foundry OpenAI-compatible endpoint, ending in `/openai/v1` |
| `DEPLOYMENT_NAME` | Default deployment (a reasoning model, e.g. gpt-5-mini) |
| `NONREASONING_DEPLOYMENT` | Second deployment that accepts `temperature` (e.g. gpt-4.1-mini) |

Shared connection code (auth, deployment selection, temperature fallback, cost
estimates) lives in `client.py` and is used by both scripts.

## hello_model.py: ask one question

```bash
python week1/hello_model.py "What is an MSP?"
```

Prints the answer, token counts and an estimated cost for the default deployment.

## prompt_lab.py: run prompt experiments

```bash
python week1/prompt_lab.py                      # reads week1/config/experiments.yaml
python week1/prompt_lab.py --config other.yaml --out other.md
```

Writes `week1/docs/results.md`: for each experiment the deployment and settings
used, every answer with its token counts, and a summary table ending in the
total estimated cost.

### experiments.yaml

```yaml
pricing:                 # USD per 1M tokens, keyed by deployment name
  gpt-5-mini:   {input: 0.25, output: 2.00}
  gpt-4.1-mini: {input: 0.40, output: 1.60}

experiments:
  - name: few-shot-three         # required, unique
    user: "Classify: ..."        # required
    runs: 1                      # required, >= 1
    system: "You classify tickets."   # optional
    examples:                    # optional few-shot pairs
      - user: "Laptop won't power on"
        assistant: "Hardware"
    temperature: 0.7             # optional
    deployment: gpt-4.1-mini     # optional; must match DEPLOYMENT_NAME or
                                 # NONREASONING_DEPLOYMENT (default: DEPLOYMENT_NAME)
```

### Error handling

- **Setup errors stop the run** before anything is written (exit code 2): bad
  YAML, an unknown field, a missing `.env` value, an unknown deployment, a
  deployment with no pricing, or an Azure sign-in failure.
- **Errors in a single run are recorded** in `results.md` and the lab continues
  (exit code 1 if any run failed, otherwise 0).
- **Temperature fallback:** reasoning models such as gpt-5-mini reject
  `temperature`. The script logs a warning, retries without it, and the report
  shows e.g. `0.2 (not applied)`.

### Pricing

Costs are estimates. Azure rates depend on deployment type, region and
agreement; check the
[Azure OpenAI pricing page](https://azure.microsoft.com/en-us/pricing/details/azure-openai/)
and update the `pricing:` block. `hello_model.py` reads the same block.

## triage.py: triage one ticket with structured outputs

```bash
python week1/triage.py "Printer on floor 2 is jammed"
```

Prints a `TicketTriage` result as JSON (title, category, priority,
likely_cause, steps, escalate). It always uses `NONREASONING_DEPLOYMENT` at
temperature 0, with structured outputs via `client.responses.parse(text_format=TicketTriage)`
(openai SDK 3.x). Exit code 1 if the model refuses or the call fails, 2 for
setup errors. Reuse it from code with `triage.triage_ticket(text, client, deployment)`.

The schema (`Category`, `Priority`, `TicketTriage`), the shared system prompt
and the validator live in `schemas.py`.

## output_lab.py: compare three levels of output control

```bash
python week1/output_lab.py        # reads week1/config/tickets_list.yml
```

Sends every ticket through three levels, with the same system message and no retries:

| Level | Output control |
|---|---|
| `prompt` | the system message asks for JSON and lists the fields |
| `json_mode` | the same + JSON mode (`text.format = json_object`) |
| `schema` | structured outputs with the `TicketTriage` model |

Every output is scored the same way: it is loaded into `TicketTriage` with
Pydantic, strictly. JSON wrapped in prose or code fences, wrong types and
extra fields all count as invalid. Refusals are recorded and counted
separately. Writes `week1/docs/ticket_output_results.md`: each raw output with its
verdict, plus a per-level summary of % valid shape, % correct category,
refusals, errors, tokens and cost. Percentages are out of all tickets.

Tickets file format:

```yaml
tickets:
  - id: T01
    text: "Laptop won't turn on."
    expected_category: Hardware   # a Category value, incl. Other
```

## Tests

```bash
python -m pytest week1
```

The tests use fake model clients and never call Azure.
