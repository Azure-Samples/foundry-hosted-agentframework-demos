#!/bin/bash
# Test the KB MCP endpoint directly with curl.
# Exports the tools/call response to a timestamped run directory.
#
# Usage:
#   ./scripts/test_kb_mcp.sh
#   ./scripts/test_kb_mcp.sh "employee benefits overview"

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/../.env"

QUERY="${1:-perksplus benefits}"
MCP_URL="${AZURE_AI_SEARCH_SERVICE_ENDPOINT}/knowledgebases/${AZURE_AI_SEARCH_KNOWLEDGE_BASE_NAME:-zava-company-kb}/mcp?api-version=2026-05-01-preview"
TOKEN=$(az account get-access-token --resource https://search.azure.com --query accessToken -o tsv)
OUTPUT_BASE="$SCRIPT_DIR/test_output_kb"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
RUN_DIR="$OUTPUT_BASE/$TIMESTAMP"
OUTPUT_FILE="$RUN_DIR/kb_mcp_response.json"

mkdir -p "$RUN_DIR"

AUTH="Authorization: Bearer $TOKEN"
CT="Content-Type: application/json"
ACCEPT="Accept: application/json, text/event-stream"

echo "MCP URL: $MCP_URL"
echo "Query: $QUERY"
echo "Run directory: $RUN_DIR"
echo ""

# Step 1: Initialize
echo "--- Initialize ---"
curl -s -X POST "$MCP_URL" \
  -H "$AUTH" -H "$CT" -H "$ACCEPT" \
  -d '{"jsonrpc":"2.0","id":0,"method":"initialize","params":{"protocolVersion":"2025-11-25","capabilities":{"sampling":{}},"clientInfo":{"name":"test","version":"0.1.0"}}}'
echo ""

# Step 2: Notify
echo "--- Notify ---"
curl -s -X POST "$MCP_URL" \
  -H "$AUTH" -H "$CT" \
  -d '{"jsonrpc":"2.0","method":"notifications/initialized"}'
echo ""

# Step 3: Call tool
echo "--- Call knowledge_base_retrieve ---"
RESPONSE=$(curl -s -X POST "$MCP_URL" \
  -H "$AUTH" -H "$CT" -H "$ACCEPT" \
  -d "{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"tools/call\",\"params\":{\"name\":\"knowledge_base_retrieve\",\"arguments\":{\"queries\":[\"$QUERY\"]}}}")

# Parse SSE: extract the data: line
echo "$RESPONSE" | grep '^data:' | head -1 | sed 's/^data://' | python3 -m json.tool > "$OUTPUT_FILE"

echo "Response saved to $OUTPUT_FILE"
echo ""
echo "First content item type:"
python3 -c "import json; d=json.load(open('$OUTPUT_FILE')); print(json.dumps(d['result']['content'][0], indent=2)[:500])" 2>/dev/null || echo "(no content)"
