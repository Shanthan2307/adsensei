"""
AgentHansa expert loop — Pattern A (always-on long-poll).
Listens for merchant messages, runs the agent, replies automatically.
Run: python3 expert_loop.py
"""

import os
import json
import httpx
from dotenv import load_dotenv
from agent import run_agent

load_dotenv()

AGENT_KEY = os.getenv("AGENT_KEY", "")
API = os.getenv("AGENTHANSA_BASE", "https://www.agenthansa.com")
CURSOR_FILE = ".cursor"


def load_cursor() -> int:
    try:
        return int(open(CURSOR_FILE).read().strip())
    except Exception:
        return 0


def save_cursor(c: int):
    open(CURSOR_FILE, "w").write(str(c))


def reply(http: httpx.Client, engagement_id: str, body: str):
    http.post(
        f"{API}/api/engagements/{engagement_id}/messages",
        headers={"Authorization": f"Bearer {AGENT_KEY}", "Content-Type": "application/json"},
        json={"body": body},
    )


def main():
    print("LeadForge expert loop started — waiting for tasks...")
    headers = {"Authorization": f"Bearer {AGENT_KEY}"}
    cursor = load_cursor()

    with httpx.Client(timeout=70) as http:
        while True:
            try:
                r = http.get(
                    f"{API}/api/experts/updates",
                    params={"offset": cursor, "wait": 60},
                    headers=headers,
                )
                data = r.json()
                messages = data.get("messages", [])

                for msg in messages:
                    eid = msg["engagement_id"]
                    body = msg["body"]
                    sender = msg.get("sender_type", "unknown")
                    print(f"\n[{sender}] engagement={eid}: {body[:120]}")

                    if sender == "merchant":
                        # Accept engagement and run agent
                        http.post(f"{API}/api/engagements/{eid}/accept", headers=headers)
                        print("  -> Accepted. Running LeadForge agent...")

                        result = run_agent(task=body, task_id=eid)
                        response_text = next(
                            (b.text for b in result.content if hasattr(b, "text")), "Task complete."
                        )

                        # Submit deliverable
                        http.post(
                            f"{API}/api/engagements/{eid}/deliverable",
                            headers={**headers, "Content-Type": "application/json"},
                            json={"body": response_text},
                        )
                        reply(http, eid, f"Task complete. Deliverable submitted:\n\n{response_text[:500]}")
                        print("  -> Deliverable submitted.")

                cursor = data.get("cursor", cursor)
                save_cursor(cursor)

            except httpx.TimeoutException:
                pass  # normal for long-poll, just retry
            except Exception as e:
                print(f"[error] {e}")


if __name__ == "__main__":
    main()
