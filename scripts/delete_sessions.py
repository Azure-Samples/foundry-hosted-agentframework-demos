"""Delete hosted agent sessions for a Foundry project.

Deletes active sessions to free up the per-subscription, per-region concurrent
session quota. By default it processes every agent in the project; pass an agent
name to limit it to one.

Note: the concurrent session quota is enforced per subscription and region
across ALL projects, and deletion is asynchronous (sessions flip to DELETED
immediately but the sandbox takes a short while to deprovision), so freed
capacity may take a moment to reflect in the quota.

Usage:
    uv run scripts/delete_sessions.py            # all agents in the project
    uv run scripts/delete_sessions.py <agent>    # a single agent
"""

import os
import sys

from azure.ai.projects import AIProjectClient
from azure.identity import AzureDeveloperCliCredential
from dotenv import load_dotenv
from rich.console import Console

load_dotenv(override=True)

console = Console()


def delete_agent_sessions(project_client: AIProjectClient, agent_name: str) -> int:
    """Delete all active sessions for a single agent. Returns the count deleted."""
    console.print(f"[bold cyan]Agent:[/bold cyan] {agent_name}")

    sessions = list(project_client.beta.agents.list_sessions(agent_name=agent_name))
    # list_sessions also returns already-deleted sessions; filter them out.
    active = [s for s in sessions if str(getattr(s, "status", "")).split(".")[-1] != "DELETED"]
    if not active:
        console.print("  (no active sessions)")
        return 0

    console.print(f"  Found [bold]{len(active)}[/bold] active session(s). Deleting...")

    deleted = 0
    for item in active:
        session_id = item.agent_session_id
        status = getattr(item, "status", "-")
        console.print(f"    Deleting {session_id} (status: {status})")

        # The SDK requires the isolation_key keyword, but the server only
        # enforces it when the agent endpoint uses Header isolation. With the
        # default Entra isolation, the delete is scoped to the calling
        # identity, so an empty key is accepted.
        project_client.beta.agents.delete_session(
            agent_name=agent_name,
            session_id=session_id,
            isolation_key="",
        )
        deleted += 1

    return deleted


def main() -> None:
    """Delete sessions for one agent (if named) or all agents in the project."""
    project_endpoint = os.environ["FOUNDRY_PROJECT_ENDPOINT"]
    single_agent = sys.argv[1] if len(sys.argv) > 1 else None

    with (
        AzureDeveloperCliCredential(tenant_id=os.environ["AZURE_TENANT_ID"]) as credential,
        AIProjectClient(endpoint=project_endpoint, credential=credential) as project_client,
    ):
        if single_agent:
            agent_names = [single_agent]
        else:
            agent_names = [getattr(a, "name", None) or a.agent_name for a in project_client.agents.list()]

        total = sum(delete_agent_sessions(project_client, name) for name in agent_names)
        console.print(f"[bold green]Deleted {total} session(s) total.[/bold green]")


if __name__ == "__main__":
    main()
