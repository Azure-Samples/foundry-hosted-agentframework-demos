"""
Internal HR Helper - A simple agent with a tool to answer health insurance questions.
Uses Microsoft Agent Framework with Azure AI Foundry.
Ready for deployment to Foundry Hosted Agent service.

Run using:
azd ai agent run
"""

import logging
import os
from collections.abc import Awaitable, Callable
from datetime import date

from agent_framework import Agent, tool
from agent_framework._middleware import ChatContext
from agent_framework._types import ChatResponse, Message
from agent_framework.foundry import FoundryChatClient
from agent_framework.observability import enable_instrumentation
from agent_framework_foundry_hosting import FoundryToolbox, ResponsesHostServer
from agent_framework_openai._exceptions import OpenAIContentFilterException
from azure.identity import (
    AzureDeveloperCliCredential,
    ChainedTokenCredential,
    ManagedIdentityCredential,
)
from dotenv import load_dotenv

load_dotenv(dotenv_path=".env", override=True)

logger = logging.getLogger("hr-agent")


# Configure these for your Foundry project via environment variables (see .env.sample)
PROJECT_ENDPOINT = os.environ["FOUNDRY_PROJECT_ENDPOINT"]
MODEL_DEPLOYMENT_NAME = os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"]
TOOLBOX_NAME = os.environ.get("CUSTOM_FOUNDRY_AGENT_TOOLBOX_NAME", "hr-agent-tools")
SEARCH_ENDPOINT = os.environ["AZURE_AI_SEARCH_SERVICE_ENDPOINT"]
KB_NAME = os.environ.get("AZURE_AI_SEARCH_KNOWLEDGE_BASE_NAME", "zava-company-kb")
CONTENT_FILTER_MESSAGE = (
    "I can't help with that request because it violates content safety policies. "
    "If you have a safer or policy-compliant version of the question, I can help with that instead."
)


@tool
def get_current_date() -> str:
    """Return the current date in ISO format."""
    logger.info("Fetching current date")
    return date.today().isoformat()

@tool
def get_enrollment_deadline_info() -> dict[str, str]:
    """Return enrollment timeline details for health insurance plans."""
    logger.info("Fetching enrollment deadline information")
    return {
        "enrollment_opens": "2026-11-11",
        "enrollment_closes": "2026-11-30"
    }


async def content_filter_middleware(
    context: ChatContext, call_next: Callable[[], Awaitable[None]]
) -> None:
    """Convert model-side content-filter blocks into a friendly assistant response."""
    try:
        await call_next()
    except OpenAIContentFilterException:
        logger.info("Returning friendly refusal for content-filtered prompt")
        context.result = ChatResponse(
            messages=Message("assistant", [CONTENT_FILTER_MESSAGE]),
            finish_reason="stop",
        )


def main():
    """Main function to run the agent as a web server."""
    managed_identity_credential = ManagedIdentityCredential()
    azure_dev_cli_credential = AzureDeveloperCliCredential(tenant_id=os.getenv("AZURE_TENANT_ID"), process_timeout=60)
    credential = ChainedTokenCredential(managed_identity_credential, azure_dev_cli_credential)

    # Foundry Toolbox MCP tool forwards the platform call-id required by protocol v2.
    toolbox_endpoint = f"{PROJECT_ENDPOINT.rstrip('/')}/toolboxes/{TOOLBOX_NAME}/mcp?api-version=v1"
    logger.info("Using Foundry Toolbox MCP at %s", toolbox_endpoint)
    toolbox_mcp_tool = FoundryToolbox(
        credential=credential,
        url=toolbox_endpoint,
        name="toolbox",
        load_prompts=False,
    )


    client = FoundryChatClient(
        project_endpoint=PROJECT_ENDPOINT,
        model=MODEL_DEPLOYMENT_NAME,
        credential=credential,
        middleware=[content_filter_middleware],
    )

    agent = Agent(
        client=client,  # ty:ignore
        name="InternalHRHelper",
        instructions="""You are an internal HR helper focused on employee benefits and company information.
        Use the knowledge base tool to answer questions and ground all answers in provided context.
        Use web search to look up current information when the knowledge base does not have the answer.
        Use these tools if the user needs information on benefits deadlines:
        get_enrollment_deadline_info, get_current_date.
        If you cannot answer a question, explain that you do not have available information
        to fully answer the question.""",
        tools=[
            get_enrollment_deadline_info,
            get_current_date,
            toolbox_mcp_tool
        ],
        default_options={"store": False},
    )

    server = ResponsesHostServer(agent)
    server.run()

if __name__ == "__main__":
    logger.setLevel(logging.INFO)

    enable_instrumentation(enable_sensitive_data=True)

    main()
