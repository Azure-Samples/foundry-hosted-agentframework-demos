"""
Stage 0: Fully local agent using a small language model via Ollama.

No cloud, no account required. Demonstrates the core agent loop:
    user -> model -> tool call -> tool result -> model -> final answer

Prerequisites:
    1. Install Ollama: https://ollama.com/download
    2. Pull a small model that supports tool calling, e.g.:
         ollama pull llama3.2
    3. Make sure Ollama is running (it serves an OpenAI-compatible API
       at http://localhost:11434/v1 by default).

Run:
    python agents/stage0_local_model.py
"""

import asyncio
import logging
from datetime import date

from agent_framework import Agent, tool
from agent_framework.openai import OpenAIChatClient
from rich.console import Console
from rich.logging import RichHandler
from rich.markdown import Markdown

console = Console()
logger = logging.getLogger("stage0")


@tool
def get_enrollment_deadline_info() -> dict:
    """Return enrollment timeline details for health insurance plans."""
    logger.info("[tool] get_enrollment_deadline_info()")
    return {
        "enrollment_opens": "2026-11-11",
        "enrollment_closes": "2026-11-30",
    }


# Ollama exposes an OpenAI-compatible endpoint; no API key needed.
client = OpenAIChatClient(
    base_url="http://localhost:11434/v1/",
    api_key="no-key-needed",  # any non-empty string
    model="qwen3.5:4b",
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


async def main():
    response = await agent.run(
        "When does benefits enrollment open?"
    )
    console.print("\n[bold]Agent answer:[/bold]")
    console.print(Markdown(response.text))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s", handlers=[RichHandler(console=console, show_path=False)])
    asyncio.run(main())
