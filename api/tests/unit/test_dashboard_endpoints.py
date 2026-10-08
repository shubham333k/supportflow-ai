"""
Unit tests for Dashboard endpoints:
- GET /api/v1/tickets/{id} enriched with customer, messages, analysis, draft, sla_timer
- POST /api/v1/tickets/{id}/approve
- POST /api/v1/tickets/{id}/sent
- GET /api/v1/analytics/overview
- GET /api/v1/analytics/trends
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from api.app.main import app
from api.app.models.base import Base
from api.app.models.database import get_db

HEADERS = {"X-API-Key": "dev-supportflow-api-key-change-me"}


class TestDashboardEndpoints:
    @pytest.fixture
    async def client(self):
        engine = create_async_engine(
            "sqlite+aiosqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        session_maker = async_sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )

        async def override():
            async with session_maker() as s:
                try:
                    yield s
                    await s.commit()
                except Exception:
                    await s.rollback()
                    raise

        prev = app.dependency_overrides.get(get_db)
        app.dependency_overrides[get_db] = override
        test_client = TestClient(app)
        yield test_client
        if prev is not None:
            app.dependency_overrides[get_db] = prev
        else:
            app.dependency_overrides.pop(get_db, None)

    @pytest.mark.asyncio
    async def test_enriched_ticket_detail_and_approval(self, client):
        # 1. Ingest a test ticket
        ingest_payload = {
            "channel": "email",
            "external_message_id": "dash-test-msg-001",
            "thread_id": "dash-thread-001",
            "from_email": "jane.pro@example.com",
            "from_name": "Jane Pro",
            "subject": "Need help with annual invoice",
            "body": "Can someone please clarify how to download our annual invoice?",
        }
        res_ingest = client.post(
            "/api/v1/messages/ingest", json=ingest_payload, headers=HEADERS
        )
        assert res_ingest.status_code == 200
        ticket_id = res_ingest.json()["ticket_id"]

        # 2. Analyze ticket
        res_analyze = client.post(
            f"/api/v1/tickets/{ticket_id}/analyze", headers=HEADERS
        )
        assert res_analyze.status_code == 200

        # 3. Draft reply
        res_draft = client.post(
            f"/api/v1/tickets/{ticket_id}/draft", headers=HEADERS
        )
        assert res_draft.status_code == 200

        # 4. Fetch enriched ticket detail
        res_detail = client.get(f"/api/v1/tickets/{ticket_id}", headers=HEADERS)
        assert res_detail.status_code == 200
        data = res_detail.json()
        assert data["id"] == ticket_id
        assert data["customer"] is not None
        assert data["customer"]["email"] == "jane.pro@example.com"
        assert len(data["messages"]) >= 1
        assert data["latest_analysis"] is not None
        assert data["latest_analysis"]["tier"] is not None
        assert data["latest_draft"] is not None
        assert data["sla_timer"] is not None
        assert len(data["audit_events"]) >= 1

        # 5. Approve draft with custom human edit
        approve_payload = {
            "edited_body": "Hello Jane,\n\nYou can download invoices from Settings > Billing. Let us know if you need anything else!\nBest,\nSupport Team",
            "agent_name": "agent:alice",
        }
        res_approve = client.post(
            f"/api/v1/tickets/{ticket_id}/approve",
            json=approve_payload,
            headers=HEADERS,
        )
        assert res_approve.status_code == 200
        appr_data = res_approve.json()
        assert appr_data["status"] == "ok"
        assert appr_data["ticket_status"] == "waiting_customer"
        assert "Hello Jane" in appr_data["reply_body"]

        # 6. Verify detail reflects approval and outbound message
        res_detail_after = client.get(f"/api/v1/tickets/{ticket_id}", headers=HEADERS)
        after_data = res_detail_after.json()
        assert after_data["status"] == "waiting_customer"
        assert len(after_data["messages"]) == 2  # 1 inbound + 1 outbound
        assert after_data["latest_draft"]["status"] == "edited_sent"

    @pytest.mark.asyncio
    async def test_analytics_overview_and_trends(self, client):
        # 1. Fetch overview
        res_ov = client.get("/api/v1/analytics/overview", headers=HEADERS)
        assert res_ov.status_code == 200
        ov_data = res_ov.json()
        assert "total_tickets" in ov_data
        assert "open_tickets" in ov_data
        assert "escalated_tickets" in ov_data
        assert "ai_resolved_tickets" in ov_data
        assert "sla_at_risk_count" in ov_data
        assert "avg_first_response_min" in ov_data

        # 2. Fetch trends
        res_tr = client.get("/api/v1/analytics/trends", headers=HEADERS)
        assert res_tr.status_code == 200
        tr_data = res_tr.json()
        assert "intent_distribution" in tr_data
        assert "sentiment_distribution" in tr_data
        assert "tier_distribution" in tr_data
        assert "status_distribution" in tr_data
        assert "escalation_rate_pct" in tr_data
        assert "ai_resolution_rate_pct" in tr_data
        assert "sla_breach_rate_pct" in tr_data
        assert "crm_sync_success_rate_pct" in tr_data
