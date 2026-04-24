"""Set up a daily scheduled evaluation for the agent.

Creates an evaluation + eval run definition, then schedules it to run daily at 9 AM UTC.

Based on:
https://github.com/Azure/azure-sdk-for-python/blob/main/sdk/ai/azure-ai-projects/samples/evaluations/sample_scheduled_evaluations.py

Usage:
    uv run scripts/scheduled_eval.py
"""

import json
import os
import time

from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import (
    DailyRecurrenceSchedule,
    EvaluationScheduleTask,
    RecurrenceTrigger,
    Schedule,
)
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

load_dotenv(override=True)

AGENT_NAME = os.environ.get("AGENT_NAME", "hosted-agentframework-agent")
SCHEDULE_ID = f"{AGENT_NAME}-daily-quality-eval"
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "eval_output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

project_endpoint = os.environ["FOUNDRY_PROJECT_ENDPOINT"]
model_deployment = os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"]

credential = DefaultAzureCredential()
project_client = AIProjectClient(endpoint=project_endpoint, credential=credential)
openai_client = project_client.get_openai_client()

# ---------------------------------------------------------------------------
# 1. Look up the latest agent version
# ---------------------------------------------------------------------------
agent = project_client.agents.get(agent_name=AGENT_NAME)
agent_version = agent.versions["latest"]
print(f"Agent: {agent_version.name}  version: {agent_version.version}")

# ---------------------------------------------------------------------------
# 2. Upload test dataset
# ---------------------------------------------------------------------------
test_queries = [
    {"query": "What health plans does Zava offer?"},
    {"query": "Who is the CEO of Zava?"},
    {"query": "What is Zava's parental leave policy?"},
    {"query": "What are the best exercises to reduce lower back pain?"},
    {"query": "How do I file my taxes as a freelancer?"},
    {"query": "Can you recommend a good therapist in London?"},
    {"query": "What is the capital of France?"},
    {"query": "Explain how to set up a Kubernetes cluster."},
    {"query": "What medications help with seasonal allergies?"},
    {"query": "Write me a Python script to sort a list."},
]

dataset_path = os.path.join(OUTPUT_DIR, "test_queries.jsonl")
with open(dataset_path, "w") as f:
    for item in test_queries:
        f.write(json.dumps(item) + "\n")

dataset = project_client.datasets.upload_file(
    name=f"{AGENT_NAME}-scheduled-eval-queries",
    version=str(int(time.time())),
    file_path=dataset_path,
)
print(f"Uploaded dataset: {dataset.id}")

# ---------------------------------------------------------------------------
# 3. Create evaluation with testing criteria
# ---------------------------------------------------------------------------
testing_criteria = [
    {
        "type": "azure_ai_evaluator",
        "name": "Task Adherence",
        "evaluator_name": "builtin.task_adherence",
        "data_mapping": {
            "query": "{{item.query}}",
            "response": "{{sample.output_items}}",
        },
        "initialization_parameters": {"deployment_name": model_deployment},
    },
    {
        "type": "azure_ai_evaluator",
        "name": "Intent Resolution",
        "evaluator_name": "builtin.intent_resolution",
        "data_mapping": {
            "query": "{{item.query}}",
            "response": "{{sample.output_items}}",
        },
        "initialization_parameters": {"deployment_name": model_deployment},
    },
    {
        "type": "azure_ai_evaluator",
        "name": "Groundedness",
        "evaluator_name": "builtin.groundedness",
        "data_mapping": {
            "query": "{{item.query}}",
            "response": "{{sample.output_items}}",
        },
        "initialization_parameters": {"deployment_name": model_deployment},
    },
    {
        "type": "azure_ai_evaluator",
        "name": "Relevance",
        "evaluator_name": "builtin.relevance",
        "data_mapping": {
            "query": "{{item.query}}",
            "response": "{{sample.output_items}}",
        },
        "initialization_parameters": {"deployment_name": model_deployment},
    },
]

data_source_config = {
    "type": "custom",
    "item_schema": {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
        },
        "required": ["query"],
    },
    "include_sample_schema": True,
}

evaluation = openai_client.evals.create(
    name=f"Scheduled Quality Evaluation - {AGENT_NAME}",
    data_source_config=data_source_config,
    testing_criteria=testing_criteria,
)
print(f"Created evaluation: {evaluation.id}")

# ---------------------------------------------------------------------------
# 4. Define the eval run (not executed yet — used by the schedule)
# ---------------------------------------------------------------------------
eval_run_definition = {
    "eval_id": evaluation.id,
    "name": f"Scheduled Quality Eval Run - {AGENT_NAME}",
    "data_source": {
        "type": "azure_ai_target_completions",
        "source": {
            "type": "file_id",
            "id": dataset.id,
        },
        "input_messages": {
            "type": "template",
            "template": [
                {
                    "type": "message",
                    "role": "user",
                    "content": {"type": "input_text", "text": "{{item.query}}"},
                }
            ],
        },
        "target": {
            "type": "azure_ai_agent",
            "name": AGENT_NAME,
            "version": str(agent_version.version),
        },
    },
}

# ---------------------------------------------------------------------------
# 5. Create the daily schedule (9 AM UTC)
# ---------------------------------------------------------------------------
schedule = Schedule(
    display_name=f"Daily Quality Eval - {AGENT_NAME}",
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
