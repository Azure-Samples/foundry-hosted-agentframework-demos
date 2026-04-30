"""Set up an hourly continuous evaluation for the agent.

Creates an evaluation and schedule that continuously evaluates recent agent traces.

Based on:
https://github.com/Azure/azure-sdk-for-python/blob/main/sdk/ai/azure-ai-projects/samples/evaluations/sample_scheduled_evaluations.py

Usage:
    uv run scripts/continuous_eval.py
"""

import os
from datetime import date

from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import (
    AzureAIDataSourceConfig,
    EvaluationScheduleTask,
    HourlyRecurrenceSchedule,
    RecurrenceTrigger,
    Schedule,
    TestingCriterionAzureAIEvaluator,
)
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

load_dotenv(override=True)

AGENT_NAME = os.environ.get("AGENT_NAME", "hosted-agentframework-agent")
MAX_TRACES = int(os.environ.get("CONTINUOUS_EVAL_MAX_TRACES", "1000"))
SCHEDULE_ID = f"{AGENT_NAME}-continuous-eval"


def main() -> None:
    """Create or update an hourly continuous evaluation schedule for the configured agent."""
    project_endpoint = os.environ["FOUNDRY_PROJECT_ENDPOINT"]
    model_deployment = os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"]
    evaluation_name = f"Continuous Evaluation - {AGENT_NAME} - {date.today().isoformat()}"

    with (
        DefaultAzureCredential() as credential,
        AIProjectClient(endpoint=project_endpoint, credential=credential) as project_client,
        project_client.get_openai_client() as openai_client,
    ):
        print(f"Configuring continuous evaluation for agent: {AGENT_NAME}")

        evaluation = openai_client.evals.create(
            name=evaluation_name,
            data_source_config=AzureAIDataSourceConfig(
                type="azure_ai_source",
                scenario="responses",
            ),
            testing_criteria=[
                TestingCriterionAzureAIEvaluator(
                    type="azure_ai_evaluator",
                    name="Task Adherence",
                    evaluator_name="builtin.task_adherence",
                    data_mapping={
                        "query": "{{item.query}}",
                        "response": "{{item.response}}",
                    },
                    initialization_parameters={
                        "deployment_name": model_deployment,
                    },
                ),
                TestingCriterionAzureAIEvaluator(
                    type="azure_ai_evaluator",
                    name="Intent Resolution",
                    evaluator_name="builtin.intent_resolution",
                    data_mapping={
                        "query": "{{item.query}}",
                        "response": "{{item.response}}",
                    },
                    initialization_parameters={
                        "deployment_name": model_deployment,
                    },
                ),
                TestingCriterionAzureAIEvaluator(
                    type="azure_ai_evaluator",
                    name="Relevance",
                    evaluator_name="builtin.relevance",
                    data_mapping={
                        "query": "{{item.query}}",
                        "response": "{{item.response}}",
                    },
                    initialization_parameters={
                        "deployment_name": model_deployment,
                    },
                ),
                TestingCriterionAzureAIEvaluator(
                    type="azure_ai_evaluator",
                    name="Coherence",
                    evaluator_name="builtin.coherence",
                    data_mapping={
                        "response": "{{item.response}}",
                    },
                    initialization_parameters={
                        "deployment_name": model_deployment,
                    },
                ),
            ],
        )
        print(f"Created evaluation: {evaluation.id}")

        schedule = Schedule(
            display_name=f"Continuous Eval - {AGENT_NAME}",
            enabled=True,
            trigger=RecurrenceTrigger(
                interval=1,
                schedule=HourlyRecurrenceSchedule(),
            ),
            task=EvaluationScheduleTask(
                eval_id=evaluation.id,
                eval_run={
                    "data_source": {
                        "type": "azure_ai_traces",
                        "agent_name": AGENT_NAME,
                        "max_traces": MAX_TRACES,
                    }
                },
            ),
            properties={
                "target_default": "true",
                "target_type": "AzureAITraces",
            },
        )

        schedule_response = project_client.beta.schedules.create_or_update(
            schedule_id=SCHEDULE_ID,
            schedule=schedule,
        )
        print(f"Schedule created: {schedule_response.schedule_id}")
        print("  Trigger: hourly")
        print(f"  Evaluation: {evaluation.id}")
        print(f"  Agent: {AGENT_NAME}")
        print(f"  Max traces: {MAX_TRACES}")


if __name__ == "__main__":
    main()