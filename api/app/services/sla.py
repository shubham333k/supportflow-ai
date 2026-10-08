"""
SLA service — timers, progress monitoring, 50%/90% warnings, and breach escalation.
Implements sections 7.2 and 10.2 of the implementation plan.
"""

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.app.models.tables import AuditEvent, SLATimer, Ticket
from api.app.services.escalation import load_escalation_config

logger = logging.getLogger(__name__)

# Default SLA hours by tier (from escalation.yaml)
DEFAULT_SLA_HOURS = {
    "immediate": 1,
    "priority": 4,
    "ai_assisted": 24,
    "automated": 48,
}


@dataclass
class SLAScanSummary:
    """Summary of SLA timer scanning results."""

    active_timers_scanned: int = 0
    warnings_50: list[UUID] = field(default_factory=list)
    warnings_90: list[UUID] = field(default_factory=list)
    breaches: list[UUID] = field(default_factory=list)


def get_sla_hours_for_tier(tier: str) -> int:
    """Read SLA deadline hours for a tier from config or defaults."""
    cfg = load_escalation_config()
    sla_hours = cfg.get("sla_hours", DEFAULT_SLA_HOURS)
    return sla_hours.get(tier, DEFAULT_SLA_HOURS.get(tier, 24))


async def start_or_update_sla_timer(
    db: AsyncSession,
    ticket_id: UUID,
    tier: str,
) -> SLATimer:
    """
    Start or update an SLA timer for a ticket based on its routing tier.
    If an unstopped timer exists, updates its due_at and tier.
    """
    now = datetime.now(UTC)
    hours = get_sla_hours_for_tier(tier)
    due_at = now + timedelta(hours=hours)

    stmt = (
        select(SLATimer)
        .where(SLATimer.ticket_id == ticket_id, SLATimer.stopped_at.is_(None))
        .order_by(SLATimer.started_at.desc())
        .limit(1)
    )
    res = await db.execute(stmt)
    existing = res.scalar_one_or_none()

    if existing:
        existing.tier = tier
        existing.due_at = due_at
        timer = existing
    else:
        timer = SLATimer(
            ticket_id=ticket_id,
            tier=tier,
            started_at=now,
            due_at=due_at,
        )
        db.add(timer)

    await db.flush()
    return timer


async def stop_sla_timer(
    db: AsyncSession,
    ticket_id: UUID,
) -> bool:
    """Stop active SLA timers for a ticket (e.g. upon reply sent or resolution)."""
    now = datetime.now(UTC)
    stmt = select(SLATimer).where(
        SLATimer.ticket_id == ticket_id,
        SLATimer.stopped_at.is_(None),
    )
    res = await db.execute(stmt)
    timers = res.scalars().all()

    if not timers:
        return False

    for t in timers:
        t.stopped_at = now

    await db.flush()
    return True


async def scan_sla_timers(
    db: AsyncSession,
) -> SLAScanSummary:
    """
    Scan all active SLA timers:
    - 50% elapsed -> trigger 50% warning
    - 90% elapsed -> trigger 90% warning & escalate ticket
    - 100% elapsed (now > due_at) -> trigger breach alert & manager escalation
    """
    now = datetime.now(UTC)
    summary = SLAScanSummary()

    stmt = select(SLATimer).where(SLATimer.stopped_at.is_(None))
    res = await db.execute(stmt)
    active_timers = res.scalars().all()
    summary.active_timers_scanned = len(active_timers)

    for timer in active_timers:
        started_at = timer.started_at.replace(tzinfo=UTC) if timer.started_at.tzinfo is None else timer.started_at
        due_at = timer.due_at.replace(tzinfo=UTC) if timer.due_at.tzinfo is None else timer.due_at

        total_seconds = (due_at - started_at).total_seconds()
        if total_seconds <= 0:
            continue

        elapsed_seconds = (now - started_at).total_seconds()
        progress = elapsed_seconds / total_seconds

        # 1. Breach check
        if now >= due_at and timer.breached_at is None:
            timer.breached_at = now
            summary.breaches.append(timer.ticket_id)
            audit = AuditEvent(
                ticket_id=timer.ticket_id,
                actor="system",
                event_type="sla_breach",
                status="alert",
                payload={"tier": timer.tier, "elapsed_seconds": elapsed_seconds},
            )
            db.add(audit)
            logger.warning("SLA breached on ticket %s (tier=%s)", timer.ticket_id, timer.tier)

        # 2. 90% Warning check
        elif progress >= 0.90 and timer.warned_90_at is None:
            timer.warned_90_at = now
            summary.warnings_90.append(timer.ticket_id)
            # Escalate ticket tier to priority if it was lower
            stmt_t = select(Ticket).where(Ticket.id == timer.ticket_id)
            res_t = await db.execute(stmt_t)
            t = res_t.scalar_one_or_none()
            if t and t.tier in ("automated", "ai_assisted"):
                t.tier = "priority"
                t.status = "pending_approval"

            audit = AuditEvent(
                ticket_id=timer.ticket_id,
                actor="system",
                event_type="sla_warning_90",
                status="alert",
                payload={"tier": timer.tier, "progress_pct": round(progress * 100, 1)},
            )
            db.add(audit)
            logger.info("SLA 90%% warning on ticket %s", timer.ticket_id)

        # 3. 50% Warning check
        elif progress >= 0.50 and timer.warned_50_at is None:
            timer.warned_50_at = now
            summary.warnings_50.append(timer.ticket_id)
            audit = AuditEvent(
                ticket_id=timer.ticket_id,
                actor="system",
                event_type="sla_warning_50",
                status="info",
                payload={"tier": timer.tier, "progress_pct": round(progress * 100, 1)},
            )
            db.add(audit)
            logger.info("SLA 50%% warning on ticket %s", timer.ticket_id)

    await db.commit()
    return summary
