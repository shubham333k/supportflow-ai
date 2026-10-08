"""
HubSpot CRM integration implementing CRMClient.
FastAPI is the single writer to PostgreSQL and HubSpot (Section 11).
Enforces <= 6 custom properties, priority tier mappings, retry/backoff,
and failure logging without blocking the core support triage flow.
"""

import logging
from typing import Any
from uuid import UUID, uuid4

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from api.app.core.config import settings
from api.app.integrations.crm_base import CRMClient, CRMContact, CRMTicket
from api.app.models.tables import AIAnalysis, AuditEvent, Customer, Ticket

logger = logging.getLogger(__name__)

# Map internal tiers to HubSpot hs_ticket_priority
TIER_TO_HS_PRIORITY = {
    "immediate": "HIGH",
    "priority": "HIGH",
    "ai_assisted": "MEDIUM",
    "automated": "LOW",
}


def _is_retryable_hubspot_error(exc: BaseException) -> bool:
    """Only retry transient network/server failures, never 4xx auth or validation errors."""
    if isinstance(exc, httpx.RequestError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        if exc.response.status_code in (400, 401, 403, 404):
            return False
        return exc.response.status_code in (429, 500, 502, 503, 504)
    return False


class HubSpotClient(CRMClient):
    """Client for HubSpot CRM REST API v3 with private app token and mock fallback."""

    def __init__(
        self,
        access_token: str | None = None,
        base_url: str = "https://api.hubapi.com",
    ):
        # If caller explicitly passes access_token (even ""), use it directly.
        # Only fall back to settings when access_token is None (not provided).
        self.access_token = settings.HUBSPOT_ACCESS_TOKEN if access_token is None else access_token
        self.base_url = base_url.rstrip("/")
        # Enter mock mode when token is absent OR is a recognizable placeholder (matches LLMClient pattern).
        _is_placeholder = not self.access_token or any(
            self.access_token.startswith(p) for p in ("mock", "dev-", "your-", "test-", "fake-")
        )
        self.mock_mode = _is_placeholder

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

    @retry(
        retry=retry_if_exception(_is_retryable_hubspot_error),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    async def find_contact_by_email(self, email: str) -> CRMContact | None:
        """Search contact by email in HubSpot."""
        if self.mock_mode:
            return CRMContact(
                crm_id=f"mock-contact-{abs(hash(email)) % 100000}",
                email=email,
                customer_tier="standard",
            )

        url = f"{self.base_url}/crm/v3/objects/contacts/search"
        payload = {
            "filterGroups": [
                {
                    "filters": [
                        {
                            "propertyName": "email",
                            "operator": "EQ",
                            "value": email.strip().lower(),
                        }
                    ]
                }
            ],
            "properties": ["email", "firstname", "lastname", "customer_tier"],
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload, headers=self._headers())
            resp.raise_for_status()
            data = resp.json()
            results = data.get("results", [])
            if not results:
                return None
            res = results[0]
            props = res.get("properties", {})
            first = props.get("firstname", "") or ""
            last = props.get("lastname", "") or ""
            name = f"{first} {last}".strip() or None
            return CRMContact(
                crm_id=str(res["id"]),
                email=props.get("email", email),
                name=name,
                customer_tier=props.get("customer_tier", "standard"),
            )

    @retry(
        retry=retry_if_exception(_is_retryable_hubspot_error),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    async def upsert_contact(
        self,
        email: str,
        name: str | None = None,
        customer_tier: str = "standard",
    ) -> CRMContact:
        """Find or create contact in HubSpot."""
        existing = await self.find_contact_by_email(email)
        if existing and not self.mock_mode:
            # Update customer_tier if needed
            url = f"{self.base_url}/crm/v3/objects/contacts/{existing.crm_id}"
            payload = {"properties": {"customer_tier": customer_tier}}
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.patch(url, json=payload, headers=self._headers())
            existing.customer_tier = customer_tier
            return existing

        if self.mock_mode:
            return CRMContact(
                crm_id=f"mock-contact-{uuid4().hex[:8]}",
                email=email,
                name=name,
                customer_tier=customer_tier,
            )

        # Create contact
        first_name = name.split()[0] if name else ""
        last_name = " ".join(name.split()[1:]) if name and len(name.split()) > 1 else ""
        url = f"{self.base_url}/crm/v3/objects/contacts"
        payload = {
            "properties": {
                "email": email.strip().lower(),
                "firstname": first_name,
                "lastname": last_name,
                "customer_tier": customer_tier,
            }
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload, headers=self._headers())
            resp.raise_for_status()
            data = resp.json()
            return CRMContact(
                crm_id=str(data["id"]),
                email=email,
                name=name,
                customer_tier=customer_tier,
            )

    @retry(
        retry=retry_if_exception(_is_retryable_hubspot_error),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    async def create_or_update_ticket(
        self,
        subject: str,
        priority: str,
        status: str,
        contact_id: str | None = None,
        custom_properties: dict[str, Any] | None = None,
        existing_crm_ticket_id: str | None = None,
    ) -> CRMTicket:
        """Create or update a ticket in HubSpot."""
        if self.mock_mode:
            crm_id = existing_crm_ticket_id or f"mock-hs-ticket-{uuid4().hex[:8]}"
            return CRMTicket(
                crm_id=crm_id,
                subject=subject,
                priority=priority,
                status=status,
                contact_id=contact_id,
                custom_properties=custom_properties or {},
            )

        properties = {
            "subject": subject,
            "hs_ticket_priority": priority,
        }
        if custom_properties:
            properties.update(custom_properties)

        async with httpx.AsyncClient(timeout=10.0) as client:
            if existing_crm_ticket_id:
                url = f"{self.base_url}/crm/v3/objects/tickets/{existing_crm_ticket_id}"
                resp = await client.patch(url, json={"properties": properties}, headers=self._headers())
                resp.raise_for_status()
                return CRMTicket(
                    crm_id=existing_crm_ticket_id,
                    subject=subject,
                    priority=priority,
                    status=status,
                    contact_id=contact_id,
                    custom_properties=custom_properties,
                )

            # Create new ticket with association
            url = f"{self.base_url}/crm/v3/objects/tickets"
            payload: dict[str, Any] = {"properties": properties}
            if contact_id:
                payload["associations"] = [
                    {
                        "to": {"id": contact_id},
                        "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 16}],
                    }
                ]
            resp = await client.post(url, json=payload, headers=self._headers())
            resp.raise_for_status()
            data = resp.json()
            return CRMTicket(
                crm_id=str(data["id"]),
                subject=subject,
                priority=priority,
                status=status,
                contact_id=contact_id,
                custom_properties=custom_properties,
            )


# Default singleton instance
hubspot_client = HubSpotClient()


async def sync_ticket_to_crm(
    db: AsyncSession,
    ticket_id: UUID,
    client: CRMClient | None = None,
) -> bool:
    """
    Synchronize a ticket and customer to HubSpot CRM.
    Sets crm_sync_status to 'ok' on success, 'failed' on error.
    Never blocks or raises unhandled exceptions to avoid impacting core ticket workflows.
    """
    if client is None:
        client = hubspot_client

    stmt = select(Ticket).where(Ticket.id == ticket_id)
    res = await db.execute(stmt)
    ticket = res.scalar_one_or_none()
    if not ticket:
        return False

    customer: Customer | None = None
    if ticket.customer_id:
        stmt_c = select(Customer).where(Customer.id == ticket.customer_id)
        res_c = await db.execute(stmt_c)
        customer = res_c.scalar_one_or_none()

    try:
        contact_id: str | None = None
        if customer:
            crm_contact = await client.upsert_contact(
                email=customer.email,
                name=customer.name,
                customer_tier=customer.tier,
            )
            customer.crm_contact_id = crm_contact.crm_id
            contact_id = crm_contact.crm_id

        # Map priority
        priority = TIER_TO_HS_PRIORITY.get(ticket.tier or "priority", "MEDIUM")

        # Custom properties (<= 6 total)
        custom_props: dict[str, Any] = {
            "ai_intent": ticket.intent or "",
            "ai_priority_score": str(ticket.priority_score or 0),
            "ai_tier": ticket.tier or "",
        }

        # Fetch latest analysis for summary
        stmt_a = (
            select(AIAnalysis)
            .where(AIAnalysis.ticket_id == ticket.id)
            .order_by(AIAnalysis.created_at.desc())
            .limit(1)
        )
        res_a = await db.execute(stmt_a)
        analysis_record = res_a.scalar_one_or_none()
        if analysis_record and isinstance(analysis_record.analysis, dict):
            custom_props["ai_summary"] = analysis_record.analysis.get("summary", "")

        crm_ticket = await client.create_or_update_ticket(
            subject=ticket.subject or "Support Ticket",
            priority=priority,
            status=ticket.status,
            contact_id=contact_id,
            custom_properties=custom_props,
            existing_crm_ticket_id=ticket.crm_ticket_id,
        )

        ticket.crm_ticket_id = crm_ticket.crm_id
        ticket.crm_sync_status = "ok"

        audit = AuditEvent(
            ticket_id=ticket.id,
            actor="system",
            event_type="crm_sync",
            status="ok",
            payload={"crm_ticket_id": crm_ticket.crm_id, "priority": priority},
        )
        db.add(audit)
        await db.flush()
        return True

    except Exception as e:
        logger.error("CRM sync failed for ticket %s: %s", ticket.id, e)
        ticket.crm_sync_status = "failed"
        audit = AuditEvent(
            ticket_id=ticket.id,
            actor="system",
            event_type="crm_sync",
            status="failed",
            error=str(e),
        )
        db.add(audit)
        await db.flush()
        return False
