"""List scheduled evaluations for a Foundry project.

Usage:
    uv run scripts/list_schedules.py
"""

import os

from azure.ai.projects import AIProjectClient
from azure.identity import AzureDeveloperCliCredential
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel

load_dotenv(override=True)

console = Console()


def print_registered_schedules(project_client: AIProjectClient, heading: str = "Registered Schedules", mark_schedule_id: str = None) -> None:
    """Print all currently registered project schedules.
    
    Args:
        project_client: AIProjectClient instance
        heading: Header text to print above the schedule list
        mark_schedule_id: Optional schedule ID to mark with ★ in output
    """
    schedules = list(project_client.beta.schedules.list())

    console.print(f"\n[bold cyan]{heading}[/bold cyan]")
    
    if not schedules:
        console.print("  (none)")
        return

    for schedule in schedules:
        task = getattr(schedule, "task", None)
        eval_id = getattr(task, "eval_id", "-") if task else "-"
        marker = "★ " if schedule.schedule_id == mark_schedule_id else "  "
        status = str(schedule.provisioning_status).split(".")[-1]
        enabled = "✓" if schedule.enabled else "✗"

        # Extract agent version from eval_run target if available
        eval_run = getattr(task, "eval_run", None) if task else None
        agent_version = "-"
        if isinstance(eval_run, dict):
            data_source = eval_run.get("data_source", {})
            target = data_source.get("target", {})
            if target.get("type") == "azure_ai_agent":
                agent_version = f"{target.get('name', '?')} v{target.get('version', '?')}"
        
        info = (
            f"[cyan]{marker}{schedule.schedule_id}[/cyan]\n"
            f"  Status: {status} | Enabled: {enabled}\n"
            f"  Name: {schedule.display_name}\n"
            f"  Evaluation: {eval_id}\n"
            f"  Target: {agent_version}"
        )
        console.print(Panel(info, expand=False, border_style="dim cyan"))


def main() -> None:
    """List all schedules in the project."""
    project_endpoint = os.environ["FOUNDRY_PROJECT_ENDPOINT"]
    
    with (
        AzureDeveloperCliCredential(tenant_id=os.environ["AZURE_TENANT_ID"]) as credential,
        AIProjectClient(endpoint=project_endpoint, credential=credential) as project_client,
    ):
        print_registered_schedules(project_client)


if __name__ == "__main__":
    main()
