"""
Call the deployed hosted agent via the azure-ai-projects SDK.

Usage:
    python call_deployed_agent.py "What PerksPlus benefits are there?"

Requires environment variables:
    FOUNDRY_PROJECT_ENDPOINT — Foundry project endpoint URL
"""

import argparse
import os

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(dotenv_path=".env", override=True)

AGENT_NAME = "hosted-agentframework-agent"
PROJECT_ENDPOINT = os.environ["FOUNDRY_PROJECT_ENDPOINT"]


def call_agent(query: str) -> None:
    """Call the deployed hosted agent and print the response."""
    credential = DefaultAzureCredential()
    project = AIProjectClient(
        endpoint=PROJECT_ENDPOINT,
        credential=credential,
    )
    # get_openai_client doesn't support agent_name yet in SDK 2.1.0,
    # so we construct the OpenAI client with the agent-specific base URL.
    base_url = f"{PROJECT_ENDPOINT.rstrip('/')}/agents/{AGENT_NAME}/endpoint/protocols/openai"
    openai_client = project.get_openai_client(
        base_url=base_url,
        default_query={"api-version": "v1"},
    )
    response = openai_client.responses.create(input=query)
    print(response.output_text)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Call the deployed hosted agent.")
    parser.add_argument("query", help="The question to ask the agent.")
    args = parser.parse_args()

    call_agent(args.query)
