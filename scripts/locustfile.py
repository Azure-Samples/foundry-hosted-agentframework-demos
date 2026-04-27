"""Locust load test for the hosted agent.

Usage:
    locust -f scripts/locustfile.py --headless -u 10 -r 2 -t 5m
    # Or with the web UI:
    locust -f scripts/locustfile.py
"""

import os
import random
import time

from azure.ai.projects import AIProjectClient
from azure.identity import AzureDeveloperCliCredential
from dotenv import load_dotenv
from locust import HttpUser, between, events, task

load_dotenv(override=True)

AGENT_NAME = os.environ.get("LOCUST_AGENT", "hosted-agentframework-agent")
PROJECT_ENDPOINT = os.environ["FOUNDRY_PROJECT_ENDPOINT"]

# Queries grouped by which tool(s) they exercise
QUERIES_KB = [
    "What PerksPlus benefits are there?",
    "What health plans does Zava offer?",
    "Can I use PerksPlus to pay for physical therapy, or is that covered by my health plan?",
    "What is Zava's parental leave policy?",
    "Tell me about the PerksPlus reimbursement limit.",
    "What mental health benefits does Zava provide?",
    "What are Zava's core values?",
    "What job roles are available at Zava?",
]

QUERIES_ENROLLMENT = [
    "When does benefits enrollment open and close?",
    "What are the enrollment deadlines for health insurance?",
]

QUERIES_DATE_PLUS_ENROLLMENT = [
    "How many days until enrollment opens?",
    "Is it too late to enroll in benefits this year?",
]

QUERIES_KB_PLUS_ENROLLMENT = [
    "What PerksPlus benefits are there, and when do I need to enroll by?",
    "What health plans does Zava offer and when is the enrollment period?",
]

QUERIES_CODE_INTERPRETER = [
    "If I contribute 6% of a $120,000 salary to my 401k with a 50% employer match, "
    "how much total goes in per year? Use Code Interpreter to write Python code to calculate.",
    "Make a pie chart of the Zava vacation tiers: Standard 2 weeks, Senior 4 weeks, Executive 6 weeks.",
]

QUERIES_WEB_SEARCH = [
    "Search the web to find weather for El Cerrito today.",
    "What was the latest US jobs report?",
    "What are the current mortgage rates?",
]

QUERIES_OFFTOPIC = [
    "What is the capital of France?",
    "Write me a Python script to sort a list.",
    "Explain how to set up a Kubernetes cluster.",
    "Who won the 2024 Super Bowl?",
    "What is the speed of light in meters per second?",
    "Tell me a joke about penguins.",
    "How do I make sourdough bread from scratch?",
]

ALL_QUERIES = (
    [(q, "kb") for q in QUERIES_KB]
    + [(q, "enrollment") for q in QUERIES_ENROLLMENT]
    + [(q, "date_enrollment") for q in QUERIES_DATE_PLUS_ENROLLMENT]
    + [(q, "kb_enrollment") for q in QUERIES_KB_PLUS_ENROLLMENT]
    + [(q, "code_interpreter") for q in QUERIES_CODE_INTERPRETER]
    + [(q, "web_search") for q in QUERIES_WEB_SEARCH]
    + [(q, "offtopic") for q in QUERIES_OFFTOPIC]
)

# Initialize Foundry client once at module load time
_project_client = AIProjectClient(
    endpoint=PROJECT_ENDPOINT,
    credential=AzureDeveloperCliCredential(tenant_id=os.environ["AZURE_TENANT_ID"]),
    allow_preview=True,
)
_openai_client = _project_client.get_openai_client(agent_name=AGENT_NAME)

print(f"Locust targeting agent '{AGENT_NAME}' at {PROJECT_ENDPOINT}")
print(f"Total query pool: {len(ALL_QUERIES)} queries")


class HostedAgentUser(HttpUser):
    """Simulates users chatting with the hosted HR agent."""

    wait_time = between(1, 3)
    host = PROJECT_ENDPOINT

    @task
    def single_turn(self):
        """Send a single random query using responses.create."""
        query, category = random.choice(ALL_QUERIES)

        start_time = time.perf_counter()
        exception = None
        response_length = 0

        try:
            response = _openai_client.responses.create(
                input=query,
            )
            response_length = len(response.output_text)
        except Exception as e:
            exception = e

        elapsed_ms = (time.perf_counter() - start_time) * 1000

        events.request.fire(
            request_type="foundry_agent",
            name=f"single/{category}",
            response_time=elapsed_ms,
            response_length=response_length,
            exception=exception,
            context={},
        )
