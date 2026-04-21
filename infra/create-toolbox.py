"""Create (or update) the Foundry Toolbox with web search and code interpreter tools.

Usage:
    uv run python infra/create-toolbox.py

Requires environment variables:
    FOUNDRY_PROJECT_ENDPOINT  — Foundry project endpoint URL
    CUSTOM_FOUNDRY_AGENT_TOOLBOX_NAME — Toolbox name (default: hr-agent-tools)
"""

import logging
import os

import httpx
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

load_dotenv(dotenv_path=".env", override=True)

logger = logging.getLogger(__name__)

_API_VERSION = "v1"
_SCOPE = "https://ai.azure.com/.default"
_FEATURE_HEADER = "Toolboxes=V1Preview"


def _headers(credential: DefaultAzureCredential) -> dict:
    token = credential.get_token(_SCOPE).token
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Foundry-Features": _FEATURE_HEADER,
    }


def create_or_update_toolbox(endpoint: str, toolbox_name: str) -> None:
    """Create a new version of the toolbox with web search and code interpreter tools."""
    credential = DefaultAzureCredential()
    base_url = f"{endpoint.rstrip('/')}/toolboxes/{toolbox_name}"

    tools = [
        {"type": "web_search", "name": "web_search"},
        {"type": "code_interpreter", "name": "code_interpreter"},
    ]

    # 1. Create a new version
    logger.info("Creating toolbox '%s' at %s ...", toolbox_name, endpoint)
    resp = httpx.post(
        f"{base_url}/versions",
        params={"api-version": _API_VERSION},
        headers=_headers(credential),
        json={
            "tools": tools,
            "description": "Web search and code interpreter tools for the HR agent.",
        },
        timeout=60,
    )
    if not resp.is_success:
        logger.error("Create version failed (%s): %s", resp.status_code, resp.text)
        resp.raise_for_status()
    version = resp.json().get("version")
    logger.info("Toolbox '%s' version %s created.", toolbox_name, version)

    # 2. Promote this version to default
    resp = httpx.patch(
        base_url,
        params={"api-version": _API_VERSION},
        headers=_headers(credential),
        json={"default_version": version},
        timeout=60,
    )
    resp.raise_for_status()
    logger.info("Toolbox '%s' default version set to %s.", toolbox_name, version)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    endpoint = os.environ["FOUNDRY_PROJECT_ENDPOINT"]
    toolbox_name = os.environ.get("CUSTOM_FOUNDRY_AGENT_TOOLBOX_NAME", "hr-agent-tools")

    create_or_update_toolbox(endpoint, toolbox_name)