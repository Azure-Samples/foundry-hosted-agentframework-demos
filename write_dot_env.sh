#!/bin/bash
# Write the necessary environment variables from azd env to .env for local development.
# Usage: ./write_dot_env.sh

set -euo pipefail

ENV_FILE=".env"

VARS=(
    AZURE_AI_PROJECT_ENDPOINT
    AZURE_AI_MODEL_DEPLOYMENT_NAME
    AZURE_AI_SEARCH_SERVICE_ENDPOINT
    AZURE_OPENAI_ENDPOINT
    APPLICATIONINSIGHTS_CONNECTION_STRING
)

echo "Writing $ENV_FILE from azd env..."
: > "$ENV_FILE"

for var in "${VARS[@]}"; do
    value=$(azd env get-value "$var" 2>/dev/null || echo "")
    if [ -n "$value" ]; then
        echo "${var}=${value}" >> "$ENV_FILE"
    fi
done

# Add non-azd vars with defaults
echo "AZURE_AI_SEARCH_KNOWLEDGE_BASE_NAME=zava-company-kb" >> "$ENV_FILE"
echo "FOUNDRY_IQ_CONTEXT_MODE=kb_mcp_endpoint" >> "$ENV_FILE"

echo "Wrote $ENV_FILE:"
cat "$ENV_FILE"
