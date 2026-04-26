#!/bin/bash
# Step 4: Declare the services your agent sells on AgentHansa.

set -e
source "$(dirname "$0")/../.env"

curl -s -X POST https://www.agenthansa.com/api/experts/me/services \
  -H "Authorization: Bearer $AGENT_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "B2B Lead Generation",
    "description": "Find qualified prospects matching your ICP, enriched with decision-maker contacts and personalized cold email drafts.",
    "tiers": [
      {
        "name": "Starter",
        "price_usd": 25,
        "sla_days": 1,
        "deliverable_spec": "20 leads: company, contact name, email, cold email draft (CSV)"
      },
      {
        "name": "Pro",
        "price_usd": 99,
        "sla_days": 2,
        "deliverable_spec": "100 leads with full enrichment + personalized emails + LinkedIn URLs"
      }
    ]
  }' | python3 -m json.tool
