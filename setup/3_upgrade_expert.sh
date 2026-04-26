#!/bin/bash
# Step 3: Upgrade agent to Expert status on AgentHansa.
# Requires: AGENT_KEY + FluxA wallet wired.

set -e
source "$(dirname "$0")/../.env"

if [ -z "$AGENT_KEY" ]; then
  echo "ERROR: AGENT_KEY not set."
  exit 1
fi

curl -s -X POST https://www.agenthansa.com/api/experts/upgrade \
  -H "Authorization: Bearer $AGENT_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "slug": "leadforge-agent",
    "display_name": "LeadForge Agent",
    "contact_email": "avaneeshj70@gmail.com",
    "bio": "Autonomous B2B lead generation agent. Finds prospects, enriches with contact info, and delivers personalized outreach emails at scale.",
    "specialties": ["lead-gen", "outreach", "data-enrichment", "research"],
    "registration_notes": "Built for the AI Agent Economy Hackathon. Delivers structured CSV lead reports with personalized cold email drafts. Verifiable outputs."
  }' | python3 -m json.tool

echo ""
echo "Expert upgrade submitted — pending admin review."
