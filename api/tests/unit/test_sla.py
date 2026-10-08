"""
Unit tests for SLA timer lifecycle, scheduled scan, warnings, and breach escalation.
Sections 7.2, 10.2, and Phase 4 requirements.
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from api.app.main import app
from api.app.models.base import Base
from api.app.models.database import get_db
from api.app.models.tables import SLATimer, Ticket
from api.app.services.sla import (
    scan_sla_timers,
    start_or_update_sla_timer,
    stop_sla_timer,
)

HEADERS = {"X-API-Key": "dev-supportflow-api-key-change-me"}


class TestSLATimerLifecycle:
    """Validate timer creation, updates, and stopping."""

    @pytest.fixture
    async def db_session(self):
        engine = create_async_engine(
            "sqlite+aiosqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with session_maker() as db:
            yield db

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)

    @pytest.mark.asyncio
    async def test_start_timer_immediate_tier_due_in_1_hour(self, db_session):
        tid = uuid4()
        timer = await start_or_update_sla_timer(db_session, tid, tier="immediate")
        assert timer.tier == "immediate"
        # Due in approx 1 hour (3600 seconds)
        diff = (timer.due_at - timer.started_at).total_seconds()
        assert 3500 <= diff <= 3700

    @pytest.mark.asyncio
    async def test_start_timer_priority_tier_due_in_4_hours(self, db_session):
        tid = uuid4()
        timer = await start_or_update_sla_timer(db_session, tid, tier="priority")
        assert timer.tier == "priority"
        diff = (timer.due_at - timer.started_at).total_seconds()
        assert 14300 <= diff <= 14500

    @pytest.mark.asyncio
    async def test_stop_sla_timer(self, db_session):
        tid = uuid4()
        await start_or_update_sla_timer(db_session, tid, tier="ai_assisted")
        stopped = await stop_sla_timer(db_session, tid)
        assert stopped is True


class TestSLAScheduledScan:
    """Validate 50%, 90% warnings, breach escalation, and ticket tier promotion."""

    @pytest.fixture
    async def db_session(self):
        engine = create_async_engine(
            "sqlite+aiosqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with session_maker() as db:
            yield db

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)

    @pytest.mark.asyncio
    async def test_scan_triggers_50_warning(self, db_session):
        tid = uuid4()
        now = datetime.now(UTC)
        # Timer started 60 min ago, due in 40 min -> total 100 min, elapsed 60 min (60% -> 50% warning)
        timer = SLATimer(
            ticket_id=tid,
            tier="priority",
            started_at=now - timedelta(minutes=60),
            due_at=now + timedelta(minutes=40),
        )
        db_session.add(timer)
        await db_session.flush()

        summary = await scan_sla_timers(db_session)
        assert tid in summary.warnings_50
        assert timer.warned_50_at is not None

    @pytest.mark.asyncio
    async def test_scan_triggers_90_warning_and_escalates_ticket(self, db_session):
        tid = uuid4()
        ticket = Ticket(
            id=tid,
            channel="email",
            subject="Slow issue",
            tier="automated",
            status="new",
        )
        db_session.add(ticket)

        now = datetime.now(UTC)
        # Started 95 min ago, due in 5 min -> elapsed 95% -> triggers 90% warning
        timer = SLATimer(
            ticket_id=tid,
            tier="ai_assisted",
            started_at=now - timedelta(minutes=95),
            due_at=now + timedelta(minutes=5),
        )
        db_session.add(timer)
        await db_session.flush()

        summary = await scan_sla_timers(db_session)
        assert tid in summary.warnings_90
        assert timer.warned_90_at is not None
        # Ticket promoted to priority
        assert ticket.tier == "priority"
        assert ticket.status == "pending_approval"

    @pytest.mark.asyncio
    async def test_scan_triggers_breach_when_past_due(self, db_session):
        tid = uuid4()
        now = datetime.now(UTC)
        # Due 10 minutes ago
        timer = SLATimer(
            ticket_id=tid,
            tier="immediate",
            started_at=now - timedelta(hours=2),
            due_at=now - timedelta(minutes=10),
        )
        db_session.add(timer)
        await db_session.flush()

        summary = await scan_sla_timers(db_session)
        assert tid in summary.breaches
        assert timer.breached_at is not None


class TestSLAEndpoints:
    """Validate POST /api/v1/sla/scan and GET /api/v1/sla/status/{ticket_id}."""

    @pytest.fixture
    async def client(self):
        engine = create_async_engine(
            "sqlite+aiosqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        async def override():
            async with session_maker() as s:
                try:
                    yield s
                    await s.commit()
                except Exception:
                    await s.rollback()
                    raise

        app.dependency_overrides[get_db] = override
        test_client = TestClient(app)
        yield test_client, session_maker
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_trigger_sla_scan_endpoint(self, client):
        test_client, _ = client
        resp = test_client.post("/api/v1/sla/scan", headers=HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "active_timers_scanned" in data

    @pytest.mark.asyncio
    async def test_get_ticket_sla_status_and_resolve(self, client):
        test_client, session_maker = client
        tid = uuid4()

        async with session_maker() as db:
            ticket = Ticket(id=tid, channel="email", status="new", tier="priority")
            db.add(ticket)
            await start_or_update_sla_timer(db, tid, "priority")
            await db.commit()

        # Check status endpoint
        resp = test_client.get(f"/api/v1/sla/status/{tid}", headers=HEADERS)
        assert resp.status_code == 200
        status_data = resp.json()
        assert status_data["ticket_id"] == str(tid)
        assert status_data["tier"] == "priority"
        assert status_data["remaining_seconds"] > 0
        assert status_data["is_breached"] is False

        # Resolve ticket via endpoint
        res_resp = test_client.post(f"/api/v1/tickets/{tid}/resolve", headers=HEADERS)
        assert res_resp.status_code == 200
        assert res_resp.json()["ticket_status"] == "resolved"

        # Timer stopped -> status should now return 404 (no active timer)
        post_resp = test_client.get(f"/api/v1/sla/status/{tid}", headers=HEADERS)
        assert post_resp.status_code == 404
