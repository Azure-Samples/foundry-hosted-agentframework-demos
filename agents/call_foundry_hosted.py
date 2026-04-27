"""
Call the deployed hosted agent via the azure-ai-projects SDK.
"""
import os

from azure.ai.projects import AIProjectClient
from azure.identity import AzureDeveloperCliCredential
from dotenv import load_dotenv

load_dotenv(dotenv_path=".env", override=True)

AGENT_NAME = "hosted-agentframework-agent" # matches agent.yaml
PROJECT_ENDPOINT = os.environ["FOUNDRY_PROJECT_ENDPOINT"]

credential = AzureDeveloperCliCredential(tenant_id=os.environ["AZURE_TENANT_ID"])
project = AIProjectClient(
    endpoint=PROJECT_ENDPOINT,
    credential=credential,
    allow_preview=True
)
openai_client = project.get_openai_client(agent_name=AGENT_NAME)
response = openai_client.responses.create(input="What PerksPlus benefits are there?")
print(response.output_text)
