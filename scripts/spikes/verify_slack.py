"""
Spike D: Slack Incoming Webhook Verification
Validates:
1. SLACK_WEBHOOK_URL is configured
2. Dispatches a formatted Block Kit message simulating an urgent escalation alert
"""
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

# Load .env
project_root = Path(__file__).resolve().parents[2]
load_dotenv(project_root / ".env")

webhook_url = os.getenv("SLACK_WEBHOOK_URL")

print("=" * 60)
print("Spike D: Slack Incoming Webhook Verification")
print("=" * 60)

if not webhook_url or webhook_url.startswith("https://hooks.slack.com/services/YOUR"):
    print("\n[SKIPPED / NOTICE] SLACK_WEBHOOK_URL is not set in .env.")
    print("To test Slack alerts:")
    print("1. Go to https://api.slack.com/apps and create an App.")
    print("2. Enable Incoming Webhooks and add a new webhook to your test channel (e.g. #support-alerts).")
    print("3. Copy the URL to SLACK_WEBHOOK_URL in .env.")
    sys.exit(0)

# Build a Block Kit escalation payload
payload = {
    "blocks": [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "🚨 SupportFlow AI - High Priority Escalation (Spike Test)",
                "emoji": True
            }
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": "*Customer:*\nAcme Corp (Enterprise)"},
                {"type": "mrkdwn", "text": "*Score:*\n*96 / 100* (Immediate)"},
                {"type": "mrkdwn", "text": "*Intent:*\nbilling_issue"},
                {"type": "mrkdwn", "text": "*SLA Target:*\n1 hour"}
            ]
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "> *Summary:* Customer reported duplicate charge on subscription renewal. Third outreach."
            }
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "View Ticket in Ops Console"},
                    "url": "http://localhost:8501",
                    "style": "danger"
                }
            ]
        }
    ]
}

try:
    print("\nSending test Block Kit message to Slack webhook...")
    resp = httpx.post(webhook_url, json=payload, timeout=10.0)
    if resp.status_code == 200:
        print("Slack message dispatched successfully! Check your Slack channel.")
        print("\n>>> Spike D Result: SUCCESS <<<")
    else:
        print(f"Failed to post to Slack: {resp.status_code} - {resp.text}")
        sys.exit(1)
except Exception as e:
    print(f"\n[ERROR] Slack verification failed: {e}")
    sys.exit(1)
