$ErrorActionPreference = "Stop"

Write-Host "Running postprovision hook for Foundry IQ (Azure AI Search)..."

if (-not $env:AZURE_AI_SEARCH_SERVICE_NAME) {
    Write-Host "AZURE_AI_SEARCH_SERVICE_NAME is not set. Skipping index creation."
    exit 0
}

$searchEndpoint = "https://$($env:AZURE_AI_SEARCH_SERVICE_NAME).search.windows.net"

uv run python infra/create-search-indexes.py `
    --endpoint "$searchEndpoint" `
    --openai-endpoint "$($env:AZURE_OPENAI_ENDPOINT)" `
    --openai-model-deployment "$($env:AZURE_AI_MODEL_DEPLOYMENT_NAME)" `
    --data-dir "data/index-data"

Write-Host "Foundry IQ postprovision complete."

Write-Host "Creating Foundry Toolbox..."

uv run python infra/create-toolbox.py

Write-Host "Foundry Toolbox postprovision complete."
