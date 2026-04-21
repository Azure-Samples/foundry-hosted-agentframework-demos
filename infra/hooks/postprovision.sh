#!/bin/sh
set -eu

echo "Running postprovision hook for Foundry IQ (Azure AI Search)..."

if [ -z "${AZURE_AI_SEARCH_SERVICE_NAME:-}" ]; then
    echo "AZURE_AI_SEARCH_SERVICE_NAME is not set. Skipping index creation."
    exit 0
fi

SEARCH_ENDPOINT="https://${AZURE_AI_SEARCH_SERVICE_NAME}.search.windows.net"

uv run python infra/create-search-indexes.py \
    --endpoint "$SEARCH_ENDPOINT" \
    --openai-endpoint "${AZURE_OPENAI_ENDPOINT:-}" \
    --openai-model-deployment "${AZURE_AI_MODEL_DEPLOYMENT_NAME:-}" \
    --data-dir "data/index-data"

echo "Foundry IQ postprovision complete."

echo "Creating Foundry Toolbox..."

uv run python infra/create-toolbox.py

echo "Foundry Toolbox postprovision complete."
