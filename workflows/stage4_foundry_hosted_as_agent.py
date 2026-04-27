"""
Workflow demo: Multi-agent workflow using Agent Framework's WorkflowBuilder.

Two agents in a chain:
    writer → formatter

The writer drafts content and the formatter styles it with Markdown and emojis.
Each agent only sees the output of the previous agent (context_mode="last_agent").
"""

import os

from agent_framework import Agent, AgentExecutor, WorkflowBuilder
from agent_framework.foundry import FoundryChatClient
from agent_framework.observability import enable_instrumentation
from agent_framework_foundry_hosting import ResponsesHostServer
from azure.identity import AzureDeveloperCliCredential, ChainedTokenCredential, ManagedIdentityCredential
from dotenv import load_dotenv

load_dotenv(dotenv_path=".env", override=True)

PROJECT_ENDPOINT = os.environ["FOUNDRY_PROJECT_ENDPOINT"]
MODEL_DEPLOYMENT_NAME = os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"]


def main():
    user_assigned_managed_identity_credential = ManagedIdentityCredential(client_id=os.getenv("AZURE_CLIENT_ID"))
    azure_dev_cli_credential = AzureDeveloperCliCredential(tenant_id=os.getenv("AZURE_TENANT_ID"), process_timeout=60)
    credential = ChainedTokenCredential(user_assigned_managed_identity_credential, azure_dev_cli_credential)

    client = FoundryChatClient(
        project_endpoint=PROJECT_ENDPOINT,
        model=MODEL_DEPLOYMENT_NAME,
        credential=credential,
    )

    writer_agent = Agent(
        client=client,
        name="Writer",
        instructions=(
            "You are a concise content writer. "
            "Write a clear, engaging short article (2-3 paragraphs) based on the user's topic. "
            "Focus on accuracy and readability."
        ),
    )

    format_agent = Agent(
        client=client,
        name="Formatter",
        instructions=(
            "You are an expert content formatter. "
            "Take the provided text and format it with Markdown (bold, headers, lists) "
            "and relevant emojis to make it visually engaging. "
            "Preserve the original meaning and content."
        ),
    )

    writer_executor = AgentExecutor(writer_agent, context_mode="last_agent")
    format_executor = AgentExecutor(format_agent, context_mode="last_agent")

    workflow_agent = (
        WorkflowBuilder(
            start_executor=writer_executor,
            output_executors=[format_executor],
        )
        .add_edge(writer_executor, format_executor)
        .build()
        .as_agent()
    )

    server = ResponsesHostServer(workflow_agent)
    server.run()


if __name__ == "__main__":
    enable_instrumentation(enable_sensitive_data=True)
    main()
