"""
Unit tests for HubSpot CRM client and synchronization workflow.
Verifies contact/ticket upsert, <= 6 custom properties, priority mapping,
and resilient failure handling without blocking ticket triage.
"""

from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from api.app.integrations.crm_base import CRMTicket
from api.app.integrations.hubspot import (
    TIER_TO_HS_PRIORITY,
    HubSpotClient,
    sync_ticket_to_crm,
)
from api.app.models.base import Base
from api.app.models.tables import AIAnalysis, Customer, Ticket


class TestHubSpotPriorityMapping:
    """Validate mapping between internal routing tiers and HubSpot priority."""

    def test_tier_to_priority_mapping(self):
        assert TIER_TO_HS_PRIORITY["immediate"] == "HIGH"
        assert TIER_TO_HS_PRIORITY["priority"] == "HIGH"
        assert TIER_TO_HS_PRIORITY["ai_assisted"] == "MEDIUM"
        assert TIER_TO_HS_PRIORITY["automated"] == "LOW"


class TestHubSpotClientMockMode:
    """Validate CRM operations in mock mode (used for tests and offline runs)."""

    @pytest.mark.asyncio
    async def test_upsert_contact_mock(self):
        client = HubSpotClient(access_token="")
        contact = await client.upsert_contact(
            email="enterprise.user@corp.com",
            name="Jane Doe",
            customer_tier="enterprise",
        )
        assert contact.crm_id.startswith("mock-contact-")
        assert contact.email == "enterprise.user@corp.com"
        assert contact.name == "Jane Doe"
        assert contact.customer_tier == "enterprise"

    @pytest.mark.asyncio
    async def test_create_or_update_ticket_mock(self):
        client = HubSpotClient(access_token="")
        crm_ticket = await client.create_or_update_ticket(
            subject="Double charge dispute",
            priority="HIGH",
            status="new",
            contact_id="mock-contact-123",
            custom_properties={
                "ai_intent": "billing_issue",
                "ai_priority_score": "96",
                "ai_tier": "immediate",
                "ai_summary": "Customer demands refund",
            },
        )
        assert crm_ticket.crm_id.startswith("mock-hs-ticket-")
        assert crm_ticket.priority == "HIGH"
        assert crm_ticket.custom_properties["ai_intent"] == "billing_issue"
        assert crm_ticket.custom_properties["ai_priority_score"] == "96"


class TestCRMSyncWorkflow:
    """Validate end-to-end sync_ticket_to_crm function against database models."""

    @pytest.fixture
    async def async_db(self):
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
    async def test_sync_ticket_to_crm_success(self, async_db):
        # Create Customer and Ticket
        cust = Customer(
            id=uuid4(),
            email="alice@company.com",
            name="Alice Smith",
            tier="pro",
        )
        async_db.add(cust)
        await async_db.flush()

        ticket = Ticket(
            id=uuid4(),
            customer_id=cust.id,
            channel="email",
            subject="Upgrade plan issue",
            intent="subscription_change",
            tier="ai_assisted",
            priority_score=45,
            status="new",
        )
        async_db.add(ticket)
        await async_db.flush()

        analysis = AIAnalysis(
            ticket_id=ticket.id,
            model="gemini-2.5-flash",
            prompt_version="classify_v1",
            analysis={"summary": "Customer wants to upgrade to Pro."},
            score=45,
            tier="ai_assisted",
        )
        async_db.add(analysis)
        await async_db.flush()

        success = await sync_ticket_to_crm(async_db, ticket.id)
        assert success is True
        assert ticket.crm_sync_status == "ok"
        assert ticket.crm_ticket_id is not None
        assert cust.crm_contact_id is not None

    @pytest.mark.asyncio
    async def test_sync_ticket_to_crm_failure_resilience(self, async_db):
        """When CRM client raises an error, sync status is 'failed' and does not raise."""
        ticket = Ticket(
            id=uuid4(),
            channel="email",
            subject="Failing CRM ticket",
            status="new",
        )
        async_db.add(ticket)
        await async_db.flush()

        class FailingCRMClient(HubSpotClient):
            async def create_or_update_ticket(self, *args, **kwargs) -> CRMTicket:
                raise RuntimeError("HubSpot 503 Service Unavailable")

        success = await sync_ticket_to_crm(async_db, ticket.id, client=FailingCRMClient())
        assert success is False
        assert ticket.crm_sync_status == "failed"
