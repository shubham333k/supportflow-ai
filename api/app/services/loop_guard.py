"""
Loop guard service — detects auto-replies, out-of-office ping-pongs,
system bounces, and enforces the 24-hour auto-reply cap per sender (HR6).
"""

import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.app.core.config import settings
from api.app.models.tables import Message

_AUTO_SUBMITTED_VALUES = {"auto-replied", "auto-generated", "auto-notified"}

_OUT_OF_OFFICE_SUBJECT_PATTERNS = [
    re.compile(r"^out of office", re.IGNORECASE),
    re.compile(r"^automatic reply", re.IGNORECASE),
    re.compile(r"^auto[- ]?reply", re.IGNORECASE),
    re.compile(r"^undelivered mail returned", re.IGNORECASE),
    re.compile(r"^delivery status notification", re.IGNORECASE),
]

_BOUNCE_SENDER_PATTERNS = [
    re.compile(r"^mailer-daemon@", re.IGNORECASE),
    re.compile(r"^postmaster@", re.IGNORECASE),
    re.compile(r"^no-?reply@", re.IGNORECASE),
]


@dataclass
class LoopGuardResult:
    """Result of loop guard inspection on an inbound message."""

    is_loop: bool
    reason: str | None = None
    is_auto_reply_cap_exceeded: bool = False


def inspect_headers_and_subject(
    sender: str,
    subject: str | None,
    headers: dict[str, str] | None = None,
) -> tuple[bool, str | None]:
    """
    Check if the incoming message is an automated reply, bounce, or system loop.

    Returns:
        (is_loop, reason)
    """
    # 1. Check against own support address
    sender_clean = sender.strip().lower()
    if settings.GMAIL_USER and sender_clean == settings.GMAIL_USER.strip().lower():
        return True, "Sender matches own support email address"

    # 2. Check bounce and noreply patterns
    for pat in _BOUNCE_SENDER_PATTERNS:
        if pat.search(sender_clean):
            return True, f"Sender matches automated bounce pattern: {sender_clean}"

    # 3. Check subject patterns
    if subject:
        subject_clean = subject.strip()
        for pat in _OUT_OF_OFFICE_SUBJECT_PATTERNS:
            if pat.search(subject_clean):
                return True, f"Subject matches out-of-office/auto-reply pattern: '{subject}'"

    # 4. Check email headers if provided
    if headers:
        normalized_headers = {k.lower(): v.strip().lower() for k, v in headers.items()}

        auto_submitted = normalized_headers.get("auto-submitted")
        if auto_submitted and auto_submitted in _AUTO_SUBMITTED_VALUES:
            return True, f"Auto-Submitted header set to '{auto_submitted}'"

        precedence = normalized_headers.get("precedence")
        if precedence and precedence in ("bulk", "junk", "auto_reply"):
            return True, f"Precedence header set to '{precedence}'"

        suppress = normalized_headers.get("x-auto-response-suppress")
        if suppress and ("all" in suppress or "oof" in suppress or "rn" in suppress):
            return True, f"X-Auto-Response-Suppress header set to '{suppress}'"

    return False, None


async def check_auto_reply_cap(
    db: AsyncSession,
    ticket_id: UUID,
    max_replies_24h: int = 5,
) -> bool:
    """
    Check if the ticket has received >= max_replies_24h auto-sent replies
    in the last 24 hours (HR6 enforcement).
    """
    cutoff = datetime.now(UTC) - timedelta(hours=24)
    stmt = (
        select(func.count(Message.id))
        .where(
            Message.ticket_id == ticket_id,
            Message.direction == "outbound",
            Message.ai_generated.is_(True),
            Message.sent_at >= cutoff,
        )
    )
    result = await db.execute(stmt)
    count = result.scalar_one() or 0
    return count >= max_replies_24h
