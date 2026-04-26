"""
LeadForge Agent — AI Agent Economy Hackathon
Autonomous B2B lead generation agent that earns USDC via AgentHansa.
"""

import os
import json
from dotenv import load_dotenv
import anthropic

load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

TOOLS = [
    {
        "name": "search_companies",
        "description": "Search for companies matching criteria (industry, location, size, hiring signals).",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query for companies"},
                "location": {"type": "string", "description": "Target city or region"},
                "industry": {"type": "string", "description": "Target industry"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "enrich_lead",
        "description": "Enrich a company with decision-maker info, tech stack, and personalization data.",
        "input_schema": {
            "type": "object",
            "properties": {
                "company_name": {"type": "string"},
                "website": {"type": "string"},
            },
            "required": ["company_name"],
        },
    },
    {
        "name": "write_email",
        "description": "Write a personalized cold outreach email for a prospect.",
        "input_schema": {
            "type": "object",
            "properties": {
                "company_name": {"type": "string"},
                "contact_name": {"type": "string"},
                "contact_role": {"type": "string"},
                "pain_point": {"type": "string"},
                "value_prop": {"type": "string"},
            },
            "required": ["company_name", "contact_name", "value_prop"],
        },
    },
    {
        "name": "submit_to_agenthansa",
        "description": "Submit completed lead report to AgentHansa for human verification and USDC payout.",
        "input_schema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string"},
                "leads": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "company": {"type": "string"},
                            "contact": {"type": "string"},
                            "email": {"type": "string"},
                            "email_draft": {"type": "string"},
                        },
                    },
                },
            },
            "required": ["task_id", "leads"],
        },
    },
]


def handle_tool(name: str, inputs: dict) -> str:
    """Mock tool handlers — replace with real API calls."""
    if name == "search_companies":
        return json.dumps([
            {"company": "Acme SaaS", "website": "acmesaas.com", "location": inputs.get("location", "SF")},
            {"company": "DataStack Inc", "website": "datastack.io", "location": inputs.get("location", "SF")},
        ])

    if name == "enrich_lead":
        return json.dumps({
            "company": inputs["company_name"],
            "contact_name": "Jane Smith",
            "contact_role": "VP of Engineering",
            "email": f"jsmith@{inputs.get('website', 'company.com')}",
            "pain_point": "Scaling engineering hiring without a sourcing team",
            "tech_stack": ["Python", "AWS", "Postgres"],
        })

    if name == "write_email":
        return (
            f"Subject: Quick question for {inputs['contact_name']}\n\n"
            f"Hi {inputs['contact_name']},\n\n"
            f"Noticed {inputs['company_name']} is growing fast. "
            f"{inputs['value_prop']}\n\n"
            f"Worth a 15-min call this week?\n\nBest,"
        )

    if name == "submit_to_agenthansa":
        print(f"\n[AgentHansa] Submitting {len(inputs['leads'])} leads for task {inputs['task_id']}...")
        return json.dumps({"status": "submitted", "task_id": inputs["task_id"], "pending_usdc": 25.00})

    return json.dumps({"error": f"Unknown tool: {name}"})


def run_agent(task: str, task_id: str = "demo-001"):
    print(f"\n=== LeadForge Agent ===")
    print(f"Task: {task}\n")

    messages = [{"role": "user", "content": task}]

    system = (
        "You are LeadForge, an autonomous B2B lead generation agent. "
        "Given a task, you: search for matching companies, enrich each lead with contact info, "
        "write personalized cold emails, then submit the final lead report to AgentHansa. "
        "Always complete all steps before submitting. Be thorough and professional."
    )

    while True:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            system=system,
            tools=TOOLS,
            messages=messages,
        )

        print(f"[Agent] stop_reason={response.stop_reason}")

        if response.stop_reason == "end_turn":
            for block in response.content:
                if hasattr(block, "text"):
                    print(f"\n[Agent Output]\n{block.text}")
            break

        if response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    print(f"  -> Tool: {block.name}({json.dumps(block.input, indent=2)})")
                    result = handle_tool(block.name, block.input)
                    print(f"     Result: {result[:120]}...")
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })
            messages.append({"role": "user", "content": tool_results})
        else:
            break

    return response


if __name__ == "__main__":
    task = (
        "Find 5 SaaS companies in San Francisco that are actively hiring engineers. "
        "For each, get the VP of Engineering's contact info and write a personalized cold email "
        "pitching our AI-powered recruiting tool. Then submit the lead report to AgentHansa. "
        f"Task ID: demo-001"
    )
    run_agent(task)
