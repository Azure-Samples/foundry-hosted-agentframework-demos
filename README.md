# Host your agents on Foundry: Microsoft Agent Framework

This is the code companion for the **[Host your agents on Foundry](https://aka.ms/AgentsOnFoundry/series)** livestream series. It builds up a sample "Internal HR Benefits Agent" with [Microsoft Agent Framework](https://learn.microsoft.com/agent-framework/) (the successor to AutoGen and Semantic Kernel) and deploys it as a hosted agent on [Microsoft Foundry](https://learn.microsoft.com/azure/foundry/) using the Azure Developer CLI (`azd`).

> 📺 Watch the session and read the annotated slides: [session write-up](https://github.com/pamelafox/presentation-writeups/blob/main/presentations/foundry-agents-agentframework/outputs/writeup.md).

## What it does

The agent helps employees with HR benefits questions. It grounds answers in company HR documents (via Azure AI Search / Foundry IQ) and uses tool-calling to:

- Answer questions about employee benefits (health insurance, dental, vision, 401k, etc.)
- Look up enrollment deadlines and dates
- Search the web for current information when the knowledge base doesn't have the answer
- Run code via Code Interpreter for data analysis tasks

## How the sample is structured

Rather than jumping straight to the finished agent, the code is organized as a series of **stages** that each add one capability. This mirrors the presentation, so you can run and understand each step on its own.

Single agent ([`agents/`](agents/)):

| Stage | File | What it adds |
|-------|------|--------------|
| 0 | [stage0_local_model.py](agents/stage0_local_model.py) | A fully local agent + tool loop using `OpenAIChatClient` with a small model from Ollama (no cloud) |
| 1 | [stage1_foundry_model.py](agents/stage1_foundry_model.py) | Swaps the local model for a Foundry-deployed model (keyless Entra auth) |
| 2 | [stage2_foundry_iq.py](agents/stage2_foundry_iq.py) | Grounds answers in a Foundry IQ knowledge base via its MCP endpoint |
| 3 | [stage3_foundry_toolbox.py](agents/stage3_foundry_toolbox.py) | Bundles web search, code interpreter, and the KB into one Foundry Toolbox, accessed via its MCP endpoint |
| 4 | [stage4_foundry_hosted.py](agents/stage4_foundry_hosted.py) | Wraps the agent in `ResponsesHostServer` for hosted deployment, using `FoundryChatClient` with a `FoundryToolbox` MCP tool |

Multi-agent workflow ([`workflows/`](workflows/)):

| Stage | File | What it adds |
|-------|------|--------------|
| 1 | [stage1_simple_executors.py](workflows/stage1_simple_executors.py) | A minimal two-node workflow with `WorkflowBuilder` and `Executor` |
| 2 | [stage2_agent_executors.py](workflows/stage2_agent_executors.py) | Uses agents as workflow nodes via `AgentExecutor` |
| 3 | [stage3_as_agent.py](workflows/stage3_as_agent.py) | Wraps a whole workflow as an agent with `.as_agent()` |
| 4 | [stage4_foundry_hosted_as_agent.py](workflows/stage4_foundry_hosted_as_agent.py) | Hosts the workflow on Foundry, exactly like a single agent |

Both the agent and the workflow are declared as services in [azure.yaml](azure.yaml), so `azd up` deploys both in one command.

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

### Knowledge base setup

After `azd up`, the `postprovision` hook automatically creates the search indexes and knowledge base.

If you need to re-run setup manually (for example, after changing index schema or sample data):

```bash
./infra/hooks/write_dot_env.sh  # or .\infra\hooks\write_dot_env.ps1 on Windows
uv run python infra/create-search-indexes.py \
    --endpoint "$AZURE_AI_SEARCH_SERVICE_ENDPOINT" \
    --openai-endpoint "$AZURE_OPENAI_ENDPOINT" \
    --openai-model-deployment "$AZURE_AI_MODEL_DEPLOYMENT_NAME"
```

Or rerun the full postprovision hook:

```bash
azd hooks run postprovision
```

This creates:

- `hrdocs` and `healthdocs` search indexes with sample data
- A single knowledge base (`zava-company-kb`) with both indexes as knowledge sources

### Run locally

1. Sync your `.env` from the azd environment:

    ```bash
    ./infra/hooks/write_dot_env.sh
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

### Test the deployed agent

Once deployed, invoke the agent by name (for the local server started by `azd ai agent run`, use `--local` without the agent name instead):

```bash
azd ai agent invoke hosted-agentframework-agent "What benefits are there, and when do I need to enroll by?"
```

You can also call the hosted agent from Python via the `azure-ai-projects` SDK, which returns an OpenAI-compatible client for the Responses API:

```bash
uv run agents/call_foundry_hosted.py
```

See [agents/call_foundry_hosted.py](agents/call_foundry_hosted.py) for the full example.

For a repeatable suite that exercises each tool path and writes timestamped results under `scripts/test_output_*/`, use the test scripts. Each runs against the deployed agent by default, or pass `--local` to target a running `azd ai agent run`:

| Script | Tests |
|--------|-------|
| [scripts/test_agent.sh](scripts/test_agent.sh) | The hosted agent (`hosted-agentframework-agent`) across its tool paths |
| [scripts/test_workflow.sh](scripts/test_workflow.sh) | The hosted workflow (`hosted-agentframework-workflow`) |
| [scripts/test_kb_mcp.sh](scripts/test_kb_mcp.sh) | The Foundry IQ knowledge base MCP endpoint directly via `curl` |

```bash
./scripts/test_agent.sh              # deployed agent
./scripts/test_agent.sh --local      # local agent (azd ai agent run must be active)
./scripts/test_workflow.sh
./scripts/test_kb_mcp.sh "employee benefits overview"
```

## Evaluation scripts

Scripts for quality evaluation, red teaming, and scheduled runs are in `scripts/`:

| Script | Description |
|--------|-------------|
| `scripts/quality_eval.py` | Run quality evaluation (task adherence, groundedness, relevance) |
| `scripts/scheduled_eval.py` | Set up daily quality evaluation schedule |
| `scripts/scheduled_red_team.py` | Placeholder for scheduled hosted red teaming once supported |
| `scripts/continuous_eval.py` | Set up hourly continuous evaluation from recent agent traces |
| `scripts/continuous_eval_alert.py` | Create an Azure Monitor alert for low evaluation pass rates |
| `scripts/red_team_scan.py` | Attempt the hosted red-team flow; currently non-actionable for this sample |
| `scripts/red_team_scan_local.py` | Run local-preview red teaming against `azd ai agent run` |
| `scripts/send_requests.py` | Send a batch of varied (and deliberately tricky) requests to generate sample traces |
| `scripts/locustfile.py` | Load-test the hosted agent with Locust to generate traffic under concurrency |

Continuous evaluation draws from recent agent traces, so you need some traffic before there's anything to evaluate. Use [scripts/send_requests.py](scripts/send_requests.py) for a quick sequential batch, or [scripts/locustfile.py](scripts/locustfile.py) for concurrent load, to populate the agent with sample data first:

```bash
uv run scripts/send_requests.py            # 60 requests (default); pass a number to change
locust -f scripts/locustfile.py --headless -u 10 -r 2 -t 5m
```

> **Note:** Red teaming requires a supported region (East US 2, Sweden Central, etc.). See [evaluation region support](https://learn.microsoft.com/en-us/azure/foundry/concepts/evaluation-regions-limits-virtual-network).
> **Current limitation:** Hosted-agent cloud red teaming is not supported yet for Foundry hosted agents. Use `scripts/red_team_scan_local.py` with a locally running agent for now, and treat `scripts/red_team_scan.py` as a future hosted path to re-enable once the service support lands.

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

This sample enables sensitive data in traces (tool call arguments, prompts, responses) by default, via `enable_instrumentation(enable_sensitive_data=True)` in [agents/stage4_foundry_hosted.py](agents/stage4_foundry_hosted.py). This is useful for debugging, but for production you should set `enable_sensitive_data=False`.

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