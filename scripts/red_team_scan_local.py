"""Run a local-preview red-team scan against the agent started with `azd ai agent run`.

This script uses `azure-ai-evaluation[redteam]` and a local callback target that
calls the agent's local Responses endpoint over localhost HTTP.

Hosted-agent cloud red teaming is not supported yet for this sample, so keep this
script as the temporary path for red teaming until the hosted service path works.

Usage:
    1. In another terminal, start the local agent:
       azd ai agent run
    2. Run this script:
       uv run scripts/red_team_scan_local.py
"""

import asyncio
import datetime
import json
import os
import pathlib
import urllib.error
import urllib.request

from azure.ai.evaluation.red_team import AttackStrategy, RedTeam, RiskCategory
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

load_dotenv(override=True)

console = Console()

OUTPUT_DIR = pathlib.Path(__file__).parent / "red_team_output"
OUTPUT_DIR.mkdir(exist_ok=True)

# The local RedTeam SDK still requires a Foundry project reference for evaluator-side services,
# even though scans created this way do not render in the new Foundry project portal UI.
PROJECT_ENDPOINT = os.environ["FOUNDRY_PROJECT_ENDPOINT"]
# Assume the agent is running via 'azd ai agent run' on the default port 8088
LOCAL_AGENT_RESPONSES_URL = "http://localhost:8088/responses"


def render_results_summary(results_file: pathlib.Path) -> None:
    """Render a Rich summary for a completed local red-team run."""
    with results_file.open() as file_handle:
        results = json.load(file_handle)

    result_counts = results.get("result_counts", {})
    console.print(
        Panel.fit(
            (
                f"[bold]Run:[/bold] {results.get('name', 'Unknown')}\n"
                f"[bold]Status:[/bold] {results.get('status', 'Unknown')}\n"
                f"[bold]Total prompts:[/bold] {result_counts.get('total', 0)}\n"
                f"[bold green]Passed:[/bold green] {result_counts.get('passed', 0)}   "
                f"[bold red]Failed:[/bold red] {result_counts.get('failed', 0)}   "
                f"[bold yellow]Errored:[/bold yellow] {result_counts.get('errored', 0)}"
            ),
            title="Local Red-Team Summary",
        )
    )

    risk_category_table = Table(title="Risk Category Summary")
    risk_category_table.add_column("Risk Category")
    risk_category_table.add_column("Passed", justify="right")
    risk_category_table.add_column("Failed", justify="right")

    attack_strategy_table = Table(title="Attack Strategy Summary")
    attack_strategy_table.add_column("Attack Strategy")
    attack_strategy_table.add_column("Passed", justify="right")
    attack_strategy_table.add_column("Failed", justify="right")

    for criterion in results.get("per_testing_criteria_results", []):
        attack_strategy = str(criterion.get("attack_strategy", "-"))
        testing_criteria = str(criterion.get("testing_criteria", ""))
        row = [str(criterion.get("passed", 0)), str(criterion.get("failed", 0))]
        if attack_strategy == "-":
            risk_category_table.add_row(testing_criteria, *row)
        else:
            attack_strategy_table.add_row(attack_strategy, *row)

    console.print(risk_category_table)
    console.print(attack_strategy_table)


def invoke_local_agent(query: str) -> str:
    """Invoke the local agent over localhost HTTP and return its text output."""
    request_body = json.dumps(
        {
            "input": [{"role": "user", "content": query}],
            "store": False,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        LOCAL_AGENT_RESPONSES_URL,
        data=request_body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        return f"Local agent invocation failed: HTTP {exc.code}: {error_body}"
    except OSError as exc:
        return f"Local agent invocation failed: {exc}"

    if body.get("status") == "completed":
        output_text = []
        for item in body.get("output", []):
            for content_item in item.get("content", []):
                text = content_item.get("text")
                if text:
                    output_text.append(text)
        if output_text:
            return "\n".join(output_text).strip()

    error = body.get("error", {})
    error_message = error.get("message") or body.get("status") or "Unknown local invocation failure"
    return f"Local agent invocation failed: {error_message}"


async def run_local_red_team() -> None:
    """Run the local preview red-team scan and save the result file."""
    credential = DefaultAzureCredential()

    red_team = RedTeam(
        azure_ai_project=PROJECT_ENDPOINT,
        credential=credential,
        risk_categories=[
            RiskCategory.Violence,
            RiskCategory.HateUnfairness,
            RiskCategory.Sexual,
            RiskCategory.SelfHarm,
        ],
        num_objectives=1,
    )

    preflight_response = invoke_local_agent("What health plans does Zava offer?")
    if preflight_response.startswith("Local agent invocation failed:"):
        raise RuntimeError(
            "Local agent preflight failed. Start the agent in another terminal with `azd ai agent run` "
            "and make sure the local Responses endpoint is healthy before running this script.\n"
            f"Details: {preflight_response}"
        )

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = OUTPUT_DIR / f"local_redteam_output_{timestamp}.json"

    await red_team.scan(
        scan_name=f"Local red team {timestamp}",
        output_path=str(output_path),
        attack_strategies=[
            AttackStrategy.Baseline,
            AttackStrategy.Url,
            AttackStrategy.Tense,
        ],
        target=invoke_local_agent,
    )

    console.print(f"Local red-team results saved to [bold]{output_path}[/bold]")

    results_file = output_path / "results.json"
    if results_file.exists():
        render_results_summary(results_file)
    else:
        console.print(f"[yellow]Expected results file not found:[/yellow] {results_file}")


if __name__ == "__main__":
    asyncio.run(run_local_red_team())