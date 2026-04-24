"""
Stage 3: Add Foundry Toolbox — web search, code interpreter, and knowledge base via MCP.

What changes from Stage 2:
    - Replace the direct KB MCP tool with a Foundry Toolbox that bundles
      web_search, code_interpreter, and the Foundry IQ knowledge_base_retrieve
      tool behind a single MCP endpoint.

Prerequisites (in addition to Stage 1):
    - A Foundry Toolbox created with web_search, code_interpreter, and KB MCP tools.
      The azd up process uses "infra/create_toolbox.py" to create the toolbox.

Run:
    python agents/stage3_foundry_toolbox.py
"""

import asyncio
import logging
import os
from datetime import date

import httpx
import mcp.types
from agent_framework import Agent, MCPStreamableHTTPTool, tool
from agent_framework.openai import OpenAIChatClient
from azure.identity.aio import DefaultAzureCredential, get_bearer_token_provider
from dotenv import load_dotenv
from rich.console import Console
from rich.logging import RichHandler
from rich.markdown import Markdown

load_dotenv(override=True)

console = Console()
logger = logging.getLogger("stage3")

@tool
def get_enrollment_deadline_info() -> dict:
    """Return enrollment timeline details for health insurance plans."""
    logger.info("[tool] get_enrollment_deadline_info()")
    return {
        "enrollment_opens": "2026-11-11",
        "enrollment_closes": "2026-11-30",
    }


class ToolboxAuth(httpx.Auth):
    """httpx Auth that injects a fresh bearer token for the Foundry Toolbox MCP endpoint."""

    def __init__(self, token_provider) -> None:
        self._token_provider = token_provider

    async def async_auth_flow(self, request):
        """Add Authorization header with a fresh token on every request."""
        token = await self._token_provider()
        request.headers["Authorization"] = f"Bearer {token}"
        yield request


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


async def main():
    credential = DefaultAzureCredential()

    # --- Chat client (Foundry / Azure OpenAI) -----------------------------
    aoai_token_provider = get_bearer_token_provider(
        credential, "https://cognitiveservices.azure.com/.default"
    )
    client = OpenAIChatClient(
        base_url=f"{os.environ['AZURE_OPENAI_ENDPOINT']}openai/v1/",
        api_key=aoai_token_provider,
        model=os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"],
    )

    # --- Foundry Toolbox (web search, code interpreter, knowledge base) via MCP ---
    toolbox_name = os.environ["CUSTOM_FOUNDRY_AGENT_TOOLBOX_NAME"]
    project_endpoint = os.environ["FOUNDRY_PROJECT_ENDPOINT"]
    toolbox_endpoint = f"{project_endpoint.rstrip('/')}/toolboxes/{toolbox_name}/mcp?api-version=v1"

    toolbox_token_provider = get_bearer_token_provider(credential, "https://ai.azure.com/.default")
    toolbox_http_client = httpx.AsyncClient(
        auth=ToolboxAuth(toolbox_token_provider),
        headers={"Foundry-Features": "Toolboxes=V1Preview"},
        timeout=120.0,
    )
    toolbox_mcp_tool = MCPStreamableHTTPTool(
        name="toolbox",
        url=toolbox_endpoint,
        http_client=toolbox_http_client,
        load_prompts=False,
    )

    async with toolbox_mcp_tool:
        agent = Agent(
            client=client,
            instructions=(
                f"You are an internal HR helper for Zava. Today's date is {date.today().isoformat()}. "
                "Use the knowledge base tool to answer questions about HR policies, benefits, "
                "and company information, and ground all answers in the retrieved context. "
                "Use get_enrollment_deadline_info for benefits enrollment timing. "
                "You can use web search to look up current information when the knowledge base "
                "does not have the answer. "
                "If you cannot answer from the tools, say so clearly."
            ),
            tools=[get_enrollment_deadline_info, toolbox_mcp_tool],
        )

        #response = await agent.run("What is the weather today in Seattle, the Zava HQ?")
        response = await agent.run("What PerksPlus benefits are available to employees?")
        console.print("\n[bold]Agent answer:[/bold]")
        console.print(Markdown(response.text))

    await toolbox_http_client.aclose()
    await credential.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s", handlers=[RichHandler(console=console, show_path=False)])
    logging.getLogger("azure.identity").setLevel(logging.WARNING)
    logging.getLogger("azure.core").setLevel(logging.WARNING)
    logging.getLogger("mcp").setLevel(logging.DEBUG)
    logging.getLogger("httpx").setLevel(logging.DEBUG)
    asyncio.run(main())
