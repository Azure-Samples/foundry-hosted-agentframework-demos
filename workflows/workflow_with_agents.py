"""
Workflow Stage 1: Writer → Reviewer workflow using a Foundry-hosted model.

Two AI agents in a chain:
    writer → formatter

The writer drafts a short article, and the formatter styles it with Markdown and emojis.
Agents are passed directly as executors to WorkflowBuilder (no need
for explicit AgentExecutor wrapping).

Prerequisites:
    - An Azure OpenAI / Foundry model deployment
    - `az login` (uses DefaultAzureCredential)
    - .env with:
        AZURE_OPENAI_ENDPOINT=https://<your-resource>.openai.azure.com
        AZURE_AI_MODEL_DEPLOYMENT_NAME=gpt-5.2

Run:
    python workflows/stage1_foundry_model.py
"""

import asyncio
import os

from agent_framework import Agent, AgentExecutor, WorkflowBuilder
from agent_framework.openai import OpenAIChatClient
from azure.identity.aio import DefaultAzureCredential, get_bearer_token_provider
from dotenv import load_dotenv

load_dotenv(override=True)

async def main():
    """Run a writer → reviewer workflow against a Foundry-hosted model."""
    credential = DefaultAzureCredential()
    token_provider = get_bearer_token_provider(
        credential, "https://cognitiveservices.azure.com/.default"
    )

    client = OpenAIChatClient(
        base_url=f"{os.environ['AZURE_OPENAI_ENDPOINT']}/openai/v1/",
        api_key=token_provider,
        model=os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"],
    )

    # Create AI agents — passed directly as executors to WorkflowBuilder
    writer = Agent(
        client=client,
        name="Writer",
        instructions=(
            "You are a concise content writer. "
            "Write a clear, engaging short article (2-3 paragraphs) based on the user's topic. "
            "Focus on accuracy and readability."
        ),
    )

    formatter = Agent(
        client=client,
        name="Formatter",
        instructions=(
            "You are an expert content formatter. "
            "Take the provided text and format it with Markdown (bold, headers, lists) "
            "and relevant emojis to make it visually engaging. "
            "Preserve the original meaning and content."
        ),
    )

    # Build the workflow: Writer → Formatter (only show Formatter output)
    # Use AgentExecutor with context_mode="last_agent" so the formatter
    # only sees the writer's output, not the original user prompt.
    writer_executor = AgentExecutor(writer, context_mode="last_agent")
    formatter_executor = AgentExecutor(formatter, context_mode="last_agent")
    workflow = (
        WorkflowBuilder(start_executor=writer_executor, output_executors=[formatter_executor])
        .add_edge(writer_executor, formatter_executor)
        .build()
    )

    prompt = 'Write a 2-sentence LinkedIn post: "Why your AI pilot looks good but fails in production."'
    print(f"\nPrompt: {prompt}\n")
    events = await workflow.run(prompt)

    for output in events.get_outputs():
        print("Output:")
        print(output)

    await credential.close()


if __name__ == "__main__":
    asyncio.run(main())
