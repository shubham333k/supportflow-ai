"""
SLA API router — scheduled scan and ticket timer status (Section 10.2).
"""

import logging
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.app.core.security import verify_api_key
from api.app.models.database import get_db
from api.app.models.tables import SLATimer
from api.app.services.sla import scan_sla_timers

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sla", tags=["SLA"], dependencies=[Depends(verify_api_key)])


@router.post("/scan")
async def trigger_sla_scan(
    db: AsyncSession = Depends(get_db),
):
    """
    Trigger scheduled SLA scan (called every 5 min by scheduler).
    Evaluates 50%, 90% warnings and breach escalation.
    """
    summary = await scan_sla_timers(db)
    return {
        "status": "ok",
        "active_timers_scanned": summary.active_timers_scanned,
        "warnings_50_count": len(summary.warnings_50),
        "warnings_90_count": len(summary.warnings_90),
        "breaches_count": len(summary.breaches),
        "warnings_50_ticket_ids": [str(tid) for tid in summary.warnings_50],
        "warnings_90_ticket_ids": [str(tid) for tid in summary.warnings_90],
        "breach_ticket_ids": [str(tid) for tid in summary.breaches],
    }


@router.get("/status/{ticket_id}")
async def get_ticket_sla_status(
    ticket_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve active SLA timer countdown and progress for a specific ticket."""
    stmt = (
        select(SLATimer)
        .where(SLATimer.ticket_id == ticket_id, SLATimer.stopped_at.is_(None))
        .order_by(SLATimer.started_at.desc())
        .limit(1)
    )
    res = await db.execute(stmt)
    timer = res.scalar_one_or_none()
    if not timer:
        raise HTTPException(status_code=404, detail="No active SLA timer found for ticket")

    now = datetime.now(UTC)
    started_at = timer.started_at.replace(tzinfo=UTC) if timer.started_at.tzinfo is None else timer.started_at
    due_at = timer.due_at.replace(tzinfo=UTC) if timer.due_at.tzinfo is None else timer.due_at

    total_seconds = (due_at - started_at).total_seconds()
    elapsed_seconds = (now - started_at).total_seconds()
    remaining_seconds = max(0.0, (due_at - now).total_seconds())
    progress_pct = min(100.0, (elapsed_seconds / total_seconds) * 100) if total_seconds > 0 else 100.0

    return {
        "ticket_id": str(ticket_id),
        "tier": timer.tier,
        "started_at": timer.started_at.isoformat(),
        "due_at": timer.due_at.isoformat(),
        "remaining_seconds": int(remaining_seconds),
        "progress_pct": round(progress_pct, 1),
        "warned_50": timer.warned_50_at is not None,
        "warned_90": timer.warned_90_at is not None,
        "is_breached": timer.breached_at is not None or now > due_at,
    }
