"""
Abstract base class for CRM integrations (Section 11).
Defines contracts for contact and ticket synchronization.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class CRMContact:
    """Standardized CRM Contact payload."""

    crm_id: str
    email: str
    name: str | None = None
    customer_tier: str = "standard"


@dataclass
class CRMTicket:
    """Standardized CRM Ticket payload."""

    crm_id: str
    subject: str
    priority: str  # LOW | MEDIUM | HIGH
    status: str
    contact_id: str | None = None
    custom_properties: dict[str, Any] | None = None


class CRMClient(ABC):
    """Abstract interface for CRM providers (HubSpot, future Zoho, etc.)."""

    @abstractmethod
    async def find_contact_by_email(self, email: str) -> CRMContact | None:
        """Search CRM for an existing contact by email."""
        pass

    @abstractmethod
    async def upsert_contact(
        self,
        email: str,
        name: str | None = None,
        customer_tier: str = "standard",
    ) -> CRMContact:
        """Create or update a contact in the CRM."""
        pass

    @abstractmethod
    async def create_or_update_ticket(
        self,
        subject: str,
        priority: str,
        status: str,
        contact_id: str | None = None,
        custom_properties: dict[str, Any] | None = None,
        existing_crm_ticket_id: str | None = None,
    ) -> CRMTicket:
        """Create or update a ticket associated with a contact in the CRM."""
        pass
