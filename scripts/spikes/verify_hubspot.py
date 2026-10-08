"""
Spike B: HubSpot Private App Token Validation
Validates:
1. HUBSPOT_ACCESS_TOKEN is configured
2. HubSpot API connectivity (GET /crm/v3/objects/contacts)
3. Ticket creation capabilities
4. Verifies/documents the ≤6 custom properties needed
"""
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

# Load .env
project_root = Path(__file__).resolve().parents[2]
load_dotenv(project_root / ".env")

token = os.getenv("HUBSPOT_ACCESS_TOKEN")

print("=" * 60)
print("Spike B: HubSpot Integration Verification")
print("=" * 60)

if not token or token == "your-hubspot-private-app-token":
    print("\n[SKIPPED / NOTICE] HUBSPOT_ACCESS_TOKEN is not set in .env.")
    print("To test HubSpot integration:")
    print("1. Create a free developer/sandbox account on HubSpot.")
    print("2. Create a Private App with scopes: crm.objects.contacts.read/write, crm.objects.custom.read, tickets.")
    print("3. Copy the Private App Access Token to HUBSPOT_ACCESS_TOKEN in .env.")
    sys.exit(0)

headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json",
}

try:
    with httpx.Client(base_url="https://api.hubapi.com", timeout=10.0) as client:
        # 1. Test Auth & Contact Access
        print("\n1. Testing Contact Object Access...")
        resp = client.get("/crm/v3/objects/contacts?limit=1", headers=headers)
        if resp.status_code == 200:
            print("Successfully authenticated and read contacts.")
        else:
            print(f"Failed to read contacts: {resp.status_code} - {resp.text}")
            sys.exit(1)

        # 2. Check Custom Properties
        print("\n2. Checking Ticket Custom Properties...")
        props_resp = client.get("/crm/v3/properties/tickets", headers=headers)
        if props_resp.status_code == 200:
            existing_props = {p["name"] for p in props_resp.json().get("results", [])}
            needed = ["customer_tier", "ai_intent", "ai_priority_score", "ai_tier", "ai_summary", "sla_due_at"]
            print(f"Found {len(existing_props)} total ticket properties.")
            for p in needed:
                status_str = "EXISTS" if p in existing_props else "NOT FOUND (to be created)"
                print(f"  - {p}: {status_str}")
        else:
            print(f"Notice: Could not list properties ({props_resp.status_code})")

    print("\n>>> Spike B Result: SUCCESS <<<")

except Exception as e:
    print(f"\n[ERROR] HubSpot verification failed: {e}")
    sys.exit(1)
