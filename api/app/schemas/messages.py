"""
Pydantic schemas for message ingestion (POST /messages/ingest).
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class IngestMessageRequest(BaseModel):
    """Payload from n8n after normalising the inbound email/webhook."""

    channel: str = Field(..., pattern=r"^(email|chat|webhook)$")
    external_message_id: str = Field(
        ..., min_length=1, description="Gmail message id or webhook event id — idempotency key"
    )
    thread_id: str | None = Field(
        None, description="Gmail thread id; one ticket per thread"
    )
    from_email: str = Field(..., min_length=1)
    from_name: str | None = None
    subject: str | None = None
    body: str = Field(..., min_length=1, max_length=50_000)
    received_at: datetime | None = None


class IngestMessageResponse(BaseModel):
    """Returned to n8n — drives the next branch."""

    ticket_id: UUID
    message_id: UUID
    customer_id: UUID
    is_duplicate: bool = False
    is_reopen: bool = False
    status: str  # current ticket status
