"""Create an Azure Monitor alert rule for agent evaluation pass rate.

Uses the Scheduled Query Rules REST API (2021-08-01) to create a log alert
that fires when the evaluation pass rate drops below a threshold.

The alert queries Application Insights custom events emitted by the Foundry
evaluation pipeline (gen_ai.evaluation.result) and triggers when the pass rate
falls at or below the configured threshold.

Reference:
https://learn.microsoft.com/rest/api/monitor/scheduled-query-rules/create-or-update?view=rest-monitor-2021-08-01

Usage:
    uv run scripts/continuous_eval_alert.py
    uv run scripts/continuous_eval_alert.py --email team@example.com
"""

import argparse
import os

import requests
from azure.identity import AzureDeveloperCliCredential
from dotenv import load_dotenv

load_dotenv(override=True)

AGENT_NAME = os.environ.get("AGENT_NAME", "hosted-agentframework-agent")
RULE_NAME = f"{AGENT_NAME}-eval-pass-rate-alert"

# Azure resource identifiers
SUBSCRIPTION_ID = os.environ["AZURE_SUBSCRIPTION_ID"]
RESOURCE_GROUP = os.environ["AZURE_RESOURCE_GROUP"]
APPINSIGHTS_RESOURCE_ID = os.environ["APPLICATIONINSIGHTS_RESOURCE_ID"]
AI_PROJECT_ID = os.environ["AZURE_AI_PROJECT_ID"]
LOCATION = os.environ.get("AZURE_LOCATION", "eastus")

# Alert configuration
ACTION_GROUP_NAME = f"{AGENT_NAME}-eval-alert-action-group"

PASS_RATE_THRESHOLD = 0.99
WINDOW_SIZE = "PT1H"
ENABLED = True

QUERY = f"""customEvents
| where name == "gen_ai.evaluation.result"
| extend evaluation_name = tostring(customDimensions["gen_ai.evaluation.name"])
| extend agent_name = tostring(customDimensions["gen_ai.agent.name"])
| extend evaluation_score_label = tostring(customDimensions["gen_ai.evaluation.score.label"])
| extend internal_properties = todynamic(tostring(customDimensions["internal_properties"]))
| extend agent_version = tostring(internal_properties["gen_ai.agent.version"])
| extend azure_ai_project_id = tostring(internal_properties["gen_ai.azure_ai_project.id"])
| extend evaluation_type = tostring(internal_properties["gen_ai.evaluation.azure_ai_type"])
| extend scheduled_type = tostring(internal_properties["gen_ai.evaluation.azure_ai_scheduled"])
| where azure_ai_project_id == "{AI_PROJECT_ID}" and agent_name == "{AGENT_NAME}"
| summarize
    PassRate = todouble(countif(evaluation_score_label == "pass")) / count()
    by
    azure_ai_project_id,
    evaluation_name,
    agent_name,
    agent_version,
    scheduled_type,
    evaluation_type
| extend category = "evaluation\""""


def create_action_group(token: str, email: str) -> str:
    """Create or update an action group with an email receiver. Returns the resource ID."""
    url = (
        f"https://management.azure.com/subscriptions/{SUBSCRIPTION_ID}"
        f"/resourceGroups/{RESOURCE_GROUP}"
        f"/providers/Microsoft.Insights/actionGroups/{ACTION_GROUP_NAME}"
        f"?api-version=2021-09-01"
    )

    body = {
        "location": "Global",
        "properties": {
            "groupShortName": "EvalAlert",
            "enabled": True,
            "emailReceivers": [
                {
                    "name": "EvalAlertEmail",
                    "emailAddress": email,
                    "useCommonAlertSchema": True,
                }
            ],
        },
    }

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    response = requests.put(url, json=body, headers=headers, timeout=30)
    response.raise_for_status()

    result = response.json()
    print(f"Action group created/updated: {result.get('id')}")
    print(f"  Email: {email}")
    print()
    return result["id"]


def create_eval_alert_rule(token: str, action_group_id: str | None = None) -> dict:
    """Create or update an Azure Monitor scheduled query rule for evaluation pass rate."""

    url = (
        f"https://management.azure.com/subscriptions/{SUBSCRIPTION_ID}"
        f"/resourceGroups/{RESOURCE_GROUP}"
        f"/providers/Microsoft.Insights/scheduledQueryRules/{RULE_NAME}"
        f"?api-version=2021-08-01"
    )

    body = {
        "location": LOCATION,
        "kind": "LogAlert",
        "tags": {
            "linked_azure_ai_project_id": AI_PROJECT_ID,
            "agent_name": AGENT_NAME,
            "agent_alert_category": "evaluation",
        },
        "properties": {
            "displayName": f"Evaluation pass rate alert for agent {AGENT_NAME}",
            "description": "",
            "severity": 3,
            "enabled": ENABLED,
            "evaluationFrequency": "PT5M",
            "scopes": [APPINSIGHTS_RESOURCE_ID],
            "targetResourceTypes": ["microsoft.insights/components"],
            "windowSize": WINDOW_SIZE,
            "actions": {
                "actionGroups": [action_group_id] if action_group_id else [],
            },
            "criteria": {
                "allOf": [
                    {
                        "query": QUERY,
                        "timeAggregation": "Average",
                        "metricMeasureColumn": "PassRate",
                        "dimensions": [
                            {"name": "azure_ai_project_id", "operator": "Include", "values": ["*"]},
                            {"name": "evaluation_name", "operator": "Include", "values": ["*"]},
                            {"name": "agent_name", "operator": "Include", "values": ["*"]},
                            {"name": "agent_version", "operator": "Include", "values": ["*"]},
                            {"name": "scheduled_type", "operator": "Include", "values": ["*"]},
                            {"name": "evaluation_type", "operator": "Include", "values": ["*"]},
                            {"name": "category", "operator": "Include", "values": ["*"]},
                        ],
                        "resourceIdColumn": "",
                        "operator": "LessThanOrEqual",
                        "threshold": PASS_RATE_THRESHOLD,
                        "failingPeriods": {
                            "numberOfEvaluationPeriods": 1,
                            "minFailingPeriodsToAlert": 1,
                        },
                    }
                ]
            },
        },
    }

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    response = requests.put(url, json=body, headers=headers, timeout=30)
    response.raise_for_status()

    result = response.json()
    return result


def main() -> None:
    """Create the evaluation alert rule and print the result."""
    parser = argparse.ArgumentParser(description="Create an Azure Monitor alert for evaluation pass rate.")
    parser.add_argument("--email", help="Email address for alert notifications (creates an action group)")
    args = parser.parse_args()

    credential = AzureDeveloperCliCredential(tenant_id=os.environ["AZURE_TENANT_ID"])
    token = credential.get_token("https://management.azure.com/.default").token

    action_group_id = None
    if args.email:
        print(f"Creating action group: {ACTION_GROUP_NAME}")
        action_group_id = create_action_group(token, args.email)

    print(f"Creating evaluation alert rule: {RULE_NAME}")
    print(f"  Agent: {AGENT_NAME}")
    print(f"  Pass rate threshold: <= {PASS_RATE_THRESHOLD}")
    print(f"  Window size: {WINDOW_SIZE}")
    if action_group_id:
        print(f"  Action group: {action_group_id}")
    print()

    result = create_eval_alert_rule(token, action_group_id)
    print(f"Alert rule created/updated: {result.get('id')}")
    print(f"  Name: {result.get('name')}")
    print(f"  Location: {result.get('location')}")
    props = result.get("properties", {})
    print(f"  Severity: {props.get('severity')}")
    print(f"  Enabled: {props.get('enabled')}")
    print(f"  Evaluation frequency: {props.get('evaluationFrequency')}")
    print(f"  Window size: {props.get('windowSize')}")


if __name__ == "__main__":
    main()
