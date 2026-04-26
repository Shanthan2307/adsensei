#!/bin/bash
# Step 1: Register your agent on AgentHansa.
# Run once — saves api_key to .env (shown ONCE, never again).

set -e
source "$(dirname "$0")/../.env" 2>/dev/null || true

AGENT_NAME="${1:-LeadForge}"
DESCRIPTION="${2:-Autonomous B2B lead generation agent}"

echo "Registering agent: $AGENT_NAME"

RESPONSE=$(curl -s -X POST https://www.agenthansa.com/api/agents/register \
  -H "Content-Type: application/json" \
  -d "{\"name\": \"$AGENT_NAME\", \"description\": \"$DESCRIPTION\"}")

echo "$RESPONSE" | python3 -m json.tool

API_KEY=$(echo "$RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('api_key',''))")

if [ -n "$API_KEY" ] && [ "$API_KEY" != "None" ]; then
  echo ""
  echo "SUCCESS — saving AGENT_KEY to .env"
  # Append or replace AGENT_KEY in .env
  ENV_FILE="$(dirname "$0")/../.env"
  if grep -q "^AGENT_KEY=" "$ENV_FILE" 2>/dev/null; then
    sed -i '' "s|^AGENT_KEY=.*|AGENT_KEY=$API_KEY|" "$ENV_FILE"
  else
    echo "AGENT_KEY=$API_KEY" >> "$ENV_FILE"
  fi
  echo "AGENT_KEY saved. Do not lose this."
else
  echo "No api_key in response — check output above."
fi
