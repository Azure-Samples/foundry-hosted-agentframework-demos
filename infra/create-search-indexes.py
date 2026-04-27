"""Create Azure AI Search indexes and upload sample data for Foundry IQ demos."""

import asyncio
import json
import os
from pathlib import Path
from typing import Any

from azure.identity.aio import AzureDeveloperCliCredential
from azure.search.documents.aio import SearchClient
from azure.search.documents.indexes.aio import SearchIndexClient
from azure.search.documents.indexes.models import (
    AzureOpenAIVectorizerParameters,
    KnowledgeBase,
    KnowledgeBaseAzureOpenAIModel,
    KnowledgeRetrievalOutputMode,
    KnowledgeSourceReference,
    SearchIndex,
    SearchIndexFieldReference,
    SearchIndexKnowledgeSource,
    SearchIndexKnowledgeSourceParameters,
)
from dotenv import load_dotenv

load_dotenv(dotenv_path=".env", override=True)


async def create_index_and_upload(
    endpoint: str,
    credential: Any,
    index_name: str,
    index_schema_path: Path,
    records_path: Path,
    openai_endpoint: str,
) -> int:
    """Create or update an index and upload documents, returning uploaded count."""
    async with SearchIndexClient(endpoint=endpoint, credential=credential) as index_client:
        with index_schema_path.open("r", encoding="utf-8") as f:
            index_data = json.load(f)

        index = SearchIndex.deserialize(index_data)
        index.name = index_name

        if openai_endpoint and index.vector_search and index.vector_search.vectorizers:
            index.vector_search.vectorizers[0].parameters.resource_url = openai_endpoint

        await index_client.create_or_update_index(index)

    uploaded_count = 0
    batch_size = 100
    batch: list[dict] = []

    async with SearchClient(endpoint=endpoint, index_name=index_name, credential=credential) as search_client:
        with records_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                batch.append(json.loads(line))
                if len(batch) >= batch_size:
                    await search_client.upload_documents(documents=batch)
                    uploaded_count += len(batch)
                    batch = []

        if batch:
            await search_client.upload_documents(documents=batch)
            uploaded_count += len(batch)

    return uploaded_count


async def create_knowledge_source(
    index_client: SearchIndexClient,
    index_name: str,
    description: str,
) -> SearchIndexKnowledgeSource:
    """Create a knowledge source that references a search index."""
    source_data_fields = [
        SearchIndexFieldReference(name="uid"),
        SearchIndexFieldReference(name="snippet"),
        SearchIndexFieldReference(name="blob_path"),
        SearchIndexFieldReference(name="snippet_parent_id"),
    ]

    knowledge_source = SearchIndexKnowledgeSource(
        name=index_name,
        description=description,
        search_index_parameters=SearchIndexKnowledgeSourceParameters(
            search_index_name=index_name,
            source_data_fields=source_data_fields,
            search_fields=[SearchIndexFieldReference(name="snippet")],
            semantic_configuration_name="semantic-configuration",
        ),
    )

    await index_client.create_or_update_knowledge_source(knowledge_source=knowledge_source)
    print(f"Created knowledge source: {index_name}")
    return knowledge_source


async def create_knowledge_base(
    endpoint: str,
    credential: Any,
    kb_name: str,
    kb_description: str,
    knowledge_source_configs: list[tuple[str, str]],
    openai_endpoint: str = "",
    openai_model_deployment: str = "",
) -> None:
    """Create a Knowledge Base with multiple knowledge sources."""
    async with SearchIndexClient(endpoint=endpoint, credential=credential) as index_client:
        # Create each knowledge source
        source_refs = []
        for index_name, source_description in knowledge_source_configs:
            source = await create_knowledge_source(index_client, index_name, source_description)
            source_refs.append(KnowledgeSourceReference(name=source.name))

        # Create the knowledge base (include LLM model for query planning if available)
        models = []
        if openai_endpoint and openai_model_deployment:
            models = [
                KnowledgeBaseAzureOpenAIModel(
                    azure_open_ai_parameters=AzureOpenAIVectorizerParameters(
                        resource_url=openai_endpoint,
                        deployment_name=openai_model_deployment,
                        model_name="gpt-5",
                    )
                )
            ]
        knowledge_base = KnowledgeBase(
            name=kb_name,
            description=kb_description,
            knowledge_sources=source_refs,
            output_mode=KnowledgeRetrievalOutputMode.EXTRACTIVE_DATA,
            **(dict(models=models) if models else {}),
        )

        await index_client.create_or_update_knowledge_base(knowledge_base=knowledge_base)
        print(f"Created knowledge base: {kb_name} with {len(source_refs)} knowledge sources")


async def main_async() -> int:
    """Run index creation for all demo indexes."""
    endpoint = os.environ["AZURE_AI_SEARCH_SERVICE_ENDPOINT"]
    openai_endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT", "")
    openai_model_deployment = os.environ.get("AZURE_AI_MODEL_DEPLOYMENT_NAME", "")
    data_dir = Path("data/index-data")

    if not data_dir.exists():
        print(f"Data directory not found: {data_dir}")
        return 1

    index_schema_path = data_dir / "index.json"
    if not index_schema_path.exists():
        print(f"Index schema not found: {index_schema_path}")
        return 1

    credential = AzureDeveloperCliCredential(tenant_id=os.environ["AZURE_TENANT_ID"])

    # Check if knowledge base already exists — skip if so
    async with SearchIndexClient(endpoint=endpoint, credential=credential) as index_client:
        try:
            await index_client.get_knowledge_base("zava-company-kb")
            print("Knowledge base 'zava-company-kb' already exists. Skipping index creation.")
            await credential.close()
            return 0
        except Exception:
            pass

    indexes = [
        ("hrdocs", data_dir / "hrdocs-exported.jsonl"),
        ("healthdocs", data_dir / "healthdocs-exported.jsonl"),
    ]

    for index_name, records_path in indexes:
        if not records_path.exists():
            print(f"Records file not found for {index_name}: {records_path}")
            return 1

        print(f"Creating index: {index_name}")
        uploaded = await create_index_and_upload(
            endpoint=endpoint,
            credential=credential,
            index_name=index_name,
            index_schema_path=index_schema_path,
            records_path=records_path,
            openai_endpoint=openai_endpoint,
        )
        print(f"Uploaded {uploaded} docs to {index_name}")
        await asyncio.sleep(2)

    # Create a single knowledge base with both indexes as knowledge sources
    print("\nCreating knowledge base...")
    await create_knowledge_base(
        endpoint=endpoint,
        credential=credential,
        kb_name="zava-company-kb",
        kb_description=(
            "Contains internal HR documents about employee benefits and health/wellness programs."
        ),
        knowledge_source_configs=[
            (
                "hrdocs",
                "HR policy and company documents including the employee handbook, PerksPlus wellness "
                "reimbursement program, company overview, vacation perks, employee recognition, "
                "role library (job descriptions), workplace safety, and performance reviews.",
            ),
            (
                "healthdocs",
                "Health insurance plan documents including medical plan details (Northwind Health Plus "
                "and Northwind Standard), coverage options (PPO, HMO, HDHP), copays, deductibles, "
                "coinsurance, prescription drug coverage, dental, vision, mental health services, "
                "workers compensation, and preventive care benefits.",
            ),
        ],
        openai_endpoint=openai_endpoint,
        openai_model_deployment=openai_model_deployment,
    )

    print("Search index and knowledge base creation complete.")

    await credential.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main_async()))
