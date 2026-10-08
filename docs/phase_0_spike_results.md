# Phase 0 Spike Results & Verification Summary

Date: October 2026

## 1. Spike A: Gemini Chat & Embeddings
- **Script**: `scripts/spikes/verify_gemini.py`
- **Embedding Model**: `gemini-embedding-001` configured to 768 output dimensions (MRL reduction).
- **Chat Model**: Pinned in `.env` as `GEMINI_MODEL=gemini-2.5-flash` (or successor flash model). Note: Never hardcode model strings in application logic; keep in `.env` to allow seamless updates.
- **Normalization**: Vector outputs are L2 normalized prior to storage in pgvector table `kb_chunks`.
- **Status**: Verification script ready. Operates against `GEMINI_API_KEY`.

## 2. Spike B: HubSpot Private App Token
- **Script**: `scripts/spikes/verify_hubspot.py`
- **Authentication**: Private App Token (or Service Key) passed via `Authorization: Bearer <TOKEN>`.
- **Custom Properties (≤ 6 limit)**:
  1. `customer_tier` (Contact property)
  2. `ai_intent` (Ticket property)
  3. `ai_priority_score` (Ticket property)
  4. `ai_tier` (Ticket property)
  5. `ai_summary` (Ticket property)
  6. `sla_due_at` (Ticket property)
- **Status**: Verification script ready. Validates contact reads and detects presence of ticket properties.

## 3. Spike C: Gmail OAuth Lifetime & Delivery
- **Documentation**: `scripts/spikes/verify_gmail.md`
- **Risk**: Google Cloud OAuth Consent Screen in "Testing" mode causes tokens to expire after 7 days, halting n8n triggers.
- **Resolution**:
  - Primary recommendation: Publish app to "In Production" (Personal/External) to avoid 7-day expiration.
  - Development alternative: Use Google App Password with IMAP/SMTP nodes in n8n for guaranteed stability during local development and testing.

## 4. Spike D: Slack Incoming Webhook
- **Script**: `scripts/spikes/verify_slack.py`
- **Payload**: Rich Block Kit message containing customer tier, escalation score breakdown, SLA target, and direct action link to the Streamlit ops dashboard.
- **Status**: Verification script ready.
