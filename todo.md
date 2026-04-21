# TODO

## Upgrade MCPStreamableHTTPTool to use `header_provider`

**When:** `azure-ai-agentserver-agentframework` releases a version compatible with `agent-framework-core>=1.0.0`

**PR:** <https://github.com/microsoft/agent-framework/pull/4849>

**What to change in `main.py`:**

Replace the `kb_mcp_endpoint` branch's httpx auth plumbing:

```python
# BEFORE (current): manual httpx client with event_hooks for auth
async def _add_auth(request: httpx.Request) -> None:
    token = await credential.get_token("https://search.azure.com/.default")
    request.headers["Authorization"] = f"Bearer {token.token}"

async with httpx.AsyncClient(event_hooks={"request": [_add_auth]}) as http_client:
    async with MCPStreamableHTTPTool(
        name="knowledge-base",
        url=mcp_url,
        http_client=http_client,
        allowed_tools=["knowledge_base_retrieve"],
    ) as kb_mcp_tool:
        ...
```

With the simpler `header_provider` parameter:

```python
# AFTER: use header_provider (requires agent-framework-core>=1.0.0)
async def _get_auth_headers() -> dict[str, str]:
    token = await credential.get_token("https://search.azure.com/.default")
    return {"Authorization": f"Bearer {token.token}"}

async with MCPStreamableHTTPTool(
    name="knowledge-base",
    url=mcp_url,
    header_provider=_get_auth_headers,
    allowed_tools=["knowledge_base_retrieve"],
) as kb_mcp_tool:
    ...
```

This also removes the `import httpx` dependency.

## Verify Search-to-OpenAI role assignment after fresh deploy

**When:** Next `azd up` / `azd provision`

**What to verify:**

The `searchToAIServicesRoleAssignment` in `infra/core/search/azure_ai_search.bicep` was updated to `scope: aiAccount`. After a fresh deploy:

1. Run `az role assignment list --assignee <search-service-principal-id> --query "[?contains(roleDefinitionName, 'OpenAI')]"` to confirm the role exists
2. Test the KB MCP endpoint tool — invoke the agent and check logs for 401 errors on OpenAI calls
3. If still failing, may need to scope the role assignment differently (e.g., to the specific AI Services resource ID)


## Open questions

Why don't we need to use uvicorn in the Dockerfile? Because the agentserver does that when you call run()

## Hosted agent identity RBAC: find a better approach

**Current workaround:** `infra/hooks/postdeploy.sh` discovers the hosted agent's managed identity
via `azd ai agent show` and assigns `Search Index Data Contributor` on the search service using `az role assignment create`.

**Why it's gross:** The agent identity (`instance_identity.principal_id`) is created by the Foundry
hosting platform at deploy time, not during Bicep provisioning. There's no ARM resource type
for it, so we can't reference it in Bicep. The postdeploy hook runs after every deploy,
relies on `azd ai agent show` JSON parsing, and uses imperative `az` CLI instead of declarative IaC.

**Ask the Hosted Agents team:**
1. Can the agent identity principal ID be exposed as a Bicep-accessible output (e.g., on the project or account resource)?
2. Can the platform auto-assign common roles (like Search Index Data Reader) based on project connections?
3. Is there a planned ARM resource type for hosted agents that would include the identity?

## Duplicate log lines in hosted container

Agent framework logs appear twice in Foundry container logs with different formats:
- `INFO:agent_framework:...` (Python's default format)
- `2026-04-20 21:41:33,411 INFO agent_framework: ...` (timestamped format)

This only happens in the hosted container, not locally. The Foundry hosting platform's
log collector likely reformats and re-emits stderr lines. Not a Python handler issue.

**Ask Hosted Agents team:** Is the container log collector intentionally duplicating stderr?