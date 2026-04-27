targetScope = 'subscription'
// targetScope = 'resourceGroup'

@minLength(1)
@maxLength(64)
@description('Name of the environment that can be used as part of naming resource convention')
param environmentName string

@minLength(1)
@maxLength(90)
@description('Name of the resource group to use or create')
param resourceGroupName string = 'rg-${environmentName}'

// Restricted locations to support all features:
// - Foundry hosted: https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/hosted-agents#region-availability
// - Responses API: https://learn.microsoft.com/en-us/azure/ai-foundry/openai/how-to/responses?tabs=python-key#region-availability
// - Evaluations + red teaming: https://learn.microsoft.com/en-us/azure/foundry/concepts/evaluation-regions-limits-virtual-network
@minLength(1)
@description('Primary location for all resources')
@allowed([
  'eastus2'
  'francecentral'
  'northcentralus'
  'swedencentral'
])
param location string

@description('Id of the user or app to assign application roles')
param principalId string

@description('Principal type of user or app')
param principalType string

@description('Optional. Name of an existing AI Services account within the resource group. If not provided, a new one will be created.')
param aiFoundryResourceName string = ''

@description('Optional. Name of the AI Foundry project. If not provided, a default name will be used.')
param aiFoundryProjectName string = 'ai-project-${environmentName}'

@description('Enable hosted agent deployment')
param enableHostedAgents bool

@description('Enable Azure AI Search provisioning and project connection')
param enableSearch bool = true

@description('Enable monitoring for the AI project')
param enableMonitoring bool = true

@description('Optional. Existing container registry resource ID. If provided, no new ACR will be created and a connection to this ACR will be established.')
param existingContainerRegistryResourceId string = ''

@description('Optional. Existing container registry endpoint (login server). Required if existingContainerRegistryResourceId is provided.')
param existingContainerRegistryEndpoint string = ''

@description('Optional. Name of an existing ACR connection on the Foundry project. If provided, no new ACR or connection will be created.')
param existingAcrConnectionName string = ''

@description('Optional. Existing Application Insights connection string. If provided, a connection will be created but no new App Insights resource.')
param existingApplicationInsightsConnectionString string = ''

@description('Optional. Existing Application Insights resource ID. Used for connection metadata when providing an existing App Insights.')
param existingApplicationInsightsResourceId string = ''

@description('Optional. Name of an existing Application Insights connection on the Foundry project. If provided, no new App Insights or connection will be created.')
param existingAppInsightsConnectionName string = ''

var aiProjectDeployments = [
  {
    name: 'gpt-5.2'
    model: {
      format: 'OpenAI'
      name: 'gpt-5.2'
      version: '2025-12-11'
    }
    sku: {
      name: 'GlobalStandard'
      capacity: 10
    }
  }
]
var defaultModelDeploymentName = string(aiProjectDeployments[0].name)


// Tags that should be applied to all resources.
// 
// Note that 'azd-service-name' tags should be applied separately to service host resources.
// Example usage:
//   tags: union(tags, { 'azd-service-name': <service name in azure.yaml> })
var tags = {
  'azd-env-name': environmentName
}

// Check if resource group exists and create it if it doesn't
resource rg 'Microsoft.Resources/resourceGroups@2021-04-01' = {
  name: resourceGroupName
  location: location
  tags: tags
}

// Build dependent resources array conditionally
var shouldCreateAcr = enableHostedAgents && empty(existingContainerRegistryResourceId) && empty(existingAcrConnectionName)
var dependentResources = shouldCreateAcr ? [
  {
    resource: 'registry'
    connectionName: 'acr-connection'
  }
] : []

// AI Project module
module aiProject 'core/ai/ai-project.bicep' = {
  scope: rg
  name: 'ai-project'
  params: {
    tags: tags
    location: location
    aiFoundryProjectName: aiFoundryProjectName
    principalId: principalId
    principalType: principalType
    existingAiAccountName: aiFoundryResourceName
    deployments: aiProjectDeployments
    additionalDependentResources: dependentResources
    enableMonitoring: enableMonitoring
    enableHostedAgents: enableHostedAgents
    enableSearch: enableSearch
    existingContainerRegistryResourceId: existingContainerRegistryResourceId
    existingContainerRegistryEndpoint: existingContainerRegistryEndpoint
    existingAcrConnectionName: existingAcrConnectionName
    existingApplicationInsightsConnectionString: existingApplicationInsightsConnectionString
    existingApplicationInsightsResourceId: existingApplicationInsightsResourceId
    existingAppInsightsConnectionName: existingAppInsightsConnectionName
  }
}

// Resources
output AZURE_RESOURCE_GROUP string = resourceGroupName
output AZURE_AI_ACCOUNT_ID string = aiProject.outputs.accountId
output AZURE_AI_PROJECT_ID string = aiProject.outputs.projectId
output AZURE_AI_FOUNDRY_PROJECT_ID string = aiProject.outputs.projectId
output AZURE_AI_ACCOUNT_NAME string = aiProject.outputs.aiServicesAccountName
output AZURE_AI_PROJECT_NAME string = aiProject.outputs.projectName

// Endpoints
output AZURE_AI_PROJECT_ENDPOINT string = aiProject.outputs.AZURE_AI_PROJECT_ENDPOINT // Required by azd deploy
output FOUNDRY_PROJECT_ENDPOINT string = aiProject.outputs.AZURE_AI_PROJECT_ENDPOINT // Future: https://github.com/Azure/azure-dev/issues/7905
output AZURE_AI_MODEL_DEPLOYMENT_NAME string = defaultModelDeploymentName
output AZURE_OPENAI_ENDPOINT string = aiProject.outputs.AZURE_OPENAI_ENDPOINT
output APPLICATIONINSIGHTS_CONNECTION_STRING string = aiProject.outputs.APPLICATIONINSIGHTS_CONNECTION_STRING
output APPLICATIONINSIGHTS_RESOURCE_ID string = aiProject.outputs.APPLICATIONINSIGHTS_RESOURCE_ID

// Dependent Resources and Connections

// ACR
output AZURE_AI_PROJECT_ACR_CONNECTION_NAME string = aiProject.outputs.dependentResources.registry.connectionName
output AZURE_CONTAINER_REGISTRY_ENDPOINT string = aiProject.outputs.dependentResources.registry.loginServer

// Bing Search
output BING_GROUNDING_CONNECTION_NAME  string = aiProject.outputs.dependentResources.bing_grounding.connectionName
output BING_GROUNDING_RESOURCE_NAME string = aiProject.outputs.dependentResources.bing_grounding.name
output BING_GROUNDING_CONNECTION_ID string = aiProject.outputs.dependentResources.bing_grounding.connectionId

// Bing Custom Search
output BING_CUSTOM_GROUNDING_CONNECTION_NAME string = aiProject.outputs.dependentResources.bing_custom_grounding.connectionName
output BING_CUSTOM_GROUNDING_NAME string = aiProject.outputs.dependentResources.bing_custom_grounding.name
output BING_CUSTOM_GROUNDING_CONNECTION_ID string = aiProject.outputs.dependentResources.bing_custom_grounding.connectionId

// Azure AI Search
output AZURE_AI_SEARCH_CONNECTION_NAME string = aiProject.outputs.dependentResources.search.connectionName
output AZURE_AI_SEARCH_SERVICE_NAME string = aiProject.outputs.dependentResources.search.serviceName
output AZURE_AI_SEARCH_SERVICE_ENDPOINT string = !empty(aiProject.outputs.dependentResources.search.serviceName) ? 'https://${aiProject.outputs.dependentResources.search.serviceName}.search.windows.net' : ''
output AZURE_AI_SEARCH_KB_MCP_CONNECTION_NAME string = aiProject.outputs.dependentResources.search.kbMcpConnectionName

// Azure Storage
output AZURE_STORAGE_CONNECTION_NAME string = aiProject.outputs.dependentResources.storage.connectionName
output AZURE_STORAGE_ACCOUNT_NAME string = aiProject.outputs.dependentResources.storage.accountName

// Tenant
output AZURE_TENANT_ID string = tenant().tenantId
