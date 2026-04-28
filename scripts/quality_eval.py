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

TOOL_DEFINITIONS = [
    {
        "name": "get_enrollment_deadline_info",
        "type": "function",
        "description": "Return enrollment timeline details for health insurance plans.",
        "parameters": {
            "type": "object",
            "properties": {},
            "title": "get_enrollment_deadline_info_input",
        },
    },
    {
        "name": "get_current_date",
        "type": "function",
        "description": "Return the current date in ISO format.",
        "parameters": {
            "type": "object",
            "properties": {},
            "title": "get_current_date_input",
        },
    },
    {
        "name": "web_search",
        "type": "function",
        "description": (
            "Tool for performing a web search to add context to your responses when user query "
            "needs any factual information, statistics, claims or fresh information that is not in "
            "your training data. Use this tool to retrieve relevant web search results based on a "
            "user's query."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "search_query": {
                    "type": "string",
                    "description": "The search query to send to the web search tool.",
                }
            },
            "required": ["search_query"],
        },
    },
    {
        "name": "knowledge_base_retrieve",
        "type": "function",
        "description": (
            "Use knowledge_base_retrieve to search for information or documents that must be "
            "authoritative and attributable to a source. This knowledge base is always relevant to "
            "the user and any organizations they're affiliated with. You may call this tool with "
            "ambiguous queries to retrieve relevant context before asking the user for further "
            "clarification."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "queries": {
                    "type": "array",
                    "description": "A list of concise, distinct retrieval queries.",
                    "items": {"type": "string"},
                }
            },
            "required": ["queries"],
        },
    },
]

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
augmented_dataset_path = os.path.join(OUTPUT_DIR, f"quality_ground_truth_with_tools_{AGENT_NAME}.jsonl")
with open(DATASET_PATH) as input_file, open(augmented_dataset_path, "w") as output_file:
    for line in input_file:
        item = json.loads(line)
        item["tool_definitions"] = TOOL_DEFINITIONS
        output_file.write(json.dumps(item) + "\n")

dataset = project_client.datasets.upload_file(
    name=f"{AGENT_NAME}-eval-ground-truth",
    version=str(int(time.time())),
    file_path=augmented_dataset_path,
)
print(f"Uploaded dataset: {dataset.id}")

# ---------------------------------------------------------------------------
# 3. Define evaluators (quality + agent behavior)
# ---------------------------------------------------------------------------
testing_criteria = [
    {
        "type": "azure_ai_evaluator",
        "name": "Task Completion",
        "evaluator_name": "builtin.task_completion",
        "data_mapping": {
            "query": "{{item.query}}",
            "response": "{{sample.output_items}}",
        },
        "initialization_parameters": {"deployment_name": model_deployment},
    },
    {
        "type": "azure_ai_evaluator",
        "name": "Tool Call Accuracy",
        "evaluator_name": "builtin.tool_call_accuracy",
        "data_mapping": {
            "query": "{{item.query}}",
            "response": "{{sample.output_items}}",
            "tool_definitions": "{{item.tool_definitions}}",
        },
        "initialization_parameters": {"deployment_name": model_deployment},
    },
    {
        "type": "azure_ai_evaluator",
        "name": "Tool Selection",
        "evaluator_name": "builtin.tool_selection",
        "data_mapping": {
            "query": "{{item.query}}",
            "response": "{{sample.output_items}}",
            "tool_definitions": "{{item.tool_definitions}}",
        },
        "initialization_parameters": {"deployment_name": model_deployment},
    },
    {
        "type": "azure_ai_evaluator",
        "name": "Tool Input Accuracy",
        "evaluator_name": "builtin.tool_input_accuracy",
        "data_mapping": {
            "query": "{{item.query}}",
            "response": "{{sample.output_items}}",
            "tool_definitions": "{{item.tool_definitions}}",
        },
        "initialization_parameters": {"deployment_name": model_deployment},
    },
    {
        "type": "azure_ai_evaluator",
        "name": "Tool Output Utilization",
        "evaluator_name": "builtin.tool_output_utilization",
        "data_mapping": {
            "query": "{{item.query}}",
            "response": "{{sample.output_items}}",
            "tool_definitions": "{{item.tool_definitions}}",
        },
        "initialization_parameters": {"deployment_name": model_deployment},
    },
    {
        "type": "azure_ai_evaluator",
        "name": "Tool Call Success",
        "evaluator_name": "builtin.tool_call_success",
        "data_mapping": {
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
        "name": "Relevance",
        "evaluator_name": "builtin.relevance",
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
    # Task Navigation Efficiency is excluded here because it requires per-item
    # expected action sequences in the input dataset.
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
            "tool_definitions": {"type": "array"},
        },
        "required": ["query", "ground_truth", "tool_definitions"],
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