"""
Analytics endpoints — KPIs, trends, distribution charts, and sync health metrics.
Prefix: /api/v1/analytics
"""

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.app.core.security import verify_api_key
from api.app.models.database import get_db
from api.app.models.tables import SLATimer, Ticket
from api.app.schemas.tickets import AnalyticsOverview, AnalyticsTrends

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analytics", tags=["Analytics"], dependencies=[Depends(verify_api_key)])


@router.get("/overview", response_model=AnalyticsOverview)
async def get_analytics_overview(
    db: AsyncSession = Depends(get_db),
):
    """Aggregate high-level KPI cards for the Ops Console."""
    # 1. Total tickets
    res_total = await db.execute(select(func.count(Ticket.id)))
    total_tickets = res_total.scalar_one() or 0

    # 2. Open tickets
    res_open = await db.execute(
        select(func.count(Ticket.id)).where(Ticket.status.notin_(["resolved", "closed"]))
    )
    open_tickets = res_open.scalar_one() or 0

    # 3. Escalated tickets
    res_esc = await db.execute(
        select(func.count(Ticket.id)).where(Ticket.tier == "immediate")
    )
    escalated_tickets = res_esc.scalar_one() or 0

    # 4. AI-resolved tickets
    res_ai_res = await db.execute(
        select(func.count(Ticket.id)).where(
            Ticket.status.in_(["resolved", "closed"]),
            Ticket.tier.in_(["automated", "ai_assisted"]),
        )
    )
    ai_resolved_tickets = res_ai_res.scalar_one() or 0

    # 5. SLA at risk (>50% warned or open timers approaching due)
    now = datetime.now(UTC)
    res_sla_risk = await db.execute(
        select(func.count(SLATimer.id)).where(
            SLATimer.stopped_at.is_(None),
            (SLATimer.warned_50_at.is_not(None)) | (SLATimer.due_at <= now),
        )
    )
    sla_at_risk_count = res_sla_risk.scalar_one() or 0

    # 6. Average first response time in minutes
    res_fr = await db.execute(
        select(Ticket.created_at, Ticket.first_response_at).where(
            Ticket.first_response_at.is_not(None)
        )
    )
    pairs = res_fr.all()
    if pairs:
        deltas = [
            (fr - cr.replace(tzinfo=UTC) if cr.tzinfo is None else fr - cr).total_seconds() / 60.0
            for cr, fr in pairs
            if fr is not None and cr is not None
        ]
        avg_first_response_min = round(sum(deltas) / len(deltas), 1) if deltas else 0.0
    else:
        avg_first_response_min = 0.0

    return AnalyticsOverview(
        total_tickets=total_tickets,
        open_tickets=open_tickets,
        escalated_tickets=escalated_tickets,
        ai_resolved_tickets=ai_resolved_tickets,
        sla_at_risk_count=sla_at_risk_count,
        avg_first_response_min=avg_first_response_min,
    )


@router.get("/trends", response_model=AnalyticsTrends)
async def get_analytics_trends(
    db: AsyncSession = Depends(get_db),
):
    """Aggregate distribution trends, escalation rates, and CRM health."""
    # 1. Fetch all tickets for breakdown
    res = await db.execute(select(Ticket))
    tickets = res.scalars().all()
    total = len(tickets)

    intent_dist: dict[str, int] = {}
    sentiment_dist: dict[str, int] = {}
    tier_dist: dict[str, int] = {}
    status_dist: dict[str, int] = {}

    escalated_count = 0
    ai_res_count = 0
    crm_success_count = 0

    for t in tickets:
        # Intent
        i = t.intent or "unclassified"
        intent_dist[i] = intent_dist.get(i, 0) + 1

        # Sentiment
        s = t.sentiment or "neutral"
        sentiment_dist[s] = sentiment_dist.get(s, 0) + 1

        # Tier
        tr = t.tier or "unknown"
        tier_dist[tr] = tier_dist.get(tr, 0) + 1
        if tr in ("immediate", "priority"):
            escalated_count += 1
        if tr in ("automated", "ai_assisted") and t.status in ("resolved", "closed"):
            ai_res_count += 1

        # Status
        st = t.status or "new"
        status_dist[st] = status_dist.get(st, 0) + 1

        # CRM sync
        if t.crm_sync_status == "synced":
            crm_success_count += 1

    # SLA breach count
    res_breach = await db.execute(
        select(func.count(SLATimer.id)).where(SLATimer.breached_at.is_not(None))
    )
    breached_count = res_breach.scalar_one() or 0

    # Total SLA timers evaluated
    res_sla_tot = await db.execute(select(func.count(SLATimer.id)))
    total_sla = res_sla_tot.scalar_one() or 0

    escalation_rate_pct = round((escalated_count / total * 100.0), 1) if total > 0 else 0.0
    ai_resolution_rate_pct = round((ai_res_count / total * 100.0), 1) if total > 0 else 0.0
    sla_breach_rate_pct = round((breached_count / total_sla * 100.0), 1) if total_sla > 0 else 0.0
    crm_sync_success_rate_pct = round((crm_success_count / total * 100.0), 1) if total > 0 else 100.0

    return AnalyticsTrends(
        intent_distribution=intent_dist,
        sentiment_distribution=sentiment_dist,
        tier_distribution=tier_dist,
        status_distribution=status_dist,
        escalation_rate_pct=escalation_rate_pct,
        ai_resolution_rate_pct=ai_resolution_rate_pct,
        sla_breach_rate_pct=sla_breach_rate_pct,
        crm_sync_success_rate_pct=crm_sync_success_rate_pct,
    )
