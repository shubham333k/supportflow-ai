"""
Audit service — write audit events for every automated action and failure.
"""

import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from api.app.models.tables import AuditEvent

logger = logging.getLogger(__name__)


async def log_event(
    db: AsyncSession,
    *,
    ticket_id: UUID | None,
    actor: str,
    event_type: str,
    status: str = "ok",
    payload: dict | None = None,
    error: str | None = None,
    n8n_execution_id: str | None = None,
) -> AuditEvent:
    """Append an audit event row."""

    event = AuditEvent(
        ticket_id=ticket_id,
        actor=actor,
        event_type=event_type,
        status=status,
        payload=payload,
        error=error,
        n8n_execution_id=n8n_execution_id,
    )
    db.add(event)
    await db.flush()
    return event
