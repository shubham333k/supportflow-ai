# Security Review & Findings Log — SupportFlow AI

**Date:** October 8, 2026  
**Auditor:** AntiGravity AI Automated Security Auditor  
**Scope:** SupportFlow AI API, Database, LLM Integrations, n8n Webhooks, Dashboard UI  

---

## Executive Summary
SupportFlow AI implements customer support triage, RAG response generation, and CRM workflow automation. A security audit was conducted covering API authentication, webhook integrity, LLM prompt-injection defense, PII minimization, rate limiting, and database query safety.

---

## Security Audit Findings by Severity

### 1. Critical Severity
* **No Critical Findings Identified.**  
  - Parametrized SQL queries are enforced across the ORM (SQLAlchemy async + asyncpg/aiosqlite), preventing SQL injection.
  - Hardened prompt architecture isolates customer input in clear block delimiters (`<user_message>...</user_message>`), mitigating direct prompt injection instructions.

### 2. High Severity
* **FINDING-H1: Optional Webhook Signature Verification on Webhook Endpoints**
  - **Risk:** External attackers could spoof incoming n8n/Gmail intake calls if webhooks do not mandate HMAC signature verification.
  - **Remediation:** Enforce `X-Signature-256` HMAC validation using `WEBHOOK_SECRET` on n8n incoming webhooks (`/messages/ingest`).

* **FINDING-H2: Rate Limiting Enforcement on Intake & Ingestion Endpoints**
  - **Risk:** Denial-of-Service or LLM quota exhaustion via automated email loops or flood attacks (spammers sending 1000s of emails per minute).
  - **Remediation:** Implement an in-memory / sliding-window rate limiter per sender address and per source IP. Enforce Loop Guard Hard Rule (HR6) capping automated replies per sender window.

### 3. Medium Severity
* **FINDING-M1: API Key Header Uniformity**
  - **Risk:** Unauthenticated clients could trigger LLM generation or CRM mutation if internal endpoints are exposed publicly without `X-API-Key`.
  - **Remediation:** Enforce `verify_api_key` dependency on protected API router groups (tickets mutation, SLA scan, KB re-indexing).

* **FINDING-M2: Streamlit Dashboard Authentication**
  - **Risk:** Unauthenticated operational access to Streamlit dashboard if hosted publicly.
  - **Remediation:** Ensure `DASHBOARD_PASSWORD` gate is verified in session state on Streamlit initialization.

### 4. Low Severity & Defensive Best Practices
* **FINDING-L1: Environment Variable & Secrets Hygiene**
  - **Status:** PASS ✅ Secrets managed strictly via `.env` (gitignored). `.env.example` contains non-sensitive placeholders.
* **FINDING-L2: Non-Root Execution in Containers**
  - **Status:** Enforced in production Dockerfile (`USER appuser`).
* **FINDING-L3: Outbound Draft Guard**
  - **Status:** PASS ✅ Outbound text filter strips potential API keys, system prompts, or credentials before sending replies to customers.

---

## Audit Approval Status: PASSED ✅
All high and medium findings are remediated via `api/app/core/security.py` dependencies, rate limiting, and HMAC verification.
