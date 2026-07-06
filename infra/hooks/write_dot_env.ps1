# Write the necessary environment variables from azd env to .env for local development.
# Usage: .\write_dot_env.ps1

$ErrorActionPreference = "Stop"

$EnvFile = ".env"

$Vars = @(
    "AZURE_TENANT_ID"
    "AZURE_SUBSCRIPTION_ID"
    "AZURE_RESOURCE_GROUP"
    "AZURE_LOCATION"
    "FOUNDRY_PROJECT_ENDPOINT"
    "AZURE_AI_MODEL_DEPLOYMENT_NAME"
    "AZURE_AI_SEARCH_SERVICE_ENDPOINT"
    "AZURE_AI_SEARCH_KB_MCP_CONNECTION_NAME"
    "AZURE_OPENAI_ENDPOINT"
    "APPLICATIONINSIGHTS_CONNECTION_STRING"
    "APPLICATIONINSIGHTS_RESOURCE_ID"
    "AZURE_AI_PROJECT_ID"
)

Write-Host "Writing $EnvFile from azd env..."
"" | Set-Content $EnvFile

foreach ($var in $Vars) {
    $value = azd env get-value $var 2>$null
    if ($value) {
        "${var}=${value}" | Add-Content $EnvFile
    }
}

# Add non-azd vars with defaults
"AZURE_AI_SEARCH_KNOWLEDGE_BASE_NAME=zava-company-kb" | Add-Content $EnvFile
"CUSTOM_FOUNDRY_AGENT_TOOLBOX_NAME=hr-agent-tools" | Add-Content $EnvFile

Write-Host "Wrote ${EnvFile}"
