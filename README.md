# Internal HR Benefits Agent

A sample AI agent built with [Microsoft Agent Framework](https://learn.microsoft.com/agent-framework/) that helps employees with HR benefits questions. This project is designed as an `azd` starter template for deploying hosted AI agents to [Microsoft Foundry](https://learn.microsoft.com/azure/foundry/).

## What it does

The agent uses company HR documents (via Azure AI Search) and tool-calling to:

- Answer questions about employee benefits (health insurance, dental, vision, 401k, etc.)
- Look up enrollment deadlines and dates
- Search the web for current information when the knowledge base doesn't have the answer
- Run code via Code Interpreter for data analysis tasks

## Architecture

The agent supports two modes for knowledge base integration, controlled by the `FOUNDRY_IQ_CONTEXT_MODE` environment variable:

- **`context_provider`** — Uses `AzureAISearchContextProvider` to inject KB results into context automatically before each turn
- **`kb_mcp_endpoint`** (default) — Uses `MCPStreamableHTTPTool` to connect to the KB's MCP endpoint, letting the model decide when to search

Both modes also include Foundry built-in tools (web search, code interpreter) when running in the hosted environment.

## Prerequisites

- [Python 3.12+](https://www.python.org/downloads/)
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- [Azure Developer CLI (azd) 1.23.7+](https://learn.microsoft.com/azure/developer/azure-developer-cli/install-azd)
- An [Azure subscription](https://azure.microsoft.com/free/)

## Quick start

### Deploy to Azure

```bash
azd auth login
azd up
```

> **Region:** The template restricts deployment to regions that support all features (Responses API, evaluations, red teaming): `eastus2`, `francecentral`, `northcentralus`, `swedencentral`.

### Set up the knowledge base

After provisioning, create the search indexes and knowledge base:

```bash
./write_dot_env.sh  # or .\write_dot_env.ps1 on Windows
uv run python infra/create-search-indexes.py \
    --endpoint "$AZURE_AI_SEARCH_SERVICE_ENDPOINT" \
    --openai-endpoint "$AZURE_OPENAI_ENDPOINT" \
    --openai-model-deployment "$AZURE_AI_MODEL_DEPLOYMENT_NAME"
```

This creates:
- `hrdocs` and `healthdocs` search indexes with sample data
- A single knowledge base (`zava-company-kb`) with both indexes as knowledge sources

### Run locally

1. Sync your `.env` from the azd environment:

    ```bash
    ./write_dot_env.sh
    ```

2. Start the local hosted-agent server:

    ```bash
    azd ai agent run
    ```

3. Invoke the agent from another terminal:

    ```bash
    azd ai agent invoke --local "What benefits are there, and when do I need to enroll by?"
    ```

### Deploy the agent

```bash
azd deploy
```

## Evaluation scripts

Scripts for quality evaluation, red teaming, and scheduled runs are in `scripts/`:

| Script | Description |
|--------|-------------|
| `scripts/quality_eval.py` | Run quality evaluation (task adherence, groundedness, relevance) |
| `scripts/red_team_scan.py` | Run a one-time red team scan with attack strategies |
| `scripts/scheduled_eval.py` | Set up daily quality evaluation schedule |
| `scripts/scheduled_red_team.py` | Set up daily red team schedule |

```bash
uv run scripts/quality_eval.py
uv run scripts/red_team_scan.py
```

> **Note:** Red teaming requires a supported region (East US 2, Sweden Central, etc.). See [evaluation region support](https://learn.microsoft.com/en-us/azure/foundry/concepts/evaluation-regions-limits-virtual-network).

## Debug with `azd`

After deploying, use these commands to inspect and troubleshoot your hosted agent:

```bash
# View container status, health, and error details
azd ai agent show

# Fetch recent logs
azd ai agent monitor

# Stream logs in real time
azd ai agent monitor -f
```

## Observability

The agent exports OpenTelemetry traces to Application Insights when `APPLICATIONINSIGHTS_CONNECTION_STRING` is set (handled automatically by the hosted agent server).

To enable sensitive data in traces (tool call arguments, prompts, responses), set `enable_sensitive_data=True` in the `enable_instrumentation()` call in `main.py`. This is useful for debugging but should be disabled in production.

To query traces in Application Insights:

```kql
dependencies
| where timestamp > ago(1h)
| where customDimensions has "gen_ai.operation.name"
| extend opName = tostring(customDimensions["gen_ai.operation.name"])
| extend toolName = tostring(customDimensions["gen_ai.tool.name"])
| extend toolArgs = tostring(customDimensions["gen_ai.tool.call.arguments"])
| project timestamp, name, opName, toolName, toolArgs
| order by timestamp desc
```

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `FOUNDRY_PROJECT_ENDPOINT` | Yes | Foundry project endpoint |
| `AZURE_AI_MODEL_DEPLOYMENT_NAME` | Yes | Model deployment name (e.g., `gpt-5.2`) |
| `AZURE_AI_SEARCH_SERVICE_ENDPOINT` | Yes | Azure AI Search endpoint |
| `AZURE_AI_SEARCH_KNOWLEDGE_BASE_NAME` | Yes | Knowledge base name (default: `zava-company-kb`) |
| `FOUNDRY_IQ_CONTEXT_MODE` | No | `context_provider` or `kb_mcp_endpoint` (default) |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | No | App Insights connection string for tracing |