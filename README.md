<div align="center">

# 🤖 SupportFlow-AI

### *Intelligent Customer Support & CRM Automation Platform*

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.40+-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)](https://streamlit.io)
[![Google Gemini](https://img.shields.io/badge/Google_Gemini-2.5_Flash-FF6D00?style=for-the-badge&logo=google&logoColor=white)](https://ai.google.dev)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-pgvector-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)](https://www.postgresql.org)
[![HubSpot](https://img.shields.io/badge/HubSpot-CRM_Sync-FF7A59?style=for-the-badge&logo=hubspot&logoColor=white)](https://hubspot.com)
[![n8n](https://img.shields.io/badge/n8n-Orchestration-EA4B71?style=for-the-badge&logo=n8n&logoColor=white)](https://n8n.io)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://docker.com)
[![Tests](https://img.shields.io/badge/Tests-95_Passing-4CAF50?style=for-the-badge&logo=pytest&logoColor=white)](#)
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)

**An enterprise-grade AI customer support triage, escalation, and CRM automation system.**
**Classifies inbound emails via a deterministic 7-factor escalation engine with hard safety rules,**
**drafts RAG-grounded replies from a vector knowledge base, and syncs everything bidirectionally with HubSpot CRM — fully automated, fail-safe, and auditable.**

---

</div>

## 📋 Table of Contents

- [Overview](#-overview)
- [Key Features](#-key-features)
- [Architecture](#-architecture)
- [Tech Stack](#-tech-stack)
- [Project Structure](#-project-structure)
- [Quick Start (Docker)](#-quick-start-docker)
- [Local Development](#-local-development)
- [API Reference](#-api-reference)
- [Highlights](#-highlights)
- [Security & System Integrity](#-security--system-integrity)
- [Contributing](#-contributing)
- [License](#-license)

---

## 🌟 Overview

SupportFlow-AI is a production-ready AI platform that fully automates the customer support lifecycle — from inbound email ingestion to CRM sync. It is designed around a single principle: **Fail Safe, Never Fail Open**.

✅ **7-Factor Escalation Engine** — Deterministic, config-driven scoring across tier, urgency, sentiment, send-mode, escalation keywords, loop-guard, and SLA breach
✅ **RAG-Grounded Replies** — Gemini 2.5 Flash retrieves relevant KB articles via pgvector and drafts context-aware responses
✅ **Hard Safety Rules** — No automated reply is ever dispatched unless explicitly approved; AI failures always escalate to human review
✅ **Full HubSpot Sync** — Contacts and tickets created/updated bidirectionally; permanent client errors (401/403/404) never block the pipeline
✅ **n8n Workflow Orchestration** — Gmail polling, Slack notifications, email delivery, and webhook intake — with zero business logic in n8n
✅ **Streamlit Ops Console** — Real-time dashboard for ticket triage, KB management, analytics, and system configuration
✅ **95-Test Suite** — Unit, API, golden-set, and integration tests covering every engine path

---

## ✨ Key Features

| Feature | Description |
|---------|-------------|
| 🎯 **AI Triage & Classification** | Gemini 2.5 Flash classifies every ticket by intent, sentiment, urgency, and language with structured Pydantic output |
| ⚡ **7-Factor Escalation Engine** | Deterministic YAML-config scoring pipeline — no LLM in the escalation path |
| 🛡️ **Hard Safety Rules** | Blocklist keywords trigger immediate human escalation regardless of score |
| 🔍 **RAG Knowledge Base** | pgvector semantic search over KB articles; every draft is grounded with source citations |
| 📝 **AI Reply Drafting** | Structured multi-step LLM pipeline: classify → retrieve → draft → validate |
| 🔄 **HubSpot CRM Sync** | Async bidirectional sync; smart retry skips permanent 4xx errors |
| 🔔 **Slack Notifications** | Real-time alerts for escalations, SLA breaches, and critical events |
| 📧 **n8n Email Orchestration** | Gmail polling, approval flows, and delivery — orchestrated via n8n webhooks |
| 🔁 **Loop Guard** | Detects and breaks automated reply loops before they escalate |
| 📊 **SLA Management** | Automated SLA tracking with configurable tier-based thresholds |
| 🖥️ **Streamlit Ops Console** | Full-featured dashboard: ticket browser, KB editor, analytics, settings |
| 🐳 **Docker Compose Stack** | One-command full-stack launch: API + PostgreSQL + n8n + Dashboard |

---

## 🏗️ Architecture

```
                     ┌─────────────────────────────────┐
                     │        n8n Orchestration         │
                     │  Gmail Poll → Webhook → Slack    │
                     │  Email Delivery → Approval Flow  │
                     └────────────────┬────────────────┘
                                      │  HTTP Webhook
                     ┌────────────────▼────────────────┐
                     │          FastAPI Engine           │
                     │  ┌──────────────────────────┐   │
                     │  │   7-Factor Escalation    │   │
                     │  │   Engine (YAML Config)   │   │
                     │  └──────────┬───────────────┘   │
                     │             │                    │
                     │  ┌──────────▼───────────────┐   │
                     │  │  Gemini 2.5 Flash (LLM)  │   │
                     │  │  Classify → RAG → Draft  │   │
                     │  └──────────┬───────────────┘   │
                     │             │                    │
                     │  ┌──────────▼───────────────┐   │
                     │  │  pgvector RAG Knowledge  │   │
                     │  │  Base (Semantic Search)  │   │
                     │  └──────────────────────────┘   │
                     └────────────────┬────────────────┘
                                      │
          ┌───────────────────────────┼─────────────────────────┐
          │                           │                         │
┌─────────▼──────────┐  ┌────────────▼──────────┐  ┌──────────▼──────────┐
│ PostgreSQL+pgvector│  │   HubSpot CRM Sync    │  │  Streamlit Console  │
│ Tickets · KB · SLA │  │  Contacts + Tickets   │  │   Ops Dashboard     │
└────────────────────┘  └───────────────────────┘  └─────────────────────┘
```

---

## 🛠️ Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **AI / LLM** | Google Gemini 2.5 Flash | Classification, RAG drafting, structured output |
| **Embeddings** | Gemini Embedding 001 | KB article vectorization for semantic search |
| **API Backend** | FastAPI + Uvicorn | Decision service, REST API, async SQLAlchemy |
| **Database** | PostgreSQL + pgvector | Tickets, KB, SLA state, vector embeddings |
| **Orchestration** | n8n | Email intake, approval flows, Slack notifications |
| **CRM** | HubSpot API | Bidirectional contact & ticket sync |
| **Dashboard** | Streamlit | Ops console — tickets, KB, analytics, settings |
| **Containerization** | Docker Compose | Full-stack local & production deployment |
| **Validation** | Pydantic v2 | Request/response schemas, structured LLM output |
| **Migrations** | Alembic | Database schema management |
| **Testing** | pytest + httpx | 95-test suite: unit, API, golden, integration |

---

## 📂 Project Structure

```
supportflow-ai/
├── api/                          # FastAPI decision service
│   ├── app/
│   │   ├── core/                 # Config, security, logging
│   │   ├── routers/              # messages, tickets, kb, sla, analytics, health
│   │   ├── services/             # classifier, escalation, rag, drafting, sla, loop_guard
│   │   ├── integrations/         # llm.py, crm_base.py, hubspot.py
│   │   ├── models/               # SQLAlchemy async models
│   │   ├── schemas/              # Pydantic v2 schemas
│   │   └── prompts/              # Versioned prompt templates
│   ├── config/
│   │   └── escalation.yaml       # 7-factor engine config & hard rules
│   ├── Dockerfile
│   └── tests/                    # unit/, api/, golden/, integration/
├── dashboard/                    # Streamlit Ops Console
│   ├── app.py                    # Main dashboard entrypoint
│   ├── pages/                    # 1_Overview, 2_Tickets, 3_KB, 4_Analytics, 5_Settings
│   ├── api_client.py             # HTTP client for FastAPI backend
│   ├── ui_components.py          # Shared UI widgets & badges
│   └── Dockerfile
├── kb/                           # Seed knowledge base markdown articles
├── eval/                         # Evaluation sets & run_eval.py
├── n8n/
│   └── workflows/                # main, approve_send, scheduler, error_handler
├── scripts/
│   ├── seed_demo.py              # Seeds 12 KB articles + demo tickets
│   ├── failure_drills.py         # 4-scenario resilience tests
│   └── spikes/                   # Phase 0 integration verification
├── docs/                         # Architecture & design documentation
├── .github/workflows/ci.yml      # GitHub Actions CI pipeline
├── .env.example                  # Environment variable template
├── docker-compose.yml            # Multi-service local stack
├── pyproject.toml                # Project metadata & dependencies
└── pytest.ini                    # Test configuration
```

---

## 🚀 Quick Start (Docker)

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running
- API keys: Google Gemini, HubSpot (optional), Slack webhook (optional)

### Step 1: Clone the Repository

```bash
git clone https://github.com/shubham333k/supportflow-ai.git
cd supportflow-ai
```

### Step 2: Configure Environment

```bash
cp .env.example .env
```

Edit `.env` and fill in your API keys:

```env
GEMINI_API_KEY=your_gemini_api_key_here
API_KEY=your_chosen_api_key_for_fastapi
HUBSPOT_ACCESS_TOKEN=your_hubspot_token_here     # Optional
SLACK_WEBHOOK_URL=your_slack_webhook_url_here    # Optional
```

### Step 3: Launch the Full Stack

```bash
docker compose up -d
```

### Step 4: Seed Demo Data

```bash
docker compose exec api python scripts/seed_demo.py
```

### Default Service URLs

| Service | URL | Description |
|---------|-----|-------------|
| FastAPI Docs | http://localhost:8000/docs | Interactive API documentation |
| Health Check | http://localhost:8000/healthz | System health status |
| Streamlit Console | http://localhost:8501 | Ops dashboard |
| n8n Editor | http://localhost:5678 | Workflow orchestration |

---

## 💻 Local Development

### Backend (FastAPI)

```bash
# Create virtual environment
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS/Linux

# Install dependencies
pip install -e ".[dev]"

# Apply database migrations
alembic upgrade head

# Seed demo data
python scripts/seed_demo.py

# Start API server
python -m uvicorn api.app.main:app --port 8000 --reload
```

### Dashboard (Streamlit)

```bash
# In a separate terminal (with .venv activated)
python -m streamlit run dashboard/app.py --server.port 8501
```

### Run Tests

```bash
# Full test suite (95 tests)
pytest

# With coverage report
pytest --cov=api --cov-report=term-missing

# Run failure drills
python scripts/failure_drills.py
```

---

## 📡 API Reference

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| `POST` | `/api/v1/messages/ingest` | Ingest inbound email/webhook, trigger triage | ✅ |
| `GET` | `/api/v1/tickets` | List tickets with filters (status, priority, tier) | ✅ |
| `GET` | `/api/v1/tickets/{id}` | Get full ticket detail with AI classification | ✅ |
| `POST` | `/api/v1/tickets/{id}/escalate` | Manually escalate a ticket | ✅ |
| `POST` | `/api/v1/tickets/{id}/resolve` | Resolve a ticket | ✅ |
| `POST` | `/api/v1/tickets/{id}/draft` | Generate AI reply draft with RAG | ✅ |
| `GET` | `/api/v1/kb` | List knowledge base articles | ✅ |
| `POST` | `/api/v1/kb` | Create KB article (auto-embeds) | ✅ |
| `POST` | `/api/v1/kb/search` | Semantic search over KB (pgvector) | ✅ |
| `GET` | `/api/v1/sla/status` | Current SLA status & breach alerts | ✅ |
| `GET` | `/api/v1/analytics/overview` | System-wide metrics & ticket stats | ✅ |
| `GET` | `/healthz` | Service health check | ❌ |

> **Authentication**: All protected endpoints require `X-API-Key` header matching your configured `API_KEY`.

---

## 🔥 Highlights

- **Deterministic Escalation** — The 7-factor engine runs entirely in Python with a YAML config; no LLM is in the escalation decision path, ensuring predictable, auditable routing
- **Fail-Safe Design** — Any AI or RAG failure automatically escalates to `priority` human review; unverified automated replies are never dispatched
- **Loop Guard** — Detects email loop patterns (auto-reply chains) and breaks them before they create runaway threads
- **Smart HubSpot Sync** — Async CRM sync with intelligent retry: permanent client errors (401/403/404) are classified as non-retryable, preventing pipeline hangs
- **Structured LLM Output** — All Gemini calls use Pydantic v2 models as output schemas, ensuring type-safe, validated AI responses
- **pgvector RAG** — Knowledge base articles are chunked, embedded via Gemini Embedding 001, and stored in PostgreSQL pgvector for sub-50ms semantic retrieval
- **95-Test Suite** — Comprehensive coverage: unit tests for every service, API integration tests, golden-set regression tests, and failure drill scenarios

---

## 🔒 Security & System Integrity

- 🛡️ **API Key Authentication** — All FastAPI endpoints protected via `X-API-Key` header; no unauthenticated writes
- 🚫 **Hard Safety Rules** — Keyword blocklist triggers immediate human escalation regardless of AI classification score
- 🔒 **Secret Management** — All credentials via `.env` file; `.env` is gitignored and never committed
- 🔄 **Retry Safety** — HubSpot sync distinguishes transient vs. permanent errors; 401/403/404 are never retried
- 📋 **Audit Trail** — Every ticket state transition, escalation decision, and CRM sync is logged with timestamps
- 🌐 **Webhook Validation** — Inbound webhooks validated via HMAC signature (configurable `WEBHOOK_SECRET`)
- 🐳 **Container Isolation** — Docker Compose network isolates services; database is not exposed externally by default

---

## 🤝 Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature-name`
3. Make your changes with tests
4. Run the test suite: `pytest`
5. Submit a pull request with a clear description

### Code Style

```bash
# Lint with ruff
ruff check .

# Format
ruff format .
```

---

## 📄 License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

> **Disclaimer**: This project is for demonstration and educational purposes. SupportFlow-AI is a portfolio project showcasing AI-powered enterprise automation patterns.

---

<div align="center">

Built with ❤️ by [Shubham](https://github.com/shubham333k)

⭐ If you found this project useful, please give it a star!

**[🐛 Report Bug](https://github.com/shubham333k/supportflow-ai/issues)** · **[✨ Request Feature](https://github.com/shubham333k/supportflow-ai/issues)** · **[📖 View Docs](https://github.com/shubham333k/supportflow-ai/wiki)**

</div>
