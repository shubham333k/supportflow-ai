"""
Ticket endpoints — analyze, draft, approve, escalate, resolve, list, detail.
Phase 2: Real classifier + escalation engine with DB persistence.
"""

import logging
import time
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.app.core.config import settings
from api.app.core.security import verify_api_key
from api.app.integrations.hubspot import sync_ticket_to_crm
from api.app.models.database import get_db
from api.app.models.tables import AIAnalysis, AuditEvent, Customer, Draft, Message, SLATimer, Ticket
from api.app.schemas.analysis import AnalyzeResponse
from api.app.schemas.drafts import DraftResponse
from api.app.schemas.tickets import ApproveRequest, ApproveResponse, TicketDetail, TicketSummary
from api.app.services.classifier import classify_ticket_message
from api.app.services.drafting import generate_draft_for_ticket
from api.app.services.escalation import (
    HardRuleFlags,
    TicketContext,
    apply_hard_rules,
    score_ticket,
)
from api.app.services.loop_guard import check_auto_reply_cap
from api.app.services.sla import start_or_update_sla_timer, stop_sla_timer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tickets", tags=["Tickets"], dependencies=[Depends(verify_api_key)])


async def _get_ticket_or_404(db: AsyncSession, ticket_id: UUID) -> Ticket:
    stmt = select(Ticket).where(Ticket.id == ticket_id)
    result = await db.execute(stmt)
    ticket = result.scalar_one_or_none()
    if ticket is None:
        raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found")
    return ticket


# ── List & Detail ──────────────────────────────────────────────────────

@router.get("", response_model=list[TicketSummary])
async def list_tickets(
    status: str | None = None,
    tier: str | None = None,
    intent: str | None = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """List tickets with optional filters."""
    stmt = select(Ticket).order_by(Ticket.created_at.desc()).limit(limit)
    if status:
        stmt = stmt.where(Ticket.status == status)
    if tier:
        stmt = stmt.where(Ticket.tier == tier)
    if intent:
        stmt = stmt.where(Ticket.intent == intent)

    result = await db.execute(stmt)
    tickets = result.scalars().all()
    return [
        TicketSummary(
            id=t.id,
            customer_id=t.customer_id,
            channel=t.channel,
            subject=t.subject,
            status=t.status,
            intent=t.intent,
            sentiment=t.sentiment,
            urgency=t.urgency,
            priority_score=t.priority_score,
            tier=t.tier,
            needs_manual_review=t.needs_manual_review,
            created_at=t.created_at,
            updated_at=t.updated_at,
        )
        for t in tickets
    ]


@router.get("/{ticket_id}", response_model=TicketDetail)
async def get_ticket(
    ticket_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get full ticket detail with enriched relations for the UI."""
    t = await _get_ticket_or_404(db, ticket_id)

    # 1. Customer
    customer_dict = None
    if t.customer_id:
        res_c = await db.execute(select(Customer).where(Customer.id == t.customer_id))
        cust = res_c.scalar_one_or_none()
        if cust:
            customer_dict = {
                "id": str(cust.id),
                "email": cust.email,
                "name": cust.name,
                "company": cust.company,
                "tier": cust.tier,
                "crm_contact_id": cust.crm_contact_id,
            }

    # 2. Messages
    res_m = await db.execute(
        select(Message).where(Message.ticket_id == t.id).order_by(Message.created_at.asc())
    )
    messages = [
        {
            "id": str(m.id),
            "direction": m.direction,
            "sender": m.sender,
            "body": m.body,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in res_m.scalars().all()
    ]

    # 3. Latest Analysis
    res_a = await db.execute(
        select(AIAnalysis).where(AIAnalysis.ticket_id == t.id).order_by(AIAnalysis.created_at.desc()).limit(1)
    )
    analysis = res_a.scalar_one_or_none()
    analysis_dict = None
    if analysis:
        analysis_dict = {
            "id": str(analysis.id),
            "score": analysis.score,
            "tier": analysis.tier,
            "analysis": analysis.analysis,
            "score_breakdown": analysis.score_breakdown,
            "hard_rule_hits": analysis.hard_rule_hits or [],
            "model": analysis.model,
            "latency_ms": analysis.latency_ms,
            "created_at": analysis.created_at.isoformat() if analysis.created_at else None,
        }

    # 4. Latest Draft
    res_d = await db.execute(
        select(Draft).where(Draft.ticket_id == t.id).order_by(Draft.created_at.desc()).limit(1)
    )
    draft = res_d.scalar_one_or_none()
    draft_dict = None
    if draft:
        draft_dict = {
            "id": str(draft.id),
            "reply": draft.reply,
            "sources": draft.sources or [],
            "top_similarity": draft.top_similarity,
            "answerable": draft.answerable,
            "verifier_passed": draft.verifier_passed,
            "send_mode": draft.send_mode,
            "status": draft.status,
            "created_at": draft.created_at.isoformat() if draft.created_at else None,
        }

    # 5. SLA Timer
    res_s = await db.execute(
        select(SLATimer).where(SLATimer.ticket_id == t.id).order_by(SLATimer.started_at.desc()).limit(1)
    )
    sla = res_s.scalar_one_or_none()
    sla_dict = None
    if sla:
        sla_dict = {
            "id": str(sla.id),
            "tier": sla.tier,
            "started_at": sla.started_at.isoformat() if sla.started_at else None,
            "due_at": sla.due_at.isoformat() if sla.due_at else None,
            "warned_50_at": sla.warned_50_at.isoformat() if sla.warned_50_at else None,
            "warned_90_at": sla.warned_90_at.isoformat() if sla.warned_90_at else None,
            "breached_at": sla.breached_at.isoformat() if sla.breached_at else None,
            "stopped_at": sla.stopped_at.isoformat() if sla.stopped_at else None,
        }

    # 6. Audit events
    res_ae = await db.execute(
        select(AuditEvent).where(AuditEvent.ticket_id == t.id).order_by(AuditEvent.created_at.desc()).limit(10)
    )
    audit_events = [
        {
            "id": str(ae.id),
            "actor": ae.actor,
            "event_type": ae.event_type,
            "status": ae.status,
            "payload": ae.payload,
            "created_at": ae.created_at.isoformat() if ae.created_at else None,
        }
        for ae in res_ae.scalars().all()
    ]

    return TicketDetail(
        id=t.id,
        customer_id=t.customer_id,
        channel=t.channel,
        thread_id=t.thread_id,
        subject=t.subject,
        status=t.status,
        intent=t.intent,
        sub_intent=t.sub_intent,
        sentiment=t.sentiment,
        urgency=t.urgency,
        priority_score=t.priority_score,
        tier=t.tier,
        hard_rule_hits=t.hard_rule_hits or [],
        assigned_to=t.assigned_to,
        crm_ticket_id=t.crm_ticket_id,
        crm_sync_status=t.crm_sync_status,
        needs_manual_review=t.needs_manual_review,
        reopened_count=t.reopened_count,
        first_response_at=t.first_response_at,
        resolved_at=t.resolved_at,
        closed_at=t.closed_at,
        csat_due_at=t.csat_due_at,
        created_at=t.created_at,
        updated_at=t.updated_at,
        customer=customer_dict,
        messages=messages,
        latest_analysis=analysis_dict,
        latest_draft=draft_dict,
        sla_timer=sla_dict,
        audit_events=audit_events,
    )


# ── Analyze (Phase 2 Real Implementation) ─────────────────────────────

@router.post("/{ticket_id}/analyze", response_model=AnalyzeResponse)
async def analyze_ticket(
    ticket_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Real analysis & escalation engine (Phase 2).
    - Classifies message with validated structured output & retry
    - Gathers 30d customer context & SLA risk
    - Scores 7 factors + applies hard rules
    - Updates ticket & stores AIAnalysis record
    """
    start_time = time.time()
    ticket = await _get_ticket_or_404(db, ticket_id)

    # 1. Fetch latest inbound message
    stmt_msg = (
        select(Message)
        .where(Message.ticket_id == ticket.id, Message.direction == "inbound")
        .order_by(Message.sent_at.desc(), Message.created_at.desc())
        .limit(1)
    )
    res_msg = await db.execute(stmt_msg)
    latest_message = res_msg.scalar_one_or_none()

    message_body = latest_message.body if latest_message else (ticket.subject or "")

    # 2. Gather customer context
    customer_tier = "unknown"
    if ticket.customer_id:
        stmt_cust = select(Customer).where(Customer.id == ticket.customer_id)
        res_cust = await db.execute(stmt_cust)
        customer = res_cust.scalar_one_or_none()
        if customer:
            customer_tier = customer.tier

    # 3. Gather 30d ticket history & active SLA timers
    cutoff = datetime.now(UTC) - timedelta(days=30)
    open_ticket_30d = False
    worst_sla_pct = 0.0

    if ticket.customer_id:
        stmt_open = select(func.count(Ticket.id)).where(
            Ticket.customer_id == ticket.customer_id,
            Ticket.id != ticket.id,
            Ticket.status.in_(["new", "pending_approval", "escalated", "waiting_customer"]),
            Ticket.created_at >= cutoff,
        )
        res_open = await db.execute(stmt_open)
        open_ticket_30d = (res_open.scalar_one() or 0) > 0

        # Check existing SLA timers for customer
        stmt_sla = (
            select(SLATimer)
            .join(Ticket, SLATimer.ticket_id == Ticket.id)
            .where(
                Ticket.customer_id == ticket.customer_id,
                Ticket.id != ticket.id,
                SLATimer.stopped_at.is_(None),
            )
        )
        res_sla = await db.execute(stmt_sla)
        active_timers = res_sla.scalars().all()
        now = datetime.now(UTC)
        for t in active_timers:
            total_duration = (t.due_at - t.started_at).total_seconds()
            if total_duration > 0:
                elapsed = (now - t.started_at).total_seconds()
                pct = elapsed / total_duration
                if pct > worst_sla_pct:
                    worst_sla_pct = pct

    # Check 24h auto-reply cap for HR6
    cap_exceeded = await check_auto_reply_cap(db, ticket.id)

    # 4. Run classifier
    analysis, is_fallback = await classify_ticket_message(
        body=message_body,
        subject=ticket.subject,
    )

    # 5. Check repeat intent in 30d
    repeat_intent_30d = False
    if ticket.customer_id and analysis.intent:
        stmt_repeat = select(func.count(Ticket.id)).where(
            Ticket.customer_id == ticket.customer_id,
            Ticket.id != ticket.id,
            Ticket.intent == analysis.intent,
            Ticket.created_at >= cutoff,
        )
        res_repeat = await db.execute(stmt_repeat)
        repeat_intent_30d = (res_repeat.scalar_one() or 0) >= 1

    # 6. Run escalation scoring & hard rules
    ctx = TicketContext(
        customer_tier=customer_tier,
        open_ticket_30d=open_ticket_30d,
        repeat_intent_30d=repeat_intent_30d,
        worst_sla_pct=worst_sla_pct,
    )
    flags = HardRuleFlags(
        analysis_invalid=is_fallback,
        auto_reply_cap_exceeded=cap_exceeded,
    )

    score, score_tier, breakdown = score_ticket(analysis, ctx)
    final_tier, hard_rule_hits = apply_hard_rules(score_tier, analysis, flags)

    # 7. Update ticket
    ticket.intent = analysis.intent
    ticket.sub_intent = analysis.sub_intent
    ticket.sentiment = analysis.sentiment
    ticket.urgency = analysis.urgency
    ticket.priority_score = score
    ticket.tier = final_tier
    ticket.hard_rule_hits = hard_rule_hits
    ticket.needs_manual_review = ("HR4" in hard_rule_hits) or analysis.requires_human
    if final_tier == "immediate":
        ticket.status = "escalated"
    elif final_tier == "priority":
        ticket.status = "pending_approval"

    # 8. Store AIAnalysis
    latency_ms = int((time.time() - start_time) * 1000)
    ai_record = AIAnalysis(
        ticket_id=ticket.id,
        message_id=latest_message.id if latest_message else None,
        model=settings.GEMINI_MODEL,
        prompt_version="classify_v1",
        analysis=analysis.model_dump(),
        score=score,
        tier=final_tier,
        score_breakdown=breakdown.model_dump(),
        hard_rule_hits=hard_rule_hits,
        latency_ms=latency_ms,
    )
    db.add(ai_record)

    # 9. Audit event
    audit = AuditEvent(
        ticket_id=ticket.id,
        actor="system",
        event_type="ticket_analyzed",
        status="ok",
        payload={
            "score": score,
            "tier": final_tier,
            "hard_rule_hits": hard_rule_hits,
            "is_fallback": is_fallback,
            "latency_ms": latency_ms,
        },
    )
    db.add(audit)
    await db.flush()

    # 10. Start or update SLA timer & Sync to HubSpot CRM
    await start_or_update_sla_timer(db, ticket.id, final_tier)
    await sync_ticket_to_crm(db, ticket.id)

    return AnalyzeResponse(
        ticket_id=str(ticket.id),
        score=score,
        tier=final_tier,
        intent=ticket.intent,
        breakdown=breakdown,
        hard_rule_hits=hard_rule_hits,
        needs_manual_review=ticket.needs_manual_review,
    )


# ── Draft (Phase 3 Real RAG Pipeline) ─────────────────────────────────

@router.post("/{ticket_id}/draft", response_model=DraftResponse)
async def draft_reply(
    ticket_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    RAG draft response generation (Phase 3).
    - Cosine similarity retrieval over kb_chunks
    - Grounded generation with citation contract
    - Hallucination verifier pass
    - Outbound safety filter
    - 5-point auto-send gate
    """
    ticket = await _get_ticket_or_404(db, ticket_id)
    return await generate_draft_for_ticket(db, ticket)


# ── Ticket Actions (Resolve, Escalate) ─────────────────────────────────

@router.post("/{ticket_id}/resolve")
async def resolve_ticket(
    ticket_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Resolve a ticket, stopping its SLA timer and updating CRM status."""
    ticket = await _get_ticket_or_404(db, ticket_id)
    ticket.status = "resolved"
    ticket.resolved_at = datetime.now(UTC)
    await stop_sla_timer(db, ticket.id)
    await sync_ticket_to_crm(db, ticket.id)
    await db.commit()
    return {"status": "ok", "ticket_id": str(ticket.id), "ticket_status": "resolved"}


@router.post("/{ticket_id}/escalate")
async def manual_escalate_ticket(
    ticket_id: UUID,
    reason: str = "manual_escalation",
    db: AsyncSession = Depends(get_db),
):
    """Escalate a ticket to immediate tier and alert team."""
    ticket = await _get_ticket_or_404(db, ticket_id)
    ticket.tier = "immediate"
    ticket.status = "escalated"
    await start_or_update_sla_timer(db, ticket.id, "immediate")
    await sync_ticket_to_crm(db, ticket.id)
    await db.commit()
    return {"status": "ok", "ticket_id": str(ticket.id), "tier": "immediate", "ticket_status": "escalated"}


@router.post("/{ticket_id}/approve", response_model=ApproveResponse)
async def approve_ticket_draft(
    ticket_id: UUID,
    payload: ApproveRequest = ApproveRequest(),
    db: AsyncSession = Depends(get_db),
):
    """
    Approve an AI-generated draft (optionally with human edits),
    record outbound message, update ticket status, and audit.
    """
    ticket = await _get_ticket_or_404(db, ticket_id)

    # 1. Fetch latest draft
    stmt = (
        select(Draft)
        .where(Draft.ticket_id == ticket.id)
        .order_by(Draft.created_at.desc())
        .limit(1)
    )
    res = await db.execute(stmt)
    draft = res.scalar_one_or_none()

    reply_body = (
        payload.edited_body.strip()
        if payload.edited_body
        else (draft.reply if draft and draft.reply else "")
    )
    if not reply_body:
        raise HTTPException(status_code=400, detail="No draft reply available to approve.")

    # 2. Update draft status
    if draft:
        draft.status = (
            "edited_sent"
            if (payload.edited_body and payload.edited_body != draft.reply)
            else "approved"
        )
        draft.reply = reply_body

    # 3. Create outbound message
    now = datetime.now(UTC)
    outbound_msg = Message(
        ticket_id=ticket.id,
        direction="outbound",
        sender=payload.agent_name,
        body=reply_body,
        created_at=now,
    )
    db.add(outbound_msg)

    # 4. Update ticket status & timestamps
    ticket.status = "waiting_customer"
    if not ticket.first_response_at:
        ticket.first_response_at = now

    # 5. Audit event
    audit = AuditEvent(
        ticket_id=ticket.id,
        actor=payload.agent_name,
        event_type="draft_approved",
        status="ok",
        payload={
            "edited": bool(payload.edited_body),
            "reply_length": len(reply_body),
            "send_mode": "manual_approval",
        },
    )
    db.add(audit)

    await sync_ticket_to_crm(db, ticket.id)
    await db.commit()

    return ApproveResponse(
        status="ok",
        ticket_id=str(ticket.id),
        ticket_status=ticket.status,
        reply_body=reply_body,
        sent_mode="approved_and_sent",
    )


@router.post("/{ticket_id}/sent")
async def mark_ticket_sent(
    ticket_id: UUID,
    sent_body: str,
    actor: str = "n8n",
    db: AsyncSession = Depends(get_db),
):
    """Callback when an external orchestrator (n8n) finishes sending a message."""
    ticket = await _get_ticket_or_404(db, ticket_id)
    now = datetime.now(UTC)
    outbound_msg = Message(
        ticket_id=ticket.id,
        direction="outbound",
        sender=actor,
        body=sent_body,
        created_at=now,
    )
    db.add(outbound_msg)
    if not ticket.first_response_at:
        ticket.first_response_at = now
    ticket.status = "waiting_customer"
    audit = AuditEvent(
        ticket_id=ticket.id,
        actor=actor,
        event_type="reply_sent",
        status="ok",
        payload={"body_length": len(sent_body)},
    )
    db.add(audit)
    await db.commit()
    return {"status": "ok", "ticket_id": str(ticket.id), "ticket_status": ticket.status}

