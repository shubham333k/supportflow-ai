"""
Unit tests for SupportFlow AI escalation engine.
Verifies all 7 scoring factors, caps, tier boundaries, hard rules (HR1-HR6),
and the four core demo scenarios (A, B, C, D) per section 7.
"""

import pytest

from api.app.schemas.analysis import ClassifierOutput
from api.app.services.escalation import (
    HardRuleFlags,
    TicketContext,
    apply_hard_rules,
    load_escalation_config,
    score_ticket,
)


def _base_analysis(**overrides) -> ClassifierOutput:
    """Helper to create ClassifierOutput with defaults."""
    data = {
        "intent": "general_question",
        "sentiment": "neutral",
        "urgency": "low",
        "previous_contact_mentioned": False,
        "security_signal": False,
        "legal_or_privacy_signal": False,
        "threat_flag": False,
        "summary": "General inquiry",
        "requires_human": False,
        "confidence": 0.95,
    }
    data.update(overrides)
    return ClassifierOutput(**data)


class TestEscalationScoringFactors:
    """Validate calculation of all 7 factors in section 7.1."""

    def test_urgency_factor_points(self):
        cfg = load_escalation_config()
        expected = {"low": 3, "medium": 10, "high": 18, "critical": 25}
        for urgency, points in expected.items():
            analysis = _base_analysis(urgency=urgency)
            _, _, breakdown = score_ticket(analysis, TicketContext(), cfg)
            assert breakdown.urgency == points

    def test_sentiment_factor_points(self):
        cfg = load_escalation_config()
        expected = {"positive": 0, "neutral": 0, "negative": 6, "frustrated": 10, "angry": 15}
        for sentiment, points in expected.items():
            analysis = _base_analysis(sentiment=sentiment)
            _, _, breakdown = score_ticket(analysis, TicketContext(), cfg)
            assert breakdown.sentiment == points

    def test_customer_tier_factor_points(self):
        cfg = load_escalation_config()
        expected = {"enterprise": 10, "pro": 6, "standard": 3, "unknown": 3}
        for c_tier, points in expected.items():
            analysis = _base_analysis()
            ctx = TicketContext(customer_tier=c_tier)
            _, _, breakdown = score_ticket(analysis, ctx, cfg)
            assert breakdown.customer == points

    def test_issue_severity_factor_points(self):
        cfg = load_escalation_config()
        expected = {
            "security_issue": 20,
            "billing_issue": 16,
            "refund_request": 16,
            "account_access": 14,
            "complaint": 12,
            "technical_issue": 8,
            "subscription_change": 6,
            "sales_question": 4,
            "other": 4,
            "product_question": 2,
            "feature_request": 2,
            "general_question": 2,
        }
        for intent, points in expected.items():
            analysis = _base_analysis(intent=intent)
            _, _, breakdown = score_ticket(analysis, TicketContext(), cfg)
            assert breakdown.issue == points

    def test_prior_failed_resolution_and_cap(self):
        cfg = load_escalation_config()
        # open_ticket (8) + repeat_intent (7) + mentioned (4) = 19 -> capped at 15
        analysis = _base_analysis(previous_contact_mentioned=True)
        ctx = TicketContext(open_ticket_30d=True, repeat_intent_30d=True)
        _, _, breakdown = score_ticket(analysis, ctx, cfg)
        assert breakdown.prior_failed == 15

    def test_sla_risk_factor(self):
        cfg = load_escalation_config()
        # over 90% -> 10 pts
        _, _, b1 = score_ticket(_base_analysis(), TicketContext(worst_sla_pct=0.95), cfg)
        assert b1.sla_risk == 10
        # over 50% -> 5 pts
        _, _, b2 = score_ticket(_base_analysis(), TicketContext(worst_sla_pct=0.6), cfg)
        assert b2.sla_risk == 5
        # under 50% -> 0 pts
        _, _, b3 = score_ticket(_base_analysis(), TicketContext(worst_sla_pct=0.4), cfg)
        assert b3.sla_risk == 0

    def test_threat_flag_factor(self):
        cfg = load_escalation_config()
        _, _, b1 = score_ticket(_base_analysis(threat_flag=True), TicketContext(), cfg)
        assert b1.threat == 5
        _, _, b2 = score_ticket(_base_analysis(threat_flag=False), TicketContext(), cfg)
        assert b2.threat == 0


class TestTierBoundaries:
    """Exact score tier boundaries: ≥80 / 60-79 / 30-59 / <30."""

    @pytest.mark.parametrize(
        ("urgency", "sentiment", "customer_tier", "intent", "expected_tier"),
        [
            # low(3) + neutral(0) + standard(3) + product(2) = 8 -> automated (<30)
            ("low", "neutral", "standard", "product_question", "automated"),
            # medium(10) + frustrated(10) + standard(3) + technical(8) = 31 -> ai_assisted (30-59)
            ("medium", "frustrated", "standard", "technical_issue", "ai_assisted"),
            # high(18) + frustrated(10) + pro(6) + billing(16) + open_ticket(8) + sla(10) = 68 -> priority (60-79)
            ("high", "frustrated", "pro", "billing_issue", "priority"),
            # critical(25) + angry(15) + enterprise(10) + security(20) + open(8) + repeat(7) + sla(10) + threat(5) = 100 -> immediate (>=80)
            ("critical", "angry", "enterprise", "security_issue", "immediate"),
        ],
    )
    def test_tier_mapping(self, urgency, sentiment, customer_tier, intent, expected_tier):
        analysis = _base_analysis(urgency=urgency, sentiment=sentiment, intent=intent)
        ctx = TicketContext(customer_tier=customer_tier)
        if expected_tier == "priority":
            ctx.open_ticket_30d = True
            ctx.worst_sla_pct = 0.95
        elif expected_tier == "immediate":
            ctx.open_ticket_30d = True
            ctx.repeat_intent_30d = True
            ctx.worst_sla_pct = 0.95
            analysis.threat_flag = True

        total, tier, _ = score_ticket(analysis, ctx)
        assert tier == expected_tier


class TestHardRules:
    """HR1 - HR6 rules from section 7.3."""

    def test_hr1_security_issue_raises_to_immediate(self):
        # Even if base score is low, security intent forces immediate
        analysis = _base_analysis(intent="security_issue", urgency="low", sentiment="neutral")
        final, hits = apply_hard_rules("automated", analysis)
        assert final == "immediate"
        assert "HR1" in hits

    def test_hr1_security_signal_raises_to_immediate(self):
        analysis = _base_analysis(security_signal=True)
        final, hits = apply_hard_rules("automated", analysis)
        assert final == "immediate"
        assert "HR1" in hits

    def test_hr2_refund_or_billing_forces_priority(self):
        analysis = _base_analysis(intent="refund_request")
        final, hits = apply_hard_rules("automated", analysis)
        assert final == "priority"
        assert "HR2" in hits

        analysis2 = _base_analysis(intent="billing_issue")
        final2, hits2 = apply_hard_rules("automated", analysis2)
        assert final2 == "priority"
        assert "HR2" in hits2

    def test_hr2_legal_or_privacy_signal_forces_priority(self):
        analysis = _base_analysis(legal_or_privacy_signal=True)
        final, hits = apply_hard_rules("automated", analysis)
        assert final == "priority"
        assert "HR2" in hits

    def test_hr3_requires_human_forces_priority(self):
        analysis = _base_analysis(requires_human=True)
        final, hits = apply_hard_rules("automated", analysis)
        assert final == "priority"
        assert "HR3" in hits

    def test_hr4_low_confidence_or_invalid_forces_priority(self):
        analysis = _base_analysis(confidence=0.3)
        final, hits = apply_hard_rules("automated", analysis)
        assert final == "priority"
        assert "HR4" in hits

        analysis_normal = _base_analysis(confidence=0.9)
        final_inv, hits_inv = apply_hard_rules(
            "automated", analysis_normal, HardRuleFlags(analysis_invalid=True)
        )
        assert final_inv == "priority"
        assert "HR4" in hits_inv

    def test_hr5_rag_failure_forces_priority(self):
        analysis = _base_analysis()
        final, hits = apply_hard_rules("automated", analysis, HardRuleFlags(rag_failed=True))
        assert final == "priority"
        assert "HR5" in hits

    def test_hr6_auto_reply_cap_forces_priority(self):
        analysis = _base_analysis()
        final, hits = apply_hard_rules(
            "automated", analysis, HardRuleFlags(auto_reply_cap_exceeded=True)
        )
        assert final == "priority"
        assert "HR6" in hits

    def test_hard_rules_never_lower_tier(self):
        # If score tier is immediate, HR2 (priority floor) must not lower it to priority
        analysis = _base_analysis(intent="billing_issue")
        final, _ = apply_hard_rules("immediate", analysis)
        assert final == "immediate"


class TestCoreDemoScenarios:
    """The four core demo scenarios from Section 7.6."""

    def test_scenario_a_enterprise_double_charge_threat(self):
        """
        Scenario A: Enterprise customer, critical urgency, angry sentiment,
        billing issue, 2 prior failures, SLA >90%, threat flag.
        Target score: 96, Tier: immediate.
        """
        analysis = _base_analysis(
            intent="billing_issue",
            urgency="critical",
            sentiment="angry",
            threat_flag=True,
        )
        ctx = TicketContext(
            customer_tier="enterprise",
            open_ticket_30d=True,
            repeat_intent_30d=True,
            worst_sla_pct=0.95,
        )
        score, tier, breakdown = score_ticket(analysis, ctx)
        final_tier, _ = apply_hard_rules(tier, analysis)

        assert breakdown.urgency == 25
        assert breakdown.sentiment == 15
        assert breakdown.customer == 10
        assert breakdown.issue == 16
        assert breakdown.prior_failed == 15  # 8 + 7 = 15
        assert breakdown.sla_risk == 10
        assert breakdown.threat == 5
        assert score == 96
        assert tier == "immediate"
        assert final_tier == "immediate"

    def test_scenario_b_pro_double_charge_frustrated(self):
        """
        Scenario B: Pro customer, high urgency, frustrated sentiment,
        billing issue, open ticket yesterday, SLA >90%.
        Target score: 68, Tier: priority (HR2 also applies).
        """
        analysis = _base_analysis(
            intent="billing_issue",
            urgency="high",
            sentiment="frustrated",
            threat_flag=False,
        )
        ctx = TicketContext(
            customer_tier="pro",
            open_ticket_30d=True,
            repeat_intent_30d=False,
            worst_sla_pct=0.95,
        )
        score, tier, breakdown = score_ticket(analysis, ctx)
        final_tier, hits = apply_hard_rules(tier, analysis)

        assert breakdown.urgency == 18
        assert breakdown.sentiment == 10
        assert breakdown.customer == 6
        assert breakdown.issue == 16
        assert breakdown.prior_failed == 8
        assert breakdown.sla_risk == 10
        assert breakdown.threat == 0
        assert score == 68
        assert tier == "priority"
        assert final_tier == "priority"
        assert "HR2" in hits

    def test_scenario_c_standard_csv_export_error(self):
        """
        Scenario C: Standard customer, medium urgency, frustrated sentiment,
        technical issue, no prior history.
        Target score: 31, Tier: ai_assisted.
        """
        analysis = _base_analysis(
            intent="technical_issue",
            urgency="medium",
            sentiment="frustrated",
            threat_flag=False,
        )
        ctx = TicketContext(customer_tier="standard")
        score, tier, breakdown = score_ticket(analysis, ctx)
        final_tier, hits = apply_hard_rules(tier, analysis)

        assert breakdown.urgency == 10
        assert breakdown.sentiment == 10
        assert breakdown.customer == 3
        assert breakdown.issue == 8
        assert breakdown.prior_failed == 0
        assert breakdown.sla_risk == 0
        assert breakdown.threat == 0
        assert score == 31
        assert tier == "ai_assisted"
        assert final_tier == "ai_assisted"
        assert hits == []

    def test_scenario_d_pro_annual_billing_inquiry(self):
        """
        Scenario D: Pro customer, low urgency, neutral sentiment,
        subscription change, no prior history.
        Target score: 15, Tier: automated.
        """
        analysis = _base_analysis(
            intent="subscription_change",
            urgency="low",
            sentiment="neutral",
            threat_flag=False,
        )
        ctx = TicketContext(customer_tier="pro")
        score, tier, breakdown = score_ticket(analysis, ctx)
        final_tier, hits = apply_hard_rules(tier, analysis)

        assert breakdown.urgency == 3
        assert breakdown.sentiment == 0
        assert breakdown.customer == 6
        assert breakdown.issue == 6
        assert breakdown.prior_failed == 0
        assert breakdown.sla_risk == 0
        assert breakdown.threat == 0
        assert score == 15
        assert tier == "automated"
        assert final_tier == "automated"
        assert hits == []
