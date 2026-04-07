# Seattle Hotel Agent

A sample AI agent built with [Microsoft Agent Framework](https://learn.microsoft.com/azure/ai-services/agents/) that helps users find hotels in Seattle. This project is designed as an `azd` starter template for deploying hosted AI agents to [Azure AI Foundry](https://learn.microsoft.com/azure/ai-studio/).

> **Blog post:** [Azure Developer CLI (azd): Debug hosted AI agents from your terminal](https://devblogs.microsoft.com/azure-sdk/azd-ai-agent-logs-status/)

## What it does

The agent uses a simulated hotel database and a tool-calling pattern to:

- Accept natural-language requests about Seattle hotels
- Ask clarifying questions about dates and budget
- Call the `get_available_hotels` tool to find matching options
- Present results in a conversational format

## Prerequisites

- [Python 3.12+](https://www.python.org/downloads/)
- [Azure Developer CLI (azd) 1.23.7+](https://learn.microsoft.com/azure/developer/azure-developer-cli/install-azd)
- An [Azure subscription](https://azure.microsoft.com/free/)
- An [Azure AI Foundry](https://ai.azure.com/) project with a deployed model (e.g., `gpt-4.1-mini`)

## Quick start

### Deploy to Azure

```bash
azd init -t puicchan/seattle-hotel-agent
azd ai agent init
azd up
```

During `azd ai agent init`, you'll be prompted to choose a model. You can:

- **Deploy a new model** — select `gpt-4.1-mini` (or another supported model)
- **Connect to an existing model** — make sure the deployment name matches `MODEL_DEPLOYMENT_NAME` in your `.env` (defaults to `gpt-4.1-mini`)
- **Skip model setup** — configure it manually later

> **Note:** If you use a model deployment name other than `gpt-4.1-mini`, update `MODEL_DEPLOYMENT_NAME` in your `.env` to match.

### Run locally

1. Copy `.env.sample` to `.env` and fill in your values:

    ```bash
    cp .env.sample .env
    ```

2. Install dependencies:

    ```bash
    python -m venv .venv
    source .venv/bin/activate   # On Windows: .venv\Scripts\activate
    pip install -r requirements.txt
    ```

3. Run the agent:

    ```bash
    python main.py
    ```

    The agent server starts on `http://localhost:8088`.

## Debug with `azd`

After deploying, use these commands to inspect and troubleshoot your hosted agent:

```bash
# View container status, health, and error details
azd ai agent show --name seattle-hotel-agent --version 1

# Fetch recent logs
azd ai agent monitor --name seattle-hotel-agent --version 1

# Stream logs in real time
azd ai agent monitor --name seattle-hotel-agent --version 1 -f

# View system-level logs
azd ai agent monitor --name seattle-hotel-agent --version 1 --type system
```

See the [blog post](https://devblogs.microsoft.com/azure-sdk/azd-ai-agent-logs-status/) for more details.

## Project structure

| File | Description |
|---|---|
| `main.py` | Agent definition, hotel tool, and server entrypoint |
| `requirements.txt` | Python dependencies |
| `Dockerfile` | Container image for deployment |
| `.env.sample` | Template for required environment variables |

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `PROJECT_ENDPOINT` | Yes | Your Azure AI Foundry project endpoint (e.g., `https://<project>.services.ai.azure.com`) |
| `MODEL_DEPLOYMENT_NAME` | No | Model deployment name (default: `gpt-4.1-mini`) |

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

This project is licensed under the MIT License. See [LICENSE.md](LICENSE.md).