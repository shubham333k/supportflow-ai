"""
Ticket service — idempotent ingestion, customer upsert, ticket matching, reopen logic.
FastAPI is the single writer to PostgreSQL.
"""

import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.app.models.tables import AuditEvent, Customer, Message, Ticket
from api.app.schemas.messages import IngestMessageRequest, IngestMessageResponse

logger = logging.getLogger(__name__)

# Ticket statuses that trigger a reopen when a new inbound message arrives
_REOPENABLE = {"resolved", "closed", "waiting_customer"}


async def upsert_customer(
    db: AsyncSession,
    email: str,
    name: str | None = None,
) -> Customer:
    """Find or create a customer by email (lowercased). Never duplicates."""

    email_lower = email.strip().lower()
    stmt = select(Customer).where(Customer.email == email_lower)
    result = await db.execute(stmt)
    customer = result.scalar_one_or_none()

    if customer is None:
        customer = Customer(email=email_lower, name=name)
        db.add(customer)
        await db.flush()
        logger.info("Created customer %s for %s", customer.id, email_lower)
    else:
        if name and not customer.name:
            customer.name = name
            await db.flush()

    return customer


async def find_ticket_by_thread(
    db: AsyncSession, thread_id: str
) -> Ticket | None:
    """Look up an existing ticket by Gmail thread_id."""
    if not thread_id:
        return None
    stmt = select(Ticket).where(Ticket.thread_id == thread_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def ingest_message(
    db: AsyncSession,
    payload: IngestMessageRequest,
) -> IngestMessageResponse:
    """
    Idempotent message ingestion.

    1. Check external_message_id for duplicates (ON CONFLICT DO NOTHING).
    2. Upsert customer by email.
    3. Match ticket by thread_id or create new.
    4. If ticket was resolved/closed/waiting_customer → reopen.
    5. Store inbound message.
    6. Write audit event.
    """

    # ── 1. Duplicate check ──────────────────────────────────────────
    existing_msg = await _find_message_by_external_id(db, payload.external_message_id)
    if existing_msg is not None:
        ticket = await _get_ticket(db, existing_msg.ticket_id)
        logger.info(
            "Duplicate message %s → ticket %s",
            payload.external_message_id,
            ticket.id,
        )
        return IngestMessageResponse(
            ticket_id=ticket.id,
            message_id=existing_msg.id,
            customer_id=ticket.customer_id,
            is_duplicate=True,
            is_reopen=False,
            status=ticket.status,
        )

    # ── 2. Upsert customer ─────────────────────────────────────────
    customer = await upsert_customer(db, payload.from_email, payload.from_name)

    # ── 3. Match or create ticket ───────────────────────────────────
    is_reopen = False
    ticket = await find_ticket_by_thread(db, payload.thread_id)

    if ticket is not None:
        # Reopen logic: if ticket is in a finished state, reopen it
        if ticket.status in _REOPENABLE:
            ticket.status = "new"
            ticket.reopened_count += 1
            is_reopen = True
            logger.info(
                "Reopened ticket %s (count=%d)", ticket.id, ticket.reopened_count
            )
            if ticket.tier:
                from api.app.services.sla import start_or_update_sla_timer
                await start_or_update_sla_timer(db, ticket.id, ticket.tier)
    else:
        ticket = Ticket(
            customer_id=customer.id,
            channel=payload.channel,
            thread_id=payload.thread_id,
            subject=payload.subject,
            status="new",
        )
        db.add(ticket)
        await db.flush()
        logger.info("Created ticket %s for thread %s", ticket.id, payload.thread_id)

    # ── 4. Store inbound message ────────────────────────────────────
    message = Message(
        ticket_id=ticket.id,
        external_message_id=payload.external_message_id,
        direction="inbound",
        sender=payload.from_email,
        body=payload.body,
        sent_at=payload.received_at,
    )
    db.add(message)
    await db.flush()

    # ── 5. Audit event ──────────────────────────────────────────────
    audit = AuditEvent(
        ticket_id=ticket.id,
        actor="system",
        event_type="message_ingested",
        status="ok",
        payload={
            "external_message_id": payload.external_message_id,
            "channel": payload.channel,
            "is_reopen": is_reopen,
        },
    )
    db.add(audit)
    await db.flush()

    return IngestMessageResponse(
        ticket_id=ticket.id,
        message_id=message.id,
        customer_id=customer.id,
        is_duplicate=False,
        is_reopen=is_reopen,
        status=ticket.status,
    )


# ── Private helpers ────────────────────────────────────────────────────
async def _find_message_by_external_id(
    db: AsyncSession, external_id: str
) -> Message | None:
    stmt = select(Message).where(Message.external_message_id == external_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def _get_ticket(db: AsyncSession, ticket_id: UUID) -> Ticket:
    stmt = select(Ticket).where(Ticket.id == ticket_id)
    result = await db.execute(stmt)
    return result.scalar_one()
