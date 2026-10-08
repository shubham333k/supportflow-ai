"""
Pydantic schemas for ticket endpoints.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class TicketSummary(BaseModel):
    """Compact ticket representation for list views."""

    id: UUID
    customer_id: UUID | None = None
    channel: str
    subject: str | None = None
    status: str
    intent: str | None = None
    sentiment: str | None = None
    urgency: str | None = None
    priority_score: int | None = None
    tier: str | None = None
    needs_manual_review: bool = False
    created_at: datetime
    updated_at: datetime


class TicketDetail(TicketSummary):
    """Full ticket with all fields for the detail view."""

    thread_id: str | None = None
    sub_intent: str | None = None
    hard_rule_hits: list[str] = []
    assigned_to: str | None = None
    crm_ticket_id: str | None = None
    crm_sync_status: str = "pending"
    reopened_count: int = 0
    first_response_at: datetime | None = None
    resolved_at: datetime | None = None
    closed_at: datetime | None = None
    csat_due_at: datetime | None = None

    # Enriched fields for Ops UI
    customer: dict | None = None
    messages: list[dict] = []
    latest_analysis: dict | None = None
    latest_draft: dict | None = None
    sla_timer: dict | None = None
    audit_events: list[dict] = []


class ApproveRequest(BaseModel):
    """Payload to approve or edit-and-approve a draft."""

    edited_body: str | None = None
    agent_name: str = "agent:ui"


class ApproveResponse(BaseModel):
    """Result of draft approval."""

    status: str
    ticket_id: str
    ticket_status: str
    reply_body: str
    sent_mode: str


class AnalyticsOverview(BaseModel):
    """High-level KPI metrics for Ops console."""

    total_tickets: int
    open_tickets: int
    escalated_tickets: int
    ai_resolved_tickets: int
    sla_at_risk_count: int
    avg_first_response_min: float


class AnalyticsTrends(BaseModel):
    """Distribution and rate metrics for Ops analytics."""

    intent_distribution: dict[str, int]
    sentiment_distribution: dict[str, int]
    tier_distribution: dict[str, int]
    status_distribution: dict[str, int]
    escalation_rate_pct: float
    ai_resolution_rate_pct: float
    sla_breach_rate_pct: float
    crm_sync_success_rate_pct: float

