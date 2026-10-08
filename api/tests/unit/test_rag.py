"""
Unit tests for RAG parsing, chunking, safety filtering, and the 5-point auto-send gate.
"""

from api.app.services.drafting import evaluate_auto_send_gate, outbound_safety_filter
from api.app.services.rag import compute_content_hash, parse_markdown_by_headings


class TestMarkdownHeadingChunker:
    """Validate heading-based markdown parser per section 8.2."""

    def test_parses_h2_and_h3_headings_with_prefix(self):
        doc = """# Subscription Guide

## Upgrading Your Plan
You can upgrade your plan at any time from settings.
All upgrades take effect immediately.

### Prorated Billing
Unused time on your current billing cycle is credited as a prorated refund.

## Canceling
To cancel your account, go to billing and confirm.
"""
        chunks = parse_markdown_by_headings(doc, "subscription-guide.md")
        assert len(chunks) == 3

        # Chunk 1: Upgrading
        assert chunks[0].heading_path == "Subscription Guide > Upgrading Your Plan"
        assert "[Document: Subscription Guide > Section: Upgrading Your Plan]" in chunks[0].content
        assert "take effect immediately" in chunks[0].content

        # Chunk 2: Prorated
        assert chunks[1].heading_path == "Subscription Guide > Prorated Billing"
        assert "prorated refund" in chunks[1].content

        # Chunk 3: Canceling
        assert chunks[2].heading_path == "Subscription Guide > Canceling"
        assert "To cancel your account" in chunks[2].content

    def test_content_hash_is_deterministic_and_unique(self):
        t1 = "Hello world"
        t2 = "Hello world"
        t3 = "Different content"
        assert compute_content_hash(t1) == compute_content_hash(t2)
        assert compute_content_hash(t1) != compute_content_hash(t3)


class TestOutboundSafetyFilter:
    """Validate outbound link allowlist and PII leakage prevention."""

    def test_allows_whitelisted_supportflow_domains(self):
        text = (
            "You can review docs at https://docs.supportflow.ai/refunds or "
            "manage credentials at https://app.supportflow.ai/settings."
        )
        passed, reason = outbound_safety_filter(text)
        assert passed is True
        assert reason is None

    def test_blocks_external_and_phishing_urls(self):
        text = "Please verify your login at https://evil-phishing.com/login immediately."
        passed, reason = outbound_safety_filter(text)
        assert passed is False
        assert "Forbidden external link" in reason

    def test_blocks_credit_card_numbers(self):
        text = "We found your card 4532 8901 2345 6789 on file."
        passed, reason = outbound_safety_filter(text)
        assert passed is False
        assert "credit card" in reason

    def test_blocks_unauthorized_email_leakage(self):
        text = "Contact other customer at john.doe@externalcorp.com regarding this."
        passed, reason = outbound_safety_filter(text, customer_email="alice@customer.com")
        assert passed is False
        assert "unauthorized email address" in reason

    def test_allows_current_customer_email_and_support_email(self):
        text = "We sent your receipt to alice@customer.com. Contact support@supportflow.ai with questions."
        passed, reason = outbound_safety_filter(text, customer_email="alice@customer.com")
        assert passed is True
        assert reason is None


class TestAutoSendGate:
    """Validate the 5-point auto-send gate logic per section 7.4."""

    def test_all_five_conditions_pass_auto_sends(self):
        mode = evaluate_auto_send_gate(
            tier="automated",
            intent="product_question",
            security_signal=False,
            answerable=True,
            citations_count=2,
            top_similarity=0.85,
            verifier_passed=True,
            outbound_passed=True,
        )
        assert mode == "auto"

    def test_feature_request_returns_ack_only(self):
        mode = evaluate_auto_send_gate(
            tier="ai_assisted",
            intent="feature_request",
            security_signal=False,
            answerable=True,
            citations_count=1,
            top_similarity=0.75,
            verifier_passed=True,
            outbound_passed=True,
        )
        assert mode == "ack_only"

    def test_disallowed_intent_drops_to_approval(self):
        # billing_issue is not on auto-send allow-list
        mode = evaluate_auto_send_gate(
            tier="automated",
            intent="billing_issue",
            security_signal=False,
            answerable=True,
            citations_count=2,
            top_similarity=0.88,
            verifier_passed=True,
            outbound_passed=True,
        )
        assert mode == "approval"

    def test_verifier_failure_drops_to_approval(self):
        mode = evaluate_auto_send_gate(
            tier="automated",
            intent="product_question",
            security_signal=False,
            answerable=True,
            citations_count=2,
            top_similarity=0.88,
            verifier_passed=False,
            outbound_passed=True,
        )
        assert mode == "approval"

    def test_outbound_filter_failure_drops_to_approval(self):
        mode = evaluate_auto_send_gate(
            tier="automated",
            intent="product_question",
            security_signal=False,
            answerable=True,
            citations_count=2,
            top_similarity=0.88,
            verifier_passed=True,
            outbound_passed=False,
        )
        assert mode == "approval"

    def test_immediate_tier_returns_none(self):
        mode = evaluate_auto_send_gate(
            tier="immediate",
            intent="security_issue",
            security_signal=True,
            answerable=False,
            citations_count=0,
            top_similarity=0.0,
            verifier_passed=None,
            outbound_passed=True,
        )
        assert mode == "none"
