"""Run an AI Red Teaming scan against the agent.

Based on:
https://learn.microsoft.com/azure/foundry/how-to/develop/run-ai-red-teaming-cloud?tabs=python

Usage:
    uv run scripts/red_team_scan.py
"""

import json
import os
import time

from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import (
    AgentTaxonomyInput,
    AttackStrategy,
    AzureAIAgentTarget,
    EvaluationTaxonomy,
    RiskCategory,
)
from azure.identity import AzureDeveloperCliCredential
from dotenv import load_dotenv

load_dotenv(override=True)

AGENT_NAME = os.environ.get("AGENT_NAME", "hosted-agentframework-agent")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "red_team_output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

project_endpoint = os.environ["FOUNDRY_PROJECT_ENDPOINT"]
model_deployment = os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"]

credential = AzureDeveloperCliCredential(tenant_id=os.environ["AZURE_TENANT_ID"])
project_client = AIProjectClient(endpoint=project_endpoint, credential=credential)

# ---------------------------------------------------------------------------
# 1. Look up the latest agent version
# ---------------------------------------------------------------------------
agent = project_client.agents.get(agent_name=AGENT_NAME)
agent_version = agent.versions["latest"]
print(f"Agent: {agent_version.name}  version: {agent_version.version}")

target = AzureAIAgentTarget(
    name=AGENT_NAME,
    version=str(agent_version.version),
)

# ---------------------------------------------------------------------------
# 2. Create the red team (eval group) with built-in safety evaluators
# ---------------------------------------------------------------------------
openai_client = project_client.get_openai_client()

red_team = openai_client.evals.create(
    name=f"Red Team - {AGENT_NAME}",
    data_source_config={"type": "azure_ai_source", "scenario": "red_team"},
    testing_criteria=[
        {
            "type": "azure_ai_evaluator",
            "name": "Task Adherence",
            "evaluator_name": "builtin.task_adherence",
            "evaluator_version": "1",
            "initialization_parameters": {"deployment_name": model_deployment},
        },
        {
            "type": "azure_ai_evaluator",
            "name": "Sensitive Data Leakage",
            "evaluator_name": "builtin.sensitive_data_leakage",
            "evaluator_version": "1",
        },
        {
            "type": "azure_ai_evaluator",
            "name": "Self-Harm",
            "evaluator_name": "builtin.self_harm",
            "evaluator_version": "1",
        },
        {
            "type": "azure_ai_evaluator",
            "name": "Sexual Content",
            "evaluator_name": "builtin.sexual",
            "evaluator_version": "1",
        },
        {
            "type": "azure_ai_evaluator",
            "name": "Violent Content",
            "evaluator_name": "builtin.violence",
            "evaluator_version": "1",
        },
    ],
)
print(f"Created red team: {red_team.id}")

# ---------------------------------------------------------------------------
# 3. Create an evaluation taxonomy for prohibited actions
# ---------------------------------------------------------------------------
taxonomy = project_client.beta.evaluation_taxonomies.create(
    name=AGENT_NAME,
    body=EvaluationTaxonomy(
        description=f"Taxonomy for red teaming {AGENT_NAME}",
        taxonomy_input=AgentTaxonomyInput(
            risk_categories=[RiskCategory.PROHIBITED_ACTIONS],
            target=target,
        ),
    ),
)
taxonomy_file_id = taxonomy.id
print(f"Created taxonomy: {taxonomy_file_id}")

# ---------------------------------------------------------------------------
# 4. Create a red teaming run with attack strategies
# ---------------------------------------------------------------------------
eval_run = openai_client.evals.runs.create(
    eval_id=red_team.id,
    name=f"Red Team Run - {AGENT_NAME}",
    data_source={
        "type": "azure_ai_red_team",
        "item_generation_params": {
            "type": "red_team_taxonomy",
            "attack_strategies": [
                AttackStrategy.BASELINE,
                AttackStrategy.URL,
                AttackStrategy.TENSE,
            ],
            "num_turns": 5,
            "source": {"type": "file_id", "id": taxonomy_file_id},
        },
        "target": target.as_dict(),
    },
)
print(f"Created run: {eval_run.id}  status: {eval_run.status}")

# ---------------------------------------------------------------------------
# 5. Poll until the run completes
# ---------------------------------------------------------------------------
print("Polling for completion", end="", flush=True)
while True:
    run = openai_client.evals.runs.retrieve(run_id=eval_run.id, eval_id=red_team.id)
    if run.status in ("completed", "failed", "canceled"):
        break
    print(".", end="", flush=True)
    time.sleep(10)

print(f"\nRun finished — status: {run.status}")
if hasattr(run, "report_url") and run.report_url:
    print(f"Report URL: {run.report_url}")

# ---------------------------------------------------------------------------
# 6. Save output items
# ---------------------------------------------------------------------------
items = list(openai_client.evals.runs.output_items.list(run_id=run.id, eval_id=red_team.id))

output_path = os.path.join(OUTPUT_DIR, f"redteam_output_{AGENT_NAME}.json")
with open(output_path, "w") as f:
    json.dump([item.to_dict() if hasattr(item, "to_dict") else str(item) for item in items], f, indent=2)

print(f"Output items ({len(items)}) saved to {output_path}")
