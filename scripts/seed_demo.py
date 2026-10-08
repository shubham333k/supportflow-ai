"""
Seed demo tickets and knowledge base for SupportFlow AI.
Runs against the live or local FastAPI server to prepare scenarios A, B, C, D.
"""

import httpx

BASE_URL = "http://localhost:8000/api/v1"
HEADERS = {
    "X-API-Key": "dev-supportflow-api-key-change-me",
    "Content-Type": "application/json",
}

DEMO_SCENARIOS = [
    {
        "name": "Scenario A (Immediate Escalation)",
        "payload": {
            "channel": "email",
            "external_message_id": "seed-msg-scen-a",
            "thread_id": "seed-thread-scen-a",
            "from_email": "cto@acmecorp.com",
            "from_name": "Marcus Vance",
            "subject": "URGENT: Third time writing — double charge dispute",
            "body": "Third time I'm writing. We were double-charged on our enterprise invoice and nobody has replied in two days. Fix it today or we cancel our contract and dispute with our bank.",
        },
    },
    {
        "name": "Scenario B (Priority / Human Approval)",
        "payload": {
            "channel": "email",
            "external_message_id": "seed-msg-scen-b",
            "thread_id": "seed-thread-scen-b",
            "from_email": "sarah.finance@techstart.io",
            "from_name": "Sarah Jenkins",
            "subject": "Duplicate charge on our account",
            "body": "I was charged twice this month for our Pro plan subscription and I already contacted support yesterday but nobody has resolved it. Please help issue a refund.",
        },
    },
    {
        "name": "Scenario C (AI Assisted / Technical)",
        "payload": {
            "channel": "email",
            "external_message_id": "seed-msg-scen-c",
            "thread_id": "seed-thread-scen-c",
            "from_email": "dev.user@example.com",
            "from_name": "Alex Rivera",
            "subject": "CSV export failing on analytics dashboard",
            "body": "The CSV export keeps failing with an error 500 on our standard workspace and it's really annoying.",
        },
    },
    {
        "name": "Scenario D (Automated / Deflection)",
        "payload": {
            "channel": "email",
            "external_message_id": "seed-msg-scen-d",
            "thread_id": "seed-thread-scen-d",
            "from_email": "dave.smith@company.org",
            "from_name": "Dave Smith",
            "subject": "Switching from monthly to annual billing",
            "body": "How do I switch our current monthly plan to annual billing to get the discount?",
        },
    },
]


def seed_demo_data():
    with httpx.Client(base_url=BASE_URL, headers=HEADERS, timeout=30.0) as client:
        print("1. Ingesting Knowledge Base...")
        try:
            res_kb = client.post("/kb/ingest")
            print(f"   KB Ingest: {res_kb.status_code} - {res_kb.json()}")
        except Exception as e:
            print(f"   KB Ingest skipped/failed: {e}")

        print("\n2. Ingesting and analyzing demo scenarios...")
        for sc in DEMO_SCENARIOS:
            print(f"\n-> Seeding {sc['name']}...")
            try:
                res_ingest = client.post("/messages/ingest", json=sc["payload"])
                if res_ingest.status_code == 200:
                    ticket_id = res_ingest.json()["ticket_id"]
                    print(f"   Ticket Created: {ticket_id}")

                    # Run analyze
                    res_an = client.post(f"/tickets/{ticket_id}/analyze")
                    if res_an.status_code == 200:
                        an_data = res_an.json()
                        print(f"   Analyzed: Tier={an_data['tier']}, Score={an_data['score']}, Rules={an_data['hard_rule_hits']}")

                    # Run draft
                    res_dr = client.post(f"/tickets/{ticket_id}/draft")
                    if res_dr.status_code == 200:
                        dr_data = res_dr.json()
                        print(f"   Draft Generated: Mode={dr_data['send_mode']}, Verifier={dr_data['verifier_passed']}")
                else:
                    print(f"   Ingest failed: {res_ingest.status_code} - {res_ingest.text}")
            except Exception as e:
                print(f"   Error: {e}")

        print("\nDemo seed completed successfully!")


if __name__ == "__main__":
    seed_demo_data()
