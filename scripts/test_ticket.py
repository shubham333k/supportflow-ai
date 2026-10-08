"""
Interactive live test script for SupportFlow AI.
Ingests a sample ticket, runs AI triage & classification, and generates a grounded RAG draft.
"""

import sys
import httpx

if sys.stdout:
    sys.stdout.reconfigure(encoding="utf-8")

BASE_URL = "http://localhost:8000/api/v1"
HEADERS = {
    "X-API-Key": "dev-supportflow-api-key-change-me",
    "Content-Type": "application/json",
}

def main():
    print("=" * 60)
    print("🚀 SupportFlow AI — Live Ticket Ingest & AI Triage Test")
    print("=" * 60)

    # 1. Ingest Inbound Email
    inbound_payload = {
        "channel": "email",
        "thread_id": "live-demo-thread-901",
        "external_message_id": "live-msg-901",
        "from_email": "alex.smith@enterprise.com",
        "from_name": "Alex Smith",
        "subject": "URGENT: Production database export failing with CSV error",
        "body": "Hi Support team, our production database export is throwing a timeout error when generating CSV files for our compliance audit. We need an immediate resolution.",
    }

    print("\n[Step 1] Ingesting message via POST /api/v1/messages/ingest ...")
    with httpx.Client(timeout=30.0) as client:
        res = client.post(f"{BASE_URL}/messages/ingest", json=inbound_payload, headers=HEADERS)
        if res.status_code != 200:
            print(f"❌ Ingestion Failed ({res.status_code}): {res.text}")
            return
        
        ingest_data = res.json()
        ticket_id = ingest_data["ticket_id"]
        print(f"✅ Ticket Ingested Successfully!")
        print(f"   • Ticket ID:    {ticket_id}")
        print(f"   • Customer ID:  {ingest_data['customer_id']}")
        print(f"   • Is Duplicate: {ingest_data['is_duplicate']}")
        print(f"   • Is Reopen:    {ingest_data['is_reopen']}")

        # 2. AI Triage & Classification
        print(f"\n[Step 2] Running AI Triage via POST /api/v1/tickets/{ticket_id}/analyze ...")
        res_analyze = client.post(f"{BASE_URL}/tickets/{ticket_id}/analyze", headers=HEADERS)
        if res_analyze.status_code != 200:
            print(f"❌ Analysis Failed ({res_analyze.status_code}): {res_analyze.text}")
            return

        analyze_data = res_analyze.json()
        print(f"✅ AI Analysis Completed!")
        print(f"   • Priority Tier:     {analyze_data['tier'].upper()}")
        print(f"   • Escalation Score:  {analyze_data['score']}/100")
        print(f"   • Intent Detected:   {analyze_data.get('intent')}")
        print(f"   • Hard Rule Hits:    {analyze_data.get('hard_rule_hits')}")

        # 3. RAG Grounding & Draft Generation
        print(f"\n[Step 3] Generating RAG Grounded Draft via POST /api/v1/tickets/{ticket_id}/draft ...")
        res_draft = client.post(f"{BASE_URL}/tickets/{ticket_id}/draft", headers=HEADERS)
        if res_draft.status_code != 200:
            print(f"❌ Drafting Failed ({res_draft.status_code}): {res_draft.text}")
            return

        draft_data = res_draft.json()
        print(f"✅ Draft Generated!")
        print(f"   • Send Mode:         {draft_data.get('send_mode')}")
        print(f"   • Verifier Passed:   {draft_data.get('verifier_passed')}")
        print(f"   • Cited Documents:   {draft_data.get('cited_docs')}")
        print(f"\n📝 Proposed AI Response:\n{'-'*50}\n{draft_data.get('reply')}\n{'-'*50}")

    print("\n🎉 Live pipeline test completed successfully! Check the dashboard at http://localhost:8501 to see the ticket.")

if __name__ == "__main__":
    main()
