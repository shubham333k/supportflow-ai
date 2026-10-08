"""
Phase 1 tests for message ingestion — idempotency, reopen, and stubs.

Uses an in-memory SQLite DB with async override for fast tests
without needing a running PostgreSQL instance.
"""

import asyncio
import json
import sqlite3
import uuid

import pytest
from fastapi.testclient import TestClient
from pgvector.sqlalchemy import Vector
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.pool import StaticPool

from api.app.main import app
from api.app.models.base import Base
from api.app.models.database import get_db
from api.app.models.tables import Ticket

# Register SQLite adapters for Python list, dict, and UUID
sqlite3.register_adapter(list, json.dumps)
sqlite3.register_adapter(dict, json.dumps)
sqlite3.register_adapter(uuid.UUID, lambda u: str(u))

# SQLite custom compilations for Postgres-specific types
@compiles(ARRAY, "sqlite")
def compile_array_sqlite(type_, compiler, **kw):
    return "TEXT"

@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return "TEXT"

@compiles(PG_UUID, "sqlite")
def compile_uuid_sqlite(type_, compiler, **kw):
    return "TEXT"

@compiles(Vector, "sqlite")
def compile_vector_sqlite(type_, compiler, **kw):
    return "BLOB"

# ── Test DB setup (Async SQLite in-memory) ────────────────────────────

async_engine = create_async_engine(
    "sqlite+aiosqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestAsyncSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def override_get_db():
    async with TestAsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


app.dependency_overrides[get_db] = override_get_db


def run_async(coro):
    return asyncio.run(coro)


API_KEY = "dev-supportflow-api-key-change-me"
HEADERS = {"X-API-Key": API_KEY}

client = TestClient(app)


# ── Fixtures ───────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def setup_db():
    """Create tables before each test, drop after."""
    async def _init():
        async with async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def _cleanup():
        async with async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)

    run_async(_init())
    yield
    run_async(_cleanup())


def _ingest_payload(**overrides):
    """Generate a standard ingest payload with optional overrides."""
    defaults = {
        "channel": "email",
        "external_message_id": f"msg-{uuid.uuid4().hex[:8]}",
        "thread_id": f"thread-{uuid.uuid4().hex[:8]}",
        "from_email": "customer@example.com",
        "from_name": "Test Customer",
        "subject": "Help with billing",
        "body": "I was charged twice for my subscription this month.",
    }
    defaults.update(overrides)
    return defaults


# ── Tests ──────────────────────────────────────────────────────────────

class TestIngestEndpoint:
    """POST /api/v1/messages/ingest"""

    def test_ingest_creates_ticket_and_customer(self):
        payload = _ingest_payload()
        resp = client.post("/api/v1/messages/ingest", json=payload, headers=HEADERS)
        assert resp.status_code == 200

        data = resp.json()
        assert data["is_duplicate"] is False
        assert data["is_reopen"] is False
        assert data["status"] == "new"
        assert data["ticket_id"] is not None
        assert data["customer_id"] is not None
        assert data["message_id"] is not None

    def test_duplicate_message_returns_existing_ticket(self):
        """Replaying the same external_message_id → is_duplicate=True, same ticket."""
        msg_id = f"msg-{uuid.uuid4().hex[:8]}"
        payload = _ingest_payload(external_message_id=msg_id)

        resp1 = client.post("/api/v1/messages/ingest", json=payload, headers=HEADERS)
        assert resp1.status_code == 200
        data1 = resp1.json()
        assert data1["is_duplicate"] is False

        resp2 = client.post("/api/v1/messages/ingest", json=payload, headers=HEADERS)
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert data2["is_duplicate"] is True
        assert data2["ticket_id"] == data1["ticket_id"]
        assert data2["message_id"] == data1["message_id"]

    def test_replay_10_times_still_one_ticket(self):
        """Section 5 contract: replaying the same email 10 times produces one ticket."""
        msg_id = f"msg-{uuid.uuid4().hex[:8]}"
        payload = _ingest_payload(external_message_id=msg_id)

        first_resp = client.post("/api/v1/messages/ingest", json=payload, headers=HEADERS)
        ticket_id = first_resp.json()["ticket_id"]

        for _ in range(9):
            resp = client.post("/api/v1/messages/ingest", json=payload, headers=HEADERS)
            assert resp.json()["is_duplicate"] is True
            assert resp.json()["ticket_id"] == ticket_id

    def test_same_thread_reuses_ticket(self):
        """Two different messages in the same thread → one ticket."""
        thread = f"thread-{uuid.uuid4().hex[:8]}"

        resp1 = client.post(
            "/api/v1/messages/ingest",
            json=_ingest_payload(thread_id=thread, external_message_id="msg-a1"),
            headers=HEADERS,
        )
        resp2 = client.post(
            "/api/v1/messages/ingest",
            json=_ingest_payload(thread_id=thread, external_message_id="msg-a2"),
            headers=HEADERS,
        )

        assert resp1.json()["ticket_id"] == resp2.json()["ticket_id"]
        assert resp2.json()["is_duplicate"] is False

    def test_different_threads_create_separate_tickets(self):
        """Different thread_ids → separate tickets."""
        resp1 = client.post(
            "/api/v1/messages/ingest",
            json=_ingest_payload(thread_id="t-1", external_message_id="m-1"),
            headers=HEADERS,
        )
        resp2 = client.post(
            "/api/v1/messages/ingest",
            json=_ingest_payload(thread_id="t-2", external_message_id="m-2"),
            headers=HEADERS,
        )

        assert resp1.json()["ticket_id"] != resp2.json()["ticket_id"]

    def test_customer_deduplication_by_email(self):
        """Same email → same customer_id."""
        resp1 = client.post(
            "/api/v1/messages/ingest",
            json=_ingest_payload(
                from_email="shared@example.com",
                thread_id="t-x1",
                external_message_id="m-x1",
            ),
            headers=HEADERS,
        )
        resp2 = client.post(
            "/api/v1/messages/ingest",
            json=_ingest_payload(
                from_email="shared@example.com",
                thread_id="t-x2",
                external_message_id="m-x2",
            ),
            headers=HEADERS,
        )

        assert resp1.json()["customer_id"] == resp2.json()["customer_id"]

    def test_missing_api_key_returns_401(self):
        resp = client.post(
            "/api/v1/messages/ingest",
            json=_ingest_payload(),
        )
        assert resp.status_code in (401, 422)

    def test_invalid_channel_rejected(self):
        resp = client.post(
            "/api/v1/messages/ingest",
            json=_ingest_payload(channel="sms"),
            headers=HEADERS,
        )
        assert resp.status_code == 422

    def test_empty_body_rejected(self):
        resp = client.post(
            "/api/v1/messages/ingest",
            json=_ingest_payload(body=""),
            headers=HEADERS,
        )
        assert resp.status_code == 422


class TestReopenLogic:
    """Ticket reopen on customer reply per section 5."""

    def _create_and_resolve_ticket(self, thread_id, msg_id):
        """Helper: create ticket, then manually set it to 'resolved'."""
        resp = client.post(
            "/api/v1/messages/ingest",
            json=_ingest_payload(thread_id=thread_id, external_message_id=msg_id),
            headers=HEADERS,
        )
        ticket_id = resp.json()["ticket_id"]

        async def _update():
            async with TestAsyncSessionLocal() as db:
                await db.execute(
                    update(Ticket).where(Ticket.id == uuid.UUID(ticket_id)).values(status="resolved")
                )
                await db.commit()

        run_async(_update())
        return ticket_id

    def test_reply_on_resolved_ticket_reopens(self):
        thread = "thread-reopen-1"
        ticket_id = self._create_and_resolve_ticket(thread, "msg-r1")

        # New message on same thread after resolution
        resp = client.post(
            "/api/v1/messages/ingest",
            json=_ingest_payload(thread_id=thread, external_message_id="msg-r2"),
            headers=HEADERS,
        )
        data = resp.json()
        assert data["ticket_id"] == ticket_id
        assert data["is_reopen"] is True
        assert data["status"] == "new"

    def test_reply_on_closed_ticket_reopens(self):
        thread = "thread-reopen-2"
        resp = client.post(
            "/api/v1/messages/ingest",
            json=_ingest_payload(thread_id=thread, external_message_id="msg-c1"),
            headers=HEADERS,
        )
        ticket_id = resp.json()["ticket_id"]

        async def _update():
            async with TestAsyncSessionLocal() as db:
                await db.execute(
                    update(Ticket).where(Ticket.id == uuid.UUID(ticket_id)).values(status="closed")
                )
                await db.commit()

        run_async(_update())

        resp2 = client.post(
            "/api/v1/messages/ingest",
            json=_ingest_payload(thread_id=thread, external_message_id="msg-c2"),
            headers=HEADERS,
        )
        assert resp2.json()["is_reopen"] is True
        assert resp2.json()["status"] == "new"

    def test_reopened_count_increments(self):
        thread = "thread-reopen-3"
        resp = client.post(
            "/api/v1/messages/ingest",
            json=_ingest_payload(thread_id=thread, external_message_id="msg-rc1"),
            headers=HEADERS,
        )
        ticket_id = resp.json()["ticket_id"]

        # Resolve and reopen twice
        for i in range(2):
            async def _update():
                async with TestAsyncSessionLocal() as db:
                    await db.execute(
                        update(Ticket).where(Ticket.id == uuid.UUID(ticket_id)).values(status="resolved")
                    )
                    await db.commit()

            run_async(_update())

            resp = client.post(
                "/api/v1/messages/ingest",
                json=_ingest_payload(thread_id=thread, external_message_id=f"msg-rc{i + 2}"),
                headers=HEADERS,
            )
            assert resp.json()["is_reopen"] is True

        # Verify reopened_count in DB
        async def _check():
            async with TestAsyncSessionLocal() as db:
                stmt = select(Ticket).where(Ticket.id == uuid.UUID(ticket_id))
                res = await db.execute(stmt)
                return res.scalar_one().reopened_count

        count = run_async(_check())
        assert count == 2


class TestStubEndpoints:
    """Phase 1 stubs for /analyze and /draft return correct schemas."""

    def _create_ticket(self):
        resp = client.post(
            "/api/v1/messages/ingest",
            json=_ingest_payload(),
            headers=HEADERS,
        )
        return resp.json()["ticket_id"]

    def test_analyze_stub_returns_valid_schema(self):
        ticket_id = self._create_ticket()
        resp = client.post(f"/api/v1/tickets/{ticket_id}/analyze", headers=HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert "score" in data
        assert "tier" in data
        assert "breakdown" in data
        assert "hard_rule_hits" in data

    def test_draft_stub_returns_valid_schema(self):
        ticket_id = self._create_ticket()
        resp = client.post(f"/api/v1/tickets/{ticket_id}/draft", headers=HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert "send_mode" in data
        assert "reply" in data
        assert "tier" in data
        assert "handoff" in data

    def test_analyze_404_for_missing_ticket(self):
        fake_id = uuid.uuid4()
        resp = client.post(f"/api/v1/tickets/{fake_id}/analyze", headers=HEADERS)
        assert resp.status_code == 404

    def test_draft_404_for_missing_ticket(self):
        fake_id = uuid.uuid4()
        resp = client.post(f"/api/v1/tickets/{fake_id}/draft", headers=HEADERS)
        assert resp.status_code == 404

    def test_list_tickets(self):
        self._create_ticket()
        resp = client.get("/api/v1/tickets", headers=HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_get_ticket_detail(self):
        ticket_id = self._create_ticket()
        resp = client.get(f"/api/v1/tickets/{ticket_id}", headers=HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == ticket_id
        assert data["status"] == "new"
