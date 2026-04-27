"""Set up a daily scheduled red-teaming run for the agent.

Creates a red-team evaluation + taxonomy, then schedules the run daily at 9 AM UTC.

Based on:
https://github.com/Azure/azure-sdk-for-python/blob/main/sdk/ai/azure-ai-projects/samples/evaluations/sample_scheduled_evaluations.py

Usage:
    uv run scripts/scheduled_red_team.py
"""

import os

from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import (
    AgentTaxonomyInput,
    AzureAIAgentTarget,
    DailyRecurrenceSchedule,
    EvaluationScheduleTask,
    EvaluationTaxonomy,
    RecurrenceTrigger,
    RiskCategory,
    Schedule,
)
from azure.identity import AzureDeveloperCliCredential
from dotenv import load_dotenv

load_dotenv(override=True)

AGENT_NAME = os.environ.get("AGENT_NAME", "hosted-agentframework-agent")
SCHEDULE_ID = f"{AGENT_NAME}-daily-red-team"

project_endpoint = os.environ["FOUNDRY_PROJECT_ENDPOINT"]
model_deployment = os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"]

credential = AzureDeveloperCliCredential(tenant_id=os.environ["AZURE_TENANT_ID"])
project_client = AIProjectClient(endpoint=project_endpoint, credential=credential)
openai_client = project_client.get_openai_client()

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
# 2. Create the red-team evaluation with safety evaluators
# ---------------------------------------------------------------------------
testing_criteria = [
    {
        "type": "azure_ai_evaluator",
        "name": "Prohibited Actions",
        "evaluator_name": "builtin.prohibited_actions",
        "evaluator_version": "1",
    },
    {
        "type": "azure_ai_evaluator",
        "name": "Task Adherence",
        "evaluator_name": "builtin.task_adherence",
        "evaluator_version": "1",
    },
    {
        "type": "azure_ai_evaluator",
        "name": "Sensitive Data Leakage",
        "evaluator_name": "builtin.sensitive_data_leakage",
        "evaluator_version": "1",
    },
    {
        "type": "azure_ai_evaluator",
        "name": "Self Harm",
        "evaluator_name": "builtin.self_harm",
        "evaluator_version": "1",
    },
    {
        "type": "azure_ai_evaluator",
        "name": "Violence",
        "evaluator_name": "builtin.violence",
        "evaluator_version": "1",
    },
    {
        "type": "azure_ai_evaluator",
        "name": "Sexual",
        "evaluator_name": "builtin.sexual",
        "evaluator_version": "1",
    },
    {
        "type": "azure_ai_evaluator",
        "name": "Hate Unfairness",
        "evaluator_name": "builtin.hate_unfairness",
        "evaluator_version": "1",
    },
]

evaluation = openai_client.evals.create(
    name=f"Scheduled Red Team - {AGENT_NAME}",
    data_source_config={"type": "azure_ai_source", "scenario": "red_team"},
    testing_criteria=testing_criteria,
)
print(f"Created evaluation: {evaluation.id}")

# ---------------------------------------------------------------------------
# 3. Create an evaluation taxonomy for prohibited actions
# ---------------------------------------------------------------------------
taxonomy = project_client.beta.evaluation_taxonomies.create(
    name=AGENT_NAME,
    body=EvaluationTaxonomy(
        description=f"Taxonomy for scheduled red teaming of {AGENT_NAME}",
        taxonomy_input=AgentTaxonomyInput(
            risk_categories=[RiskCategory.PROHIBITED_ACTIONS],
            target=target,
        ),
    ),
)
print(f"Created taxonomy: {taxonomy.id}")

# ---------------------------------------------------------------------------
# 4. Define the eval run (not executed yet — used by the schedule)
# ---------------------------------------------------------------------------
eval_run_definition = {
    "eval_id": evaluation.id,
    "name": f"Scheduled Red Team Run - {AGENT_NAME}",
    "data_source": {
        "type": "azure_ai_red_team",
        "item_generation_params": {
            "type": "red_team_taxonomy",
            "attack_strategies": ["Flip", "Base64"],
            "num_turns": 5,
            "source": {"type": "file_id", "id": taxonomy.id},
        },
        "target": target.as_dict(),
    },
}

# ---------------------------------------------------------------------------
# 5. Create the daily schedule (9 AM UTC)
# ---------------------------------------------------------------------------
schedule = Schedule(
    display_name=f"Daily Red Team - {AGENT_NAME}",
    enabled=True,
    trigger=RecurrenceTrigger(
        interval=1,
        schedule=DailyRecurrenceSchedule(hours=[9]),
    ),
    task=EvaluationScheduleTask(
        eval_id=evaluation.id,
        eval_run=eval_run_definition,
    ),
)

schedule_response = project_client.beta.schedules.create_or_update(
    schedule_id=SCHEDULE_ID,
    schedule=schedule,
)
print(f"Schedule created: {schedule_response.schedule_id}")
print("  Trigger: daily at 9 AM UTC")
print(f"  Evaluation: {evaluation.id}")
print(f"  Agent: {AGENT_NAME} v{agent_version.version}")
