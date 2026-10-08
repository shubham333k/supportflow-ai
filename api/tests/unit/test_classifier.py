"""
Unit tests for SupportFlow AI classifier service.
Verifies input sanitization, structured output extraction, retry on failure,
fail-safe fallback, and prompt injection defences.
"""

import pytest

from api.app.integrations.llm import LLMClient
from api.app.schemas.analysis import ClassifierOutput
from api.app.services.classifier import (
    classify_ticket_message,
    create_fail_safe_output,
    sanitize_customer_text,
)


class TestInputSanitization:
    """Validate HTML stripping, whitespace collapsing, and char capping."""

    def test_strips_html_tags(self):
        dirty = "<p>Hello <b>Support</b>, <script>alert(1)</script> I have a bug.</p>"
        clean = sanitize_customer_text(dirty)
        assert "<p>" not in clean
        assert "<b>" not in clean
        assert "<script>" not in clean
        assert "Hello Support , alert(1) I have a bug." in clean

    def test_normalizes_whitespace(self):
        dirty = "Too   many    spaces\n\n\nand   newlines"
        clean = sanitize_customer_text(dirty)
        assert clean == "Too many spaces and newlines"

    def test_caps_text_length(self):
        long_text = "A" * 6000
        clean = sanitize_customer_text(long_text, max_chars=4000)
        assert len(clean) == 4000


class TestClassifierExecutionAndRetries:
    """Validate LLM invocation, retry behavior, and fail-safe fallback."""

    @pytest.mark.asyncio
    async def test_successful_classification_on_first_try(self):
        client = LLMClient()
        expected = ClassifierOutput(
            intent="technical_issue",
            sub_intent="csv export fail",
            sentiment="frustrated",
            urgency="medium",
            previous_contact_mentioned=False,
            security_signal=False,
            legal_or_privacy_signal=False,
            threat_flag=False,
            summary="CSV export keeps failing",
            requires_human=False,
            confidence=0.92,
        )
        client.set_mock_responses([expected])

        output, is_fallback = await classify_ticket_message(
            body="The CSV export keeps failing with an error.",
            subject="Export issue",
            client=client,
        )

        assert is_fallback is False
        assert output.intent == "technical_issue"
        assert output.sentiment == "frustrated"
        assert output.confidence == 0.92

    @pytest.mark.asyncio
    async def test_retry_on_first_attempt_failure(self):
        client = LLMClient()
        # Attempt 1 raises ValueError, Attempt 2 succeeds
        expected = ClassifierOutput(
            intent="billing_issue",
            sentiment="frustrated",
            urgency="high",
            confidence=0.88,
        )
        client.set_mock_responses([ValueError("JSON decode error"), expected])

        output, is_fallback = await classify_ticket_message(
            body="I was charged twice.",
            client=client,
        )

        assert is_fallback is False
        assert output.intent == "billing_issue"
        assert output.urgency == "high"

    @pytest.mark.asyncio
    async def test_fail_safe_fallback_when_all_attempts_fail(self):
        client = LLMClient()
        # generate_structured has stop_after_attempt(3) tenacity retry.
        # classify_ticket_message makes 2 sequential calls. Total errors needed = 3 * 2 = 6.
        client.set_mock_responses([
            RuntimeError("API quota exhausted"),
            RuntimeError("API quota exhausted"),
            RuntimeError("API quota exhausted"),
            RuntimeError("API quota exhausted"),
            RuntimeError("API quota exhausted"),
            RuntimeError("API quota exhausted"),
        ])

        output, is_fallback = await classify_ticket_message(
            body="Important message but LLM service is down",
            client=client,
        )

        assert is_fallback is True
        assert output.intent == "other"
        assert output.confidence == 0.0
        assert output.requires_human is True
        assert "Classifier failed" in output.summary

    def test_create_fail_safe_output(self):
        fallback = create_fail_safe_output()
        assert fallback.intent == "other"
        assert fallback.confidence == 0.0
        assert fallback.requires_human is True
        assert fallback.urgency == "high"
