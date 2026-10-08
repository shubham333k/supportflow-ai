"""
Unit tests for Loop Guard service.
Tests out-of-office detection, bounce sender detection, auto-reply headers,
and own-email loop detection.
"""

from api.app.core.config import settings
from api.app.services.loop_guard import inspect_headers_and_subject


class TestLoopGuardInspection:
    """Validate header, subject, and sender inspection for automated loops."""

    def test_out_of_office_subjects_detected(self):
        subjects = [
            "Out of Office: vacation until Monday",
            "Automatic reply: Re: Support ticket #123",
            "Auto-reply: In a meeting",
            "Auto reply: thanks for contacting me",
            "Undelivered Mail Returned to Sender",
            "Delivery Status Notification (Failure)",
        ]
        for sub in subjects:
            is_loop, reason = inspect_headers_and_subject(
                sender="user@company.com",
                subject=sub,
            )
            assert is_loop is True
            assert reason is not None

    def test_bounce_senders_detected(self):
        senders = [
            "mailer-daemon@mx.google.com",
            "postmaster@mail.example.org",
            "noreply@saas.com",
            "no-reply@service.io",
        ]
        for sender in senders:
            is_loop, reason = inspect_headers_and_subject(
                sender=sender,
                subject="Regular ticket question",
            )
            assert is_loop is True
            assert "bounce pattern" in reason

    def test_own_support_email_detected(self):
        original = settings.GMAIL_USER
        try:
            settings.GMAIL_USER = "support@supportflow.ai"
            is_loop, reason = inspect_headers_and_subject(
                sender="support@supportflow.ai",
                subject="Help with account",
            )
            assert is_loop is True
            assert "own support email" in reason
        finally:
            settings.GMAIL_USER = original

    def test_auto_submitted_headers_detected(self):
        headers = {"Auto-Submitted": "auto-replied"}
        is_loop, reason = inspect_headers_and_subject(
            sender="customer@example.com",
            subject="Help please",
            headers=headers,
        )
        assert is_loop is True
        assert "Auto-Submitted" in reason

    def test_precedence_bulk_headers_detected(self):
        headers = {"Precedence": "bulk"}
        is_loop, reason = inspect_headers_and_subject(
            sender="customer@example.com",
            subject="Question",
            headers=headers,
        )
        assert is_loop is True
        assert "Precedence" in reason

    def test_x_auto_response_suppress_detected(self):
        headers = {"X-Auto-Response-Suppress": "All"}
        is_loop, reason = inspect_headers_and_subject(
            sender="customer@example.com",
            subject="Question",
            headers=headers,
        )
        assert is_loop is True
        assert "X-Auto-Response-Suppress" in reason

    def test_legitimate_customer_email_passes(self):
        is_loop, reason = inspect_headers_and_subject(
            sender="alice@customer.com",
            subject="Billing question about invoice #442",
            headers={"Message-ID": "<abc@customer.com>"},
        )
        assert is_loop is False
        assert reason is None
