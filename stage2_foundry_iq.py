"""
Stage 2: Add Foundry IQ — ground answers in an enterprise knowledge base
served by Azure AI Search via its MCP endpoint.

Slide-friendly version: uses Agent Framework's built-in
`MCPStreamableHTTPTool` directly, with `header_provider` for bearer-token
auth. No custom wrapper needed.

What changes from Stage 1:
    - Open an `MCPStreamableHTTPTool` pointing at the KB MCP endpoint.
    - Pass it as one more tool on the Agent.
    - Update the system prompt to prefer the KB.

Prerequisites (in addition to Stage 1):
    AZURE_AI_SEARCH_SERVICE_ENDPOINT=https://<your-search>.search.windows.net
    AZURE_AI_SEARCH_KNOWLEDGE_BASE_NAME=zava-company-kb

Run:
    python stage2_foundry_iq.py
"""

import asyncio
import logging
import os
from datetime import date
from typing import Any

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
logger = logging.getLogger("stage2")


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


@tool
def get_enrollment_deadline_info() -> dict:
    """Return enrollment timeline details for health insurance plans."""
    logger.info("[tool] get_enrollment_deadline_info()")
    return {
        "benefits_enrollment_opens": "2026-11-11",
        "benefits_enrollment_closes": "2026-11-30",
    }


async def main():
    credential = DefaultAzureCredential()

    # --- Chat client (Foundry / Azure OpenAI) -----------------------------
    aoai_token_provider = get_bearer_token_provider(
        credential, "https://cognitiveservices.azure.com/.default"
    )
    client = OpenAIChatClient(
        base_url=f"{os.environ['AZURE_OPENAI_ENDPOINT']}/openai/v1/",
        api_key=aoai_token_provider,
        model=os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"],
    )

    # --- Foundry IQ knowledge base via MCP --------------------------------
    mcp_url = (
        f"{os.environ['AZURE_AI_SEARCH_SERVICE_ENDPOINT']}"
        f"/knowledgebases/{os.environ['AZURE_AI_SEARCH_KNOWLEDGE_BASE_NAME']}"
        f"/mcp?api-version=2025-11-01-Preview"
    )

    async def _get_auth_headers(context: dict[str, Any]) -> dict[str, str]:
        token = await credential.get_token("https://search.azure.com/.default")
        return {"Authorization": f"Bearer {token.token}"}

    async with MCPStreamableHTTPTool(
        name="knowledge-base",
        url=mcp_url,
        header_provider=_get_auth_headers,
        allowed_tools=["knowledge_base_retrieve"],
    ) as kb_mcp_tool:
        agent = Agent(
            client=client,
            instructions=(
                f"You are an internal HR helper for Zava. Today's date is {date.today().isoformat()}. "
                "Use the knowledge base tool to answer questions about HR policies, benefits, "
                "and company information, and ground all answers in the retrieved context. "
                "Use get_enrollment_deadline_info for benefits enrollment timing. "
                "If you cannot answer from the tools, say so clearly."
            ),
            tools=[kb_mcp_tool, get_enrollment_deadline_info],
        )

        response = await agent.run(
            "What PerksPlus benefits are there, and when do I need to enroll by?"
        )
        console.print("\n[bold]Agent answer:[/bold]")
        console.print(Markdown(response.text))

    await credential.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s", handlers=[RichHandler(console=console, show_path=False)])
    logging.getLogger("azure.identity").setLevel(logging.WARNING)
    logging.getLogger("azure.core").setLevel(logging.WARNING)
    asyncio.run(main())
