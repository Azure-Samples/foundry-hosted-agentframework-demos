"""
Simple workflow example: UpperCase → ReverseText.

Demonstrates class-based Executors connected with WorkflowBuilder:
    - UpperCase uses ctx.send_message() to forward data to the next step
    - ReverseText uses ctx.yield_output() to emit the final result

No LLM calls — pure data transformation to illustrate workflow mechanics.

Run:
    python workflows/stage1_simple_executors.py
"""

import asyncio

from agent_framework import Executor, WorkflowBuilder, WorkflowContext, handler


class UpperCase(Executor):
    """Convert input text to uppercase and forward to the next executor."""

    def __init__(self) -> None:
        super().__init__(id="upper_case")

    @handler
    async def to_upper_case(self, text: str, ctx: WorkflowContext[str]) -> None:
        """Convert input to uppercase and send to the next node."""
        await ctx.send_message(text.upper())


class ReverseText(Executor):
    """Reverse the string and yield the final workflow output."""

    def __init__(self) -> None:
        super().__init__(id="reverse_text")

    @handler
    async def reverse(self, text: str, ctx: WorkflowContext[str, str]) -> None:
        """Reverse the string and yield as output."""
        await ctx.yield_output(text[::-1])


async def main():
    """Build and run the UpperCase → ReverseText workflow."""
    upper = UpperCase()
    reverse = ReverseText()
    workflow = WorkflowBuilder(start_executor=upper, output_from=[reverse]).add_edge(upper, reverse).build()
    events = await workflow.run("hello world")

    print("Input:  hello world")
    print(f"Output: {events.get_outputs()}")
    print(f"State:  {events.get_final_state()}")


if __name__ == "__main__":
    asyncio.run(main())
