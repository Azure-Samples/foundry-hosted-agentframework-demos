"""
Call the deployed hosted agent via its Responses API endpoint.

Usage:
    python call_deployed_agent.py "What PerksPlus benefits are there?"

Requires environment variables:
    FOUNDRY_PROJECT_ENDPOINT — Foundry project endpoint URL
"""

import argparse
import os

import httpx
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

load_dotenv(dotenv_path=".env", override=True)

AGENT_NAME = "hosted-agentframework-agent"
PROJECT_ENDPOINT = os.environ["FOUNDRY_PROJECT_ENDPOINT"]
RESPONSES_URL = f"{PROJECT_ENDPOINT.rstrip('/')}/agents/{AGENT_NAME}/endpoint/protocols/openai/responses"
API_VERSION = "v1"
SCOPE = "https://ai.azure.com/.default"


def call_agent(query: str) -> None:
    credential = DefaultAzureCredential()
    token = credential.get_token(SCOPE).token

    response = httpx.post(
        RESPONSES_URL,
        params={"api-version": API_VERSION},
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json={
            "input": query,
            "store": True,
        },
        timeout=120.0,
    )
    if not response.is_success:
        print(f"Error {response.status_code}: {response.text}")
        response.raise_for_status()

    data = response.json()
    for item in data.get("output", []):
        if item.get("type") == "message":
            for content in item.get("content", []):
                if content.get("type") == "output_text":
                    print(content["text"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Call the deployed hosted agent.")
    parser.add_argument("query", help="The question to ask the agent.")
    args = parser.parse_args()

    call_agent(args.query)
