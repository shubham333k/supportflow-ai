"""
Escalation engine for SupportFlow AI.
Pure function, config-driven via api/config/escalation.yaml.
Calculates 7-factor score (0-100), maps to tiers, and applies overriding hard rules.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from api.app.schemas.analysis import ClassifierOutput, ScoreBreakdown

TIER_ORDER = ["automated", "ai_assisted", "priority", "immediate"]

_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "escalation.yaml"
_CACHED_CONFIG: dict[str, Any] | None = None


def load_escalation_config() -> dict[str, Any]:
    """Load and cache escalation configuration from YAML."""
    global _CACHED_CONFIG
    if _CACHED_CONFIG is None:
        if not _CONFIG_PATH.exists():
            raise FileNotFoundError(f"Escalation config not found at {_CONFIG_PATH}")
        with open(_CONFIG_PATH, encoding="utf-8") as f:
            _CACHED_CONFIG = yaml.safe_load(f)
    return _CACHED_CONFIG


@dataclass
class TicketContext:
    """Historical and customer context used by the escalation scoring engine."""

    customer_tier: str = "standard"  # enterprise | pro | standard | unknown
    open_ticket_30d: bool = False
    repeat_intent_30d: bool = False
    worst_sla_pct: float = 0.0  # 0.0 to 1.0+ (percentage through SLA deadline of existing open ticket)


@dataclass
class HardRuleFlags:
    """Extra system flags checked by hard rules."""

    analysis_invalid: bool = False
    rag_failed: bool = False
    auto_reply_cap_exceeded: bool = False


def score_ticket(
    analysis: ClassifierOutput,
    ctx: TicketContext,
    cfg: dict[str, Any] | None = None,
) -> tuple[int, str, ScoreBreakdown]:
    """
    Compute 7-factor escalation score (0-100) per section 7.1.

    Returns:
        (total_score, tier, breakdown)
    """
    if cfg is None:
        cfg = load_escalation_config()

    w = cfg["weights"]

    # 1. Prior failed resolution (capped at w["prior"]["cap"])
    prior = 0
    if ctx.open_ticket_30d:
        prior += w["prior"]["open_ticket_30d"]
    if ctx.repeat_intent_30d:
        prior += w["prior"]["repeat_same_intent"]
    if analysis.previous_contact_mentioned and not ctx.open_ticket_30d:
        prior += w["prior"]["mentioned_no_record"]
    prior = min(prior, w["prior"]["cap"])

    # 2. SLA risk (looked up from existing tickets for customer)
    sla = 0
    if ctx.worst_sla_pct > 0.9:
        sla = w["sla"]["over_90"]
    elif ctx.worst_sla_pct > 0.5:
        sla = w["sla"]["over_50"]

    # 3. Factor calculations
    urgency_score = w["urgency"].get(analysis.urgency, w["urgency"]["low"])
    sentiment_score = w["sentiment"].get(analysis.sentiment, 0)
    customer_score = w["customer_tier"].get(ctx.customer_tier, w["customer_tier"]["unknown"])
    issue_score = w["issue"].get(analysis.intent, w["issue"]["other"])
    threat_score = w["threat"] if analysis.threat_flag else 0

    breakdown = ScoreBreakdown(
        urgency=urgency_score,
        sentiment=sentiment_score,
        customer=customer_score,
        issue=issue_score,
        prior_failed=prior,
        sla_risk=sla,
        threat=threat_score,
    )

    total = (
        breakdown.urgency
        + breakdown.sentiment
        + breakdown.customer
        + breakdown.issue
        + breakdown.prior_failed
        + breakdown.sla_risk
        + breakdown.threat
    )

    # Map total score to descending tier thresholds
    # e.g. [("immediate", 80), ("priority", 60), ("ai_assisted", 30), ("automated", 0)]
    tier = next(t for t, lo in cfg["tiers_desc"] if total >= lo)

    return total, tier, breakdown


def apply_hard_rules(
    tier: str,
    analysis: ClassifierOutput,
    flags: HardRuleFlags | None = None,
) -> tuple[str, list[str]]:
    """
    Apply hard rules (HR1-HR6) per section 7.3.
    Hard rules can only raise the tier, never lower it.

    Returns:
        (final_tier, list_of_hit_rule_ids)
    """
    if flags is None:
        flags = HardRuleFlags()

    hits: list[str] = []
    floor = "automated"

    def raise_to(target_tier: str) -> None:
        nonlocal floor
        if TIER_ORDER.index(target_tier) > TIER_ORDER.index(floor):
            floor = target_tier

    # HR1: Security signal or intent -> immediate
    if analysis.intent == "security_issue" or analysis.security_signal:
        hits.append("HR1")
        raise_to("immediate")

    # HR2: Refund/billing or legal/privacy signal -> priority (human must approve)
    if analysis.intent in ("refund_request", "billing_issue") or analysis.legal_or_privacy_signal:
        hits.append("HR2")
        raise_to("priority")

    # HR3: LLM requested human -> priority
    if analysis.requires_human:
        hits.append("HR3")
        raise_to("priority")

    # HR4: Classifier validation failed or low confidence (< 0.5) -> priority
    if flags.analysis_invalid or analysis.confidence < 0.5:
        hits.append("HR4")
        raise_to("priority")

    # HR5: RAG failure / out of scope -> priority
    if flags.rag_failed:
        hits.append("HR5")
        raise_to("priority")

    # HR6: Sender exceeded 24h auto-reply cap -> priority (human-only)
    if flags.auto_reply_cap_exceeded:
        hits.append("HR6")
        raise_to("priority")

    # Final tier is max(score_tier, floor)
    final_tier = tier if TIER_ORDER.index(tier) >= TIER_ORDER.index(floor) else floor

    return final_tier, hits
