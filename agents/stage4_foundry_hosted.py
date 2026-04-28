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

import httpx
import mcp.types
from agent_framework import Agent, MCPStreamableHTTPTool, tool
from agent_framework._middleware import ChatContext
from agent_framework._types import ChatResponse, Message
from agent_framework.foundry import FoundryChatClient
from agent_framework.observability import enable_instrumentation
from agent_framework_foundry_hosting import ResponsesHostServer
from agent_framework_openai._exceptions import OpenAIContentFilterException
from azure.identity import (
    AzureDeveloperCliCredential,
    ChainedTokenCredential,
    ManagedIdentityCredential,
    get_bearer_token_provider,
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
    "I can’t help with that request because it violates content safety policies. "
    "If you have a safer or policy-compliant version of the question, I can help with that instead."
)


@tool
def get_current_date() -> str:
    """Return the current date in ISO format."""
    logger.info("Fetching current date")
    return date.today().isoformat()

@tool
def get_enrollment_deadline_info() -> str:
    """Return enrollment timeline details for health insurance plans."""
    logger.info("Fetching enrollment deadline information")
    return {
        "enrollment_opens": "2026-11-11",
        "enrollment_closes": "2026-11-30"
    }


class ToolboxAuth(httpx.Auth):
    """httpx Auth that injects a fresh bearer token for the Foundry Toolbox MCP endpoint."""

    def __init__(self, token_provider) -> None:
        self._token_provider = token_provider

    def auth_flow(self, request):
        """Add Authorization header with a fresh token on every request."""
        request.headers["Authorization"] = f"Bearer {self._token_provider()}"
        yield request


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


# ---------------------------------------------------------------------------
# Workaround: Azure AI Search KB MCP returns resource content with uri: null
# or uri: "", which fails pydantic AnyUrl validation in the MCP SDK.
# Relax the uri field to accept any string (or None) so parsing succeeds.
# ---------------------------------------------------------------------------
for _cls in [mcp.types.ResourceContents, mcp.types.TextResourceContents, mcp.types.BlobResourceContents]:
    _cls.model_fields["uri"].annotation = str | None
    _cls.model_fields["uri"].default = None
    _cls.model_fields["uri"].metadata = []
for _cls in [mcp.types.ResourceContents, mcp.types.TextResourceContents,
             mcp.types.BlobResourceContents, mcp.types.EmbeddedResource,
             mcp.types.CallToolResult]:
    _cls.model_rebuild(force=True)


def main():
    """Main function to run the agent as a web server."""
    user_assigned_managed_identity_credential = ManagedIdentityCredential(client_id=os.getenv("AZURE_CLIENT_ID"))
    azure_dev_cli_credential = AzureDeveloperCliCredential(tenant_id=os.getenv("AZURE_TENANT_ID"), process_timeout=60)
    credential = ChainedTokenCredential(user_assigned_managed_identity_credential, azure_dev_cli_credential)

    # Foundry Toolbox MCP tool (web_search, code_interpreter, and knowledge_base_retrieve)
    toolbox_endpoint = f"{PROJECT_ENDPOINT.rstrip('/')}/toolboxes/{TOOLBOX_NAME}/mcp?api-version=v1"
    logger.info("Using Foundry Toolbox MCP at %s", toolbox_endpoint)
    token_provider = get_bearer_token_provider(credential, "https://ai.azure.com/.default")
    toolbox_http_client = httpx.AsyncClient(
        auth=ToolboxAuth(token_provider),
        headers={"Foundry-Features": "Toolboxes=V1Preview"},
        timeout=120.0,
    )
    toolbox_mcp_tool = MCPStreamableHTTPTool(
        name="toolbox",
        url=toolbox_endpoint,
        http_client=toolbox_http_client,
        # Our toolbox includes Foundry IQ MCP KB, but that currently doesn't work.
        # Fix should be out April 30th week. For now, just allow-list the other tools.
        allowed_tools=["web_search", "code_interpreter"],
        load_prompts=False,
    )

    # Direct KB MCP connection (workaround: toolbox names KB tool with a dot,
    # which the hosted agent Responses API rejects)
    kb_mcp_url = f"{SEARCH_ENDPOINT.rstrip('/')}/knowledgebases/{KB_NAME}/mcp?api-version=2025-11-01-Preview"
    logger.info("Using KB MCP at %s", kb_mcp_url)
    search_token_provider = get_bearer_token_provider(credential, "https://search.azure.com/.default")
    kb_http_client = httpx.AsyncClient(
        auth=ToolboxAuth(search_token_provider),
        timeout=120.0,
    )
    kb_mcp_tool = MCPStreamableHTTPTool(
        name="knowledge_base",
        url=kb_mcp_url,
        http_client=kb_http_client,
        allowed_tools=["knowledge_base_retrieve"],
        load_prompts=False,
    )

    client = FoundryChatClient(
        project_endpoint=PROJECT_ENDPOINT,
        model=MODEL_DEPLOYMENT_NAME,
        credential=credential,
        middleware=[content_filter_middleware],
    )

    agent = Agent(
        client=client,
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
            toolbox_mcp_tool,
            kb_mcp_tool,
        ],
        default_options={"store": False},
    )

    server = ResponsesHostServer(agent)
    server.run()

if __name__ == "__main__":
    logger.setLevel(logging.INFO)

    enable_instrumentation(enable_sensitive_data=True)

    main()
