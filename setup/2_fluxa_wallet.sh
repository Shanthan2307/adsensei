#!/bin/bash
# Step 2: Initialize FluxA wallet and wire it to AgentHansa.
# Requires: AGENT_KEY in .env

set -e
source "$(dirname "$0")/../.env"

if [ -z "$AGENT_KEY" ]; then
  echo "ERROR: AGENT_KEY not set. Run 1_register_agent.sh first."
  exit 1
fi

echo "=== Initializing FluxA wallet ==="
npx @fluxa-pay/fluxa-wallet@latest init --name "LeadForge" --client python

echo ""
echo "=== Enter your FluxA Agent ID from above ==="
read -r FLUXA_ID

echo "Wiring FluxA wallet to AgentHansa..."
curl -s -X PUT https://www.agenthansa.com/api/agents/fluxa-wallet \
  -H "Authorization: Bearer $AGENT_KEY" \
  -H "Content-Type: application/json" \
  -d "{\"fluxa_agent_id\": \"$FLUXA_ID\"}" | python3 -m json.tool

# Save to .env
ENV_FILE="$(dirname "$0")/../.env"
if grep -q "^FLUXA_AGENT_ID=" "$ENV_FILE" 2>/dev/null; then
  sed -i '' "s|^FLUXA_AGENT_ID=.*|FLUXA_AGENT_ID=$FLUXA_ID|" "$ENV_FILE"
else
  echo "FLUXA_AGENT_ID=$FLUXA_ID" >> "$ENV_FILE"
fi

echo "FluxA wallet wired."
