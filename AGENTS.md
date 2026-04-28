# Instructions for Coding Agents

The goal of this project is to be the teaching example for this livestream series:

https://developer.microsoft.com/en-us/reactor/series/S-1655/

Specifically, these two sessions:

## Host your agents on Foundry: Microsoft Agent Framework

In this three-part series, we're showing you how to host your own agents on Microsoft Foundry.

In our first session, we'll deploy agents built with Microsoft Agent Framework (the successor of Autogen and Semantic Kernel).

Starting with a simple agent, we'll add Foundry tools like Code Interpreter, ground the agent in enterprise data with Foundry IQ, and finally deploy multi-agent workflows.

Along the way, we'll use the Foundry UI to interact with the hosted agent, testing it out in the playground and observing the traces from the reasoning and tool calls.

All code samples will be open-source and ready for easy deployment to your own Microsoft Foundry using the Azure Developer CLI.

## Host your agents on Foundry: Quality & safety evaluations

In this three-part series, we're showing you how to host your own agents on Microsoft Foundry.

In our third session, we'll ensure that our AI agents are producing high-quality outputs and operating safely and responsibly.

First we'll explore what it means for agent outputs to be high quality, using built-in evaluators to check overall task adherence and then building custom evaluators for domain-specific checks. With Foundry hosted agents, we can run bulk evaluations on demand, set up scheduled evaluations, and even enable continuous evaluation on a subset of live agent traces.

Next we'll discuss safety systems that can be layered on top of agents and audit agents for potential safety risks. To improve compliance with an organization's goals, we can configure custom policies and guardrails that can be shared across agents.

Finally, we can ensure that adversarial inputs can't produce unsafe outputs by running automated red-teaming scans on agents, and even schedule those to run regularly as well. With all of these evaluation and compliance features available in Foundry, you can have more confidence hosting your agents in production.

## Azure conventions

This repository follows Azure Developer CLI (`azd ai`) environment variable naming conventions.

Always use these names in code, scripts, and docs:

- `FOUNDRY_PROJECT_ENDPOINT`
- `AZURE_AI_MODEL_DEPLOYMENT_NAME`
- `AZURE_AI_SEARCH_SERVICE_ENDPOINT`
- `AZURE_AI_SEARCH_CONNECTION_NAME`

Do not introduce custom aliases unless there is a temporary backward-compatibility need.

Reference:

- https://learn.microsoft.com/en-us/azure/developer/azure-developer-cli/extensions/azure-ai-foundry-extension#manage-environment-variables

## Hosted agent environment variables

**Reserved prefixes:** The hosted agent platform reserves the `FOUNDRY_*` and `AGENT_*`
environment variable prefixes. Do not use these prefixes for custom variables in
`agent.yaml` — the deploy will fail with `invalid_payload`. If you need a custom variable
that references a Foundry concept, use a different prefix (e.g., `CUSTOM_FOUNDRY_AGENT_TOOLBOX_NAME`).

**Auto-injected variables:** The platform automatically injects these variables into the
container at runtime — do **not** set them in `agent.yaml`:

- `FOUNDRY_PROJECT_ENDPOINT` — the Foundry project endpoint
- `APPLICATIONINSIGHTS_CONNECTION_STRING` — the App Insights connection string for tracing

## Logging

Do NOT call `logging.basicConfig()` in agent code that uses `ResponsesHostServer`.

`ResponsesHostServer` inherits from `AgentServerHost`, which calls `configure_observability()` during
`__init__`. That function (`azure.ai.agentserver.core._tracing`) adds its own `StreamHandler` to the
root logger with a timestamped format. If you also call `logging.basicConfig()`, you get two
`StreamHandler`s on root and every log line appears twice with different formats.

Instead, let the agentserver handle logging setup. If you need to adjust log levels for
specific loggers (e.g., silencing noisy SDK loggers), do that directly:

```python
logging.getLogger("azure.core.pipeline").setLevel(logging.WARNING)
```

If you need full control over logging and want to suppress the agentserver's handler, pass
`configure_observability=None` when creating the server:

```python
server = ResponsesHostServer(agent, configure_observability=None)
```

Note: this also disables the agentserver's OTel tracing/metrics setup, so only do this
if you're configuring observability yourself.

## Dependency management

`pyproject.toml` and `uv.lock` exist in both the repo root and `workflows/`. Each
service has its own Docker build context, so both copies are needed. When you add or
update dependencies, copy the files to keep them in sync:

```bash
cp pyproject.toml workflows/pyproject.toml
cp uv.lock workflows/uv.lock
```

## Testing hooks

To re-run azd hooks without a full deploy:

```bash
azd hooks run postprovision
azd hooks run postdeploy
```

## Filing bugs

This is where to search and file bugs for the technologies used in this repository:

* Agent framework: github.com/microsoft/agent-framework
* azd: github.com/Azure/azure-dev
* Agentserver wrapper SDK (part of Azure Python SDK): github.com/azure/azure-sdk-for-python

## Relevant documentation

MAF Observability
https://learn.microsoft.com/en-us/agent-framework/agents/observability?pivots=programming-language-python#spans-and-metrics

Set up tracing in Foundry
https://learn.microsoft.com/en-us/azure/foundry/observability/how-to/trace-agent-setup

Hosted agents overview:
https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/hosted-agents

Deploy a hosted agent (tutorial):
https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/deploy-hosted-agent?tabs=bash

Evaluation support across region:
https://learn.microsoft.com/en-us/azure/foundry/concepts/evaluation-regions-limits-virtual-network

Cloud-based red teaming
https://learn.microsoft.com/en-us/azure/foundry/how-to/develop/run-ai-red-teaming-cloud