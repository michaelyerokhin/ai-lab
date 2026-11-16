# Week 1: Hello Foundry Model

Ask the configured Azure Foundry model one question:

```bash
cp .env.example .env
python week1/hello_model.py "What is an MSP?"
```

Set `AZURE_ENDPOINT` and `DEPLOYMENT_NAME` in `.env`. Sign in with an Entra ID
credential supported by `DefaultAzureCredential` before running the script.
Install dependencies with `python -m pip install -r requirements.txt`.

The cost line is an estimate using USD rates of $0.25 per million input tokens
and $2.00 per million output tokens for GPT-5 mini. Azure rates depend on the
deployment type, region, and agreement; verify the applicable rate on the
[Azure OpenAI pricing page](https://azure.microsoft.com/en-us/pricing/details/azure-openai/).

Run the test with `python -m pytest week1/test_hello_model.py`.
