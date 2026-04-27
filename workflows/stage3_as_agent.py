"""
Workflow as Agent: Writer → Formatter pipeline exposed as a single agent.

Demonstrates workflow.as_agent() which wraps a multi-step workflow behind
the standard Agent interface.  This is the same pattern used by the hosted
version in workflows/main.py, but run locally with streaming output.

Prerequisites:
    - An Azure OpenAI / Foundry model deployment
    - `azd auth login` (uses AzureDeveloperCliCredential)
    - .env with:
        AZURE_TENANT_ID=<your-tenant-id>
        AZURE_OPENAI_ENDPOINT=https://<your-resource>.openai.azure.com
        AZURE_AI_MODEL_DEPLOYMENT_NAME=gpt-5.2

Run:
    python workflows/stage3_as_agent.py
"""

import asyncio
import os

from agent_framework import Agent, AgentExecutor, WorkflowBuilder
from agent_framework.openai import OpenAIChatClient
from azure.identity.aio import AzureDeveloperCliCredential, get_bearer_token_provider
from dotenv import load_dotenv

load_dotenv(override=True)


async def main():
    """Build a Writer → Formatter workflow and run it as a single agent."""
    credential = AzureDeveloperCliCredential(tenant_id=os.environ["AZURE_TENANT_ID"])
    token_provider = get_bearer_token_provider(
        credential, "https://cognitiveservices.azure.com/.default"
    )

    client = OpenAIChatClient(
        base_url=f"{os.environ['AZURE_OPENAI_ENDPOINT']}/openai/v1/",
        api_key=token_provider,
        model=os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"],
    )

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

    # Build the workflow and convert to a single agent via .as_agent()
    formatter_executor = AgentExecutor(formatter, context_mode="last_agent")
    workflow = (
        WorkflowBuilder(start_executor=writer, output_executors=[formatter_executor])
        .add_edge(writer, formatter_executor)
        .build()
    )
    workflow_agent = workflow.as_agent(name="Content Pipeline")

    # Use the workflow agent with streaming — same API as any other Agent
    prompt = "Write a short post about why open-source AI frameworks matter."
    print(f"Prompt: {prompt}\n")
    print("=" * 60)

    current_author = None
    async for update in workflow_agent.run(prompt, stream=True):
        if update.author_name and update.author_name != current_author:
            if current_author:
                print("\n" + "-" * 40)
            print(f"\n[{update.author_name}]:")
            current_author = update.author_name
        if update.text:
            print(update.text, end="", flush=True)

    print("\n" + "=" * 60)
    await credential.close()


if __name__ == "__main__":
    asyncio.run(main())
