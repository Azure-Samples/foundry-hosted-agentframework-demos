"""Run a quality evaluation against the agent

Evaluates in-scope knowledge base queries against ground truth answers.

Based on:
https://learn.microsoft.com/en-us/azure/foundry/observability/how-to/evaluate-agent

Usage:
    uv run scripts/quality_eval.py
"""

import json
import os
import time

from azure.ai.projects import AIProjectClient
from azure.identity import AzureDeveloperCliCredential
from dotenv import load_dotenv

load_dotenv(override=True)

AGENT_NAME = os.environ.get("AGENT_NAME", "hosted-agentframework-agent")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "eval_output")
DATASET_PATH = os.path.join(os.path.dirname(__file__), "eval_data", "quality_ground_truth.jsonl")
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

# ---------------------------------------------------------------------------
# 2. Upload a ground truth test dataset (JSONL)
# ---------------------------------------------------------------------------
dataset = project_client.datasets.upload_file(
    name=f"{AGENT_NAME}-eval-ground-truth",
    version=str(int(time.time())),
    file_path=DATASET_PATH,
)
print(f"Uploaded dataset: {dataset.id}")

# ---------------------------------------------------------------------------
# 3. Define evaluators (quality + agent behavior)
# ---------------------------------------------------------------------------
testing_criteria = [
    {
        "type": "azure_ai_evaluator",
        "name": "Tool Call Accuracy",
        "evaluator_name": "builtin.tool_call_accuracy",
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
        "name": "Response Completeness",
        "evaluator_name": "builtin.response_completeness",
        "data_mapping": {
            "ground_truth": "{{item.ground_truth}}",
            "response": "{{sample.output_text}}",
        },
        "initialization_parameters": {"deployment_name": model_deployment},
    },
    # RAG specific:
    {
        "type": "azure_ai_evaluator",
        "name": "Groundedness",
        "evaluator_name": "builtin.groundedness",
        "data_mapping": {
            "query": "{{item.query}}",
            "response": "{{sample.output_items}}",
        },
        "initialization_parameters": {"deployment_name": model_deployment},
    }
]

# ---------------------------------------------------------------------------
# 4. Create the evaluation (container for runs)
# ---------------------------------------------------------------------------
openai_client = project_client.get_openai_client()

data_source_config = {
    "type": "custom",
    "item_schema": {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "ground_truth": {"type": "string"},
        },
        "required": ["query", "ground_truth"],
    },
    "include_sample_schema": True,
}

evaluation = openai_client.evals.create(
    name=f"Quality Evaluation - {AGENT_NAME}",
    data_source_config=data_source_config,
    testing_criteria=testing_criteria,
)
print(f"Created evaluation: {evaluation.id}")

# ---------------------------------------------------------------------------
# 5. Create a run targeting the agent
# ---------------------------------------------------------------------------
eval_run = openai_client.evals.runs.create(
    eval_id=evaluation.id,
    name=f"Quality Eval Run - {AGENT_NAME}",
    data_source={
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
)
print(f"Evaluation run started: {eval_run.id}  status: {eval_run.status}")

# ---------------------------------------------------------------------------
# 6. Poll until the run completes
# ---------------------------------------------------------------------------
print("Polling for completion", end="", flush=True)
while True:
    run = openai_client.evals.runs.retrieve(run_id=eval_run.id, eval_id=evaluation.id)
    if run.status in ("completed", "failed", "canceled"):
        break
    print(".", end="", flush=True)
    time.sleep(10)

print(f"\nRun finished — status: {run.status}")
if hasattr(run, "report_url") and run.report_url:
    print(f"Report URL: {run.report_url}")

# ---------------------------------------------------------------------------
# 7. Save output items
# ---------------------------------------------------------------------------
items = list(openai_client.evals.runs.output_items.list(run_id=run.id, eval_id=evaluation.id))

output_path = os.path.join(OUTPUT_DIR, f"quality_eval_output_{AGENT_NAME}.json")
with open(output_path, "w") as f:
    json.dump(
        [item.to_dict() if hasattr(item, "to_dict") else str(item) for item in items],
        f,
        indent=2,
    )

print(f"Output items ({len(items)}) saved to {output_path}")
