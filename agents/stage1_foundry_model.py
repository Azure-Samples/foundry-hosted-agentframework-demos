"""
Stage 1: Same agent, but using a model deployed in Microsoft Foundry
(Azure OpenAI) instead of a local SLM.

Only the chat client changes — the Agent + tool code is identical to Stage 0.

Prerequisites:
    - An Azure OpenAI / Foundry model deployment
    - `az login` (uses DefaultAzureCredential)
    - .env with:
        AZURE_OPENAI_ENDPOINT=https://<your-resource>.openai.azure.com
        AZURE_AI_MODEL_DEPLOYMENT_NAME=gpt-5.2

Run:
    python agents/stage1_foundry_model.py
"""

import asyncio
import logging
import os
from datetime import date

from agent_framework import Agent, tool
from agent_framework.openai import OpenAIChatClient
from azure.identity.aio import DefaultAzureCredential, get_bearer_token_provider
from dotenv import load_dotenv
from rich.console import Console
from rich.logging import RichHandler
from rich.markdown import Markdown

load_dotenv(override=True)

console = Console()
logger = logging.getLogger("stage1")


@tool
def get_enrollment_deadline_info() -> dict:
    """Return enrollment timeline details for health insurance plans."""
    logger.info("[tool] get_enrollment_deadline_info()")
    return {
        "enrollment_opens": "2026-11-11",
        "enrollment_closes": "2026-11-30",
    }


async def main():
    credential = DefaultAzureCredential()
    token_provider = get_bearer_token_provider(
        credential, "https://cognitiveservices.azure.com/.default"
    )

    client = OpenAIChatClient(
        base_url=f"{os.environ['AZURE_OPENAI_ENDPOINT']}/openai/v1/",
        api_key=token_provider,
        model=os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"],
    )

    agent = Agent(
        client=client,
        instructions=(
            f"You are an internal HR helper. Today's date is {date.today().isoformat()}. "
            "Use the available tools to answer questions about benefits enrollment timing. "
            "Always ground your answers in tool results."
        ),
        tools=[get_enrollment_deadline_info],
    )

    response = await agent.run(
        "When does benefits enrollment open?"
    )
    console.print("\n[bold]Agent answer:[/bold]")
    console.print(Markdown(response.text))

    await credential.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s", handlers=[RichHandler(console=console, show_path=False)])
    logging.getLogger("azure.identity").setLevel(logging.WARNING)
    logging.getLogger("azure.core").setLevel(logging.WARNING)
    asyncio.run(main())
