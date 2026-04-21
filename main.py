"""
Internal HR Helper - A simple agent with a tool to answer health insurance questions.
Uses Microsoft Agent Framework with Azure AI Foundry.
Ready for deployment to Foundry Hosted Agent service.

Run using:
azd ai agent run
"""

import json
import logging
import os
from datetime import date
from typing import Annotated

import httpx
from agent_framework import Agent, MCPStreamableHTTPTool
from agent_framework.foundry import FoundryChatClient
from agent_framework.observability import enable_instrumentation
from agent_framework_foundry_hosting import ResponsesHostServer
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from dotenv import load_dotenv
from pydantic import Field

load_dotenv(dotenv_path=".env", override=True)


logger = logging.getLogger("hr-agent")


# Configure these for your Foundry project via environment variables (see .env.sample)
PROJECT_ENDPOINT = os.environ["FOUNDRY_PROJECT_ENDPOINT"]
MODEL_DEPLOYMENT_NAME = os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"]
SEARCH_SERVICE_ENDPOINT = os.environ["AZURE_AI_SEARCH_SERVICE_ENDPOINT"]
KNOWLEDGE_BASE_NAME = os.environ["AZURE_AI_SEARCH_KNOWLEDGE_BASE_NAME"]
TOOLBOX_NAME = os.environ.get("CUSTOM_FOUNDRY_AGENT_TOOLBOX_NAME", "hr-agent-tools")


def get_current_date() -> str:
    """Return the current date in ISO format."""
    logger.info("Fetching current date")
    return date.today().isoformat()

def get_enrollment_deadline_info() -> str:
    """Return enrollment timeline details for health insurance plans."""
    logger.info("Fetching enrollment deadline information")
    return {
        "benefits_enrollment_opens": "2026-11-11",
        "benefits_enrollment_closes": "2026-11-30"
    }


class _ToolboxAuth(httpx.Auth):
    """httpx Auth that injects a fresh bearer token for the Foundry Toolbox MCP endpoint."""

    def __init__(self, token_provider) -> None:
        self._token_provider = token_provider

    def auth_flow(self, request):
        """Add Authorization header with a fresh token on every request."""
        request.headers["Authorization"] = f"Bearer {self._token_provider()}"
        yield request


class KnowledgeBaseMCPTool:
    """Wraps the KB MCP endpoint as a callable tool, working around the MCP SDK
    validation bug where the endpoint returns resource content with uri: null.
    See: https://github.com/Azure/azure-search/issues/XXXX
    """

    def __init__(self, http_client: httpx.Client, mcp_url: str) -> None:
        self._http_client = http_client
        self._mcp_url = mcp_url
        self._headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        self._initialized = False

    def _ensure_initialized(self) -> None:
        """Perform MCP handshake if not already done."""
        if self._initialized:
            return
        self._http_client.post(
            self._mcp_url,
            json={"jsonrpc": "2.0", "id": 0, "method": "initialize", "params": {
                "protocolVersion": "2025-11-25",
                "capabilities": {"sampling": {}},
                "clientInfo": {"name": "hr-agent", "version": "0.1.0"},
            }},
            headers=self._headers,
        )
        self._http_client.post(
            self._mcp_url,
            json={"jsonrpc": "2.0", "method": "notifications/initialized"},
            headers=self._headers,
        )
        self._initialized = True

    def retrieve(
        self,
        queries: Annotated[list[str], Field(
            description="1 to 4 concise search queries (max ~12 words each). "
            "Include facets and alternative formulations as separate array entries.",
            min_length=1,
            max_length=4,
        )],
    ) -> str:
        """Search the Zava company knowledge base for HR policies, benefits, insurance, and job information.

        Use this tool to find information from internal company documents before answering HR-related questions.
        """
        self._ensure_initialized()
        logger.info("KB MCP retrieve: %s", queries)
        response = self._http_client.post(
            self._mcp_url,
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {
                "name": "knowledge_base_retrieve",
                "arguments": {"queries": queries},
            }},
            headers=self._headers,
        )
        # Parse SSE response, extract text from resource content items
        for line in response.text.split("\n"):
            if not line.startswith("data:"):
                continue
            data = json.loads(line[5:].strip())
            if "result" not in data or "content" not in data["result"]:
                continue
            snippets = []
            for item in data["result"]["content"]:
                if item.get("type") == "resource" and "resource" in item:
                    snippets.append(item["resource"].get("text", ""))
                elif item.get("type") == "text":
                    snippets.append(item.get("text", ""))
            return "\n\n---\n\n".join(snippets)
        return "No results found."


def main():
    """Main function to run the agent as a web server."""
    mcp_url = (
        f"{SEARCH_SERVICE_ENDPOINT}/knowledgebases/{KNOWLEDGE_BASE_NAME}"
        f"/mcp?api-version=2025-11-01-Preview"
    )
    logger.info("Using KB MCP tool at %s", mcp_url)

    credential = DefaultAzureCredential()

    def _add_auth(request: httpx.Request) -> None:
        token = credential.get_token("https://search.azure.com/.default")
        request.headers["Authorization"] = f"Bearer {token.token}"

    http_client = httpx.Client(
        event_hooks={"request": [_add_auth]},
        timeout=httpx.Timeout(30.0, read=300.0),
    )
    kb_tool = KnowledgeBaseMCPTool(http_client, mcp_url)

    # Foundry Toolbox MCP tool (replaces individual web_search / code_interpreter tools)
    toolbox_endpoint = f"{PROJECT_ENDPOINT.rstrip('/')}/toolboxes/{TOOLBOX_NAME}/mcp?api-version=v1"
    logger.info("Using Foundry Toolbox MCP at %s", toolbox_endpoint)
    token_provider = get_bearer_token_provider(credential, "https://ai.azure.com/.default")
    toolbox_http_client = httpx.AsyncClient(
        auth=_ToolboxAuth(token_provider),
        headers={"Foundry-Features": "Toolboxes=V1Preview"},
        timeout=120.0,
    )
    toolbox_mcp_tool = MCPStreamableHTTPTool(
        name="toolbox",
        url=toolbox_endpoint,
        http_client=toolbox_http_client,
        load_prompts=False,
    )

    client = FoundryChatClient(
        project_endpoint=PROJECT_ENDPOINT,
        model=MODEL_DEPLOYMENT_NAME,
        credential=credential,
    )

    agent = Agent(
        client=client,
        name="InternalHRHelper",
        instructions="""You are an internal HR helper focused on employee benefits and company information.
        Use the knowledge base tool to answer questions and ground all answers in provided context.
        You can use web search to look up current information when the knowledge base does not have the answer.
        You can use these tools if the user needs information on benefits deadlines: get_enrollment_deadline_info, get_current_date.
        If you cannot answer a question, explain that you do not have available information to fully answer the question.""",
        tools=[
            kb_tool.retrieve,
            get_enrollment_deadline_info,
            get_current_date,
            toolbox_mcp_tool,
        ],
        default_options={"store": False},
    )

    server = ResponsesHostServer(agent)
    server.run()

if __name__ == "__main__":
    logger.setLevel(logging.INFO)

    enable_instrumentation(enable_sensitive_data=True)

    main()
