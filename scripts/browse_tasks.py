"""
Browse open bounty tasks on AgentHansa and optionally claim one.
Run: python3 browse_tasks.py
"""

import os
import json
import httpx
from dotenv import load_dotenv

load_dotenv()

AGENT_KEY = os.getenv("AGENT_KEY", "")
API = os.getenv("AGENTHANSA_BASE", "https://www.agenthansa.com")
HEADERS = {"Authorization": f"Bearer {AGENT_KEY}"}


def browse():
    with httpx.Client(timeout=30) as http:
        r = http.get(f"{API}/api/collective/bounties/public", headers=HEADERS)
        tasks = r.json()

        if not tasks:
            print("No open tasks right now.")
            return

        print(f"\n{'─'*60}")
        print(f"{'ID':<10} {'Title':<35} {'$':<8} {'SLA'}")
        print(f"{'─'*60}")

        for t in tasks[:20]:
            print(f"{str(t.get('id','')):<10} {str(t.get('title',''))[:34]:<35} "
                  f"${t.get('reward_usd', 0):<7} {t.get('sla_days','?')}d")

        print(f"{'─'*60}")
        print(f"Total: {len(tasks)} tasks\n")

        task_id = input("Enter task ID to claim (or press Enter to skip): ").strip()
        if task_id:
            r2 = http.post(f"{API}/api/collective/bounties/{task_id}/join", headers=HEADERS)
            print(json.dumps(r2.json(), indent=2))


if __name__ == "__main__":
    browse()
