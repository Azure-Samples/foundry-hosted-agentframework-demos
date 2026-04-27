"""Create (or update) the Foundry Toolbox with web search, code interpreter,
and Foundry IQ knowledge base tools.

Usage:
    uv run python infra/create-toolbox.py

Requires environment variables:
    FOUNDRY_PROJECT_ENDPOINT  — Foundry project endpoint URL
    CUSTOM_FOUNDRY_AGENT_TOOLBOX_NAME — Toolbox name (default: hr-agent-tools)
    AZURE_AI_SEARCH_SERVICE_ENDPOINT — Azure AI Search service URL
    AZURE_AI_SEARCH_KNOWLEDGE_BASE_NAME — Knowledge base name (default: zava-company-kb)
    AZURE_AI_SEARCH_KB_MCP_CONNECTION_NAME — KB MCP connection name (default: kb-mcp-connection)
"""

import os

import httpx
from azure.identity import AzureDeveloperCliCredential
from dotenv import load_dotenv

load_dotenv(dotenv_path=".env", override=True)

_API_VERSION = "v1"
_SCOPE = "https://ai.azure.com/.default"
_FEATURE_HEADER = "Toolboxes=V1Preview"


def _headers(credential: AzureDeveloperCliCredential) -> dict:
    token = credential.get_token(_SCOPE).token
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Foundry-Features": _FEATURE_HEADER,
    }


def create_or_update_toolbox(endpoint: str, toolbox_name: str, kb_mcp_url: str, kb_mcp_connection_name: str) -> None:
    """Create a new version of the toolbox with web search, code interpreter, and KB MCP tools."""
    credential = AzureDeveloperCliCredential(tenant_id=os.environ["AZURE_TENANT_ID"])
    base_url = f"{endpoint.rstrip('/')}/toolboxes/{toolbox_name}"

    tools = [
        {"type": "web_search", "name": "web_search"},
        {"type": "code_interpreter", "name": "code_interpreter"},
        {
            "type": "mcp",
            "server_label": "knowledge-base",
            "server_url": kb_mcp_url,
            "project_connection_id": kb_mcp_connection_name,
            "allowed_tools": ["knowledge_base_retrieve"],
        },
    ]

    # 1. Create a new version
    print(f"Creating toolbox '{toolbox_name}' at {endpoint} ...")
    resp = httpx.post(
        f"{base_url}/versions",
        params={"api-version": _API_VERSION},
        headers=_headers(credential),
        json={
            "tools": tools,
            "description": "Web search, code interpreter, and knowledge base tools for the HR agent.",
        },
        timeout=60,
    )
    if not resp.is_success:
        print(f"Create version failed ({resp.status_code}): {resp.text}")
        resp.raise_for_status()
    version = resp.json().get("version")
    print(f"Toolbox '{toolbox_name}' version {version} created.")

    # 2. Promote this version to default
    resp = httpx.patch(
        base_url,
        params={"api-version": _API_VERSION},
        headers=_headers(credential),
        json={"default_version": version},
        timeout=60,
    )
    resp.raise_for_status()
    print(f"Toolbox '{toolbox_name}' default version set to {version}.")


if __name__ == "__main__":
    endpoint = os.environ["FOUNDRY_PROJECT_ENDPOINT"]
    toolbox_name = os.environ.get("CUSTOM_FOUNDRY_AGENT_TOOLBOX_NAME", "hr-agent-tools")
    search_endpoint = os.environ["AZURE_AI_SEARCH_SERVICE_ENDPOINT"]
    kb_name = os.environ.get("AZURE_AI_SEARCH_KNOWLEDGE_BASE_NAME", "zava-company-kb")
    kb_mcp_connection_name = os.environ.get("AZURE_AI_SEARCH_KB_MCP_CONNECTION_NAME", "kb-mcp-connection")

    kb_mcp_url = (
        f"{search_endpoint.rstrip('/')}/knowledgebases/{kb_name}"
        f"/mcp?api-version=2025-11-01-preview"
    )

    create_or_update_toolbox(endpoint, toolbox_name, kb_mcp_url, kb_mcp_connection_name)