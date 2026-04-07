# Seattle Hotel Agent

A sample AI agent built with [Microsoft Agent Framework](https://learn.microsoft.com/agent-framework/) that helps users find hotels in Seattle. This project is designed as an `azd` starter template for deploying hosted AI agents to [Microsoft Foundry](https://learn.microsoft.com/azure/foundry/).

> **Blog post:** [Azure Developer CLI (azd): Debug hosted AI agents from your terminal](https://devblogs.microsoft.com/azure-sdk/azd-ai-agent-logs-status/)

## What it does

The agent uses a simulated hotel database and a tool-calling pattern to:

- Accept natural-language requests about Seattle hotels
- Ask clarifying questions about dates and budget
- Call the `get_available_hotels` tool to find matching options
- Present results in a conversational format

## Prerequisites

- [Python 3.12+](https://www.python.org/downloads/)
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- [Azure Developer CLI (azd) 1.23.7+](https://learn.microsoft.com/azure/developer/azure-developer-cli/install-azd)
- An [Azure subscription](https://azure.microsoft.com/free/)
- A [Microsoft Foundry](https://ai.azure.com/) project with a deployed model (e.g., `gpt-5.2`)

## Quick start

### Deploy to Azure

```bash
azd init -t puicchan/seattle-hotel-agent
azd ai agent init
azd up
```

During `azd ai agent init`, you'll be prompted to choose a model. You can:

- **Deploy a new model** — select `gpt-5.2` (or another supported model)
- **Connect to an existing model** — make sure the deployment name matches `MS_FOUNDRY_MODEL_DEPLOYMENT` in your `.env`
- **Skip model setup** — configure it manually later

> **Note:** If you use a model deployment name other than `gpt-5.2`, update `MS_FOUNDRY_MODEL_DEPLOYMENT` in your `.env` to match.

### Run locally

1. Copy `.env.sample` to `.env`, then set both required variables:
    - `MS_FOUNDRY_PROJECT_ENDPOINT`
    - `MS_FOUNDRY_MODEL_DEPLOYMENT`

    ```bash
    cp .env.sample .env
    ```

2. Start the local hosted-agent server:

    ```bash
    azd ai agent run
    ```

    This starts the local server on `http://localhost:8088`.

3. Invoke the agent from another terminal:

    ```bash
    azd ai agent invoke --local "hi agent"
    ```

4. Or test it with any HTTP client:

    ```http
    POST http://localhost:8088/responses
    Content-Type: application/json

    {"input": "Find me a hotel near Pike Place Market for this weekend"}
    ```

## Debug with `azd`

After deploying, use these commands to inspect and troubleshoot your hosted agent:

```bash
# View container status, health, and error details
azd ai agent show

# Fetch recent logs
azd ai agent monitor

# Stream logs in real time
azd ai agent monitor -f

# View system-level logs
azd ai agent monitor --type system
```

See the [blog post](https://devblogs.microsoft.com/azure-sdk/azd-ai-agent-logs-status/) for more details.