"""
Stage 2 (retrieve action): Add Foundry IQ — ground answers in an enterprise
knowledge base served by Azure AI Search via the Python SDK retrieve action.

This version uses `KnowledgeBaseRetrievalClient` from the azure-search-documents
SDK, bypassing MCP entirely. Use this as a fallback if the MCP endpoint has issues.

What changes from Stage 1:
    - Query the KB via the retrieve action and inject results into the prompt.
    - The agent uses the KB context to answer grounded questions.

Prerequisites (in addition to Stage 1):
    pip install --pre azure-search-documents
    AZURE_AI_SEARCH_SERVICE_ENDPOINT=https://<your-search>.search.windows.net
    AZURE_AI_SEARCH_KNOWLEDGE_BASE_NAME=zava-company-kb

Run:
    python stage2_foundry_iq_retrieve.py
"""

import asyncio
import logging
import os
from datetime import date
from typing import Annotated

from agent_framework import Agent, tool
from agent_framework.openai import OpenAIChatClient
from azure.identity.aio import DefaultAzureCredential, get_bearer_token_provider
from azure.search.documents.knowledgebases.aio import KnowledgeBaseRetrievalClient
from azure.search.documents.knowledgebases.models import (
    KnowledgeBaseRetrievalRequest,
    KnowledgeRetrievalSemanticIntent,
)
from dotenv import load_dotenv
from pydantic import Field

load_dotenv(override=True)

logging.basicConfig(level=logging.WARNING, format="%(message)s")
logger = logging.getLogger("stage2")
logger.setLevel(logging.INFO)


@tool
def get_enrollment_deadline_info() -> dict:
    """Return enrollment timeline details for health insurance plans."""
    logger.info("[tool] get_enrollment_deadline_info()")
    return {
        "benefits_enrollment_opens": "2026-11-11",
        "benefits_enrollment_closes": "2026-11-30",
    }


class KnowledgeBaseRetrieveTool:
    """Wraps the Azure AI Search retrieve action as an agent tool."""

    def __init__(self, kb_client: KnowledgeBaseRetrievalClient) -> None:
        self._kb_client = kb_client

    async def retrieve(
        self,
        queries: Annotated[
            list[str],
            Field(
                description=(
                    "1 to 3 concise search queries (max ~12 words each). "
                    "Include facets and alternative formulations as separate entries."
                ),
                min_length=1,
                max_length=3,
            ),
        ],
    ) -> str:
        """Search the Zava company knowledge base for HR policies, benefits,
        insurance, and job information.

        Use this tool to find information from internal company documents
        before answering HR-related questions.
        """
        logger.info("[tool] kb.retrieve(queries=%s)", queries)
        request = KnowledgeBaseRetrievalRequest(
            intents=[
                KnowledgeRetrievalSemanticIntent(search=q)
                for q in queries
            ],
        )
        try:
            result = await self._kb_client.retrieve(retrieval_request=request)
        except Exception as e:
            return f"Error: {e}"
        if result.response and result.response[0].content:
            return result.response[0].content[0].text
        return "No results found."


async def main():
    credential = DefaultAzureCredential()
    token_provider = get_bearer_token_provider(
        credential, "https://cognitiveservices.azure.com/.default"
    )

    # --- Chat client (Foundry / Azure OpenAI) -----------------------------
    client = OpenAIChatClient(
        base_url=f"{os.environ['AZURE_OPENAI_ENDPOINT']}/openai/v1/",
        api_key=token_provider,
        model=os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"],
    )

    # --- Foundry IQ knowledge base via retrieve action --------------------
    kb_client = KnowledgeBaseRetrievalClient(
        endpoint=os.environ["AZURE_AI_SEARCH_SERVICE_ENDPOINT"],
        knowledge_base_name=os.environ["AZURE_AI_SEARCH_KNOWLEDGE_BASE_NAME"],
        credential=credential,
    )
    kb_tool = KnowledgeBaseRetrieveTool(kb_client)

    agent = Agent(
        client=client,
        instructions=(
            f"You are an internal HR helper for Zava. Today's date is {date.today().isoformat()}. "
            "Use the knowledge base tool to answer questions about HR policies, benefits, "
            "and company information, and ground all answers in the retrieved context. "
            "Use get_enrollment_deadline_info for benefits enrollment timing. "
            "If you cannot answer from the tools, say so clearly."
        ),
        tools=[kb_tool.retrieve, get_enrollment_deadline_info],
    )

    response = await agent.run(
        "What PerksPlus benefits are there, and when do I need to enroll by?"
    )
    print("\n--- Agent answer ---")
    print(response.text)

    await kb_client.close()
    await credential.close()


if __name__ == "__main__":
    asyncio.run(main())
