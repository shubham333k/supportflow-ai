"""
Drafting pipeline for SupportFlow AI.
Implements:
- Retrieval formatting
- Grounded generation with citation contract
- Second-stage hallucination verifier pass
- Outbound URL and PII safety filter
- 5-point auto-send gate (section 7.4)
"""

import logging
import re
from pathlib import Path

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.app.integrations.llm import LLMClient, llm_client
from api.app.models.tables import Draft, Ticket
from api.app.schemas.drafts import DraftResponse, DraftSource
from api.app.services.rag import retrieve_relevant_chunks

logger = logging.getLogger(__name__)

_DRAFT_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "draft_v1.md"
_VERIFY_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "verify_v1.md"

_ALLOWED_DOMAINS = {"supportflow.ai", "docs.supportflow.ai", "app.supportflow.ai"}
_URL_REGEX = re.compile(r"https?://([a-zA-Z0-9.-]+)(?:/[^\s]*)?", re.IGNORECASE)
_EMAIL_REGEX = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
_CREDIT_CARD_REGEX = re.compile(r"\b(?:\d{4}[ -]?){3}\d{4}\b")

# Intents permitted to automatically send replies (section 7.4)
_AUTO_SEND_INTENT_ALLOWLIST = {
    "product_question",
    "general_question",
    "feature_request",
    "subscription_change",
    "technical_issue",
    "account_access",
}


class GeneratorOutput(BaseModel):
    """Pydantic model for draft generator structured output."""

    answerable: bool
    reply: str | None = None
    citations: list[str] = []


class VerifierOutput(BaseModel):
    """Pydantic model for hallucination verifier structured output."""

    verifier_passed: bool
    unsupported_claims: list[str] = []


def _load_prompt(path: Path) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


def outbound_safety_filter(
    text: str | None,
    customer_email: str | None = None,
) -> tuple[bool, str | None]:
    """
    Scan outbound draft text for forbidden links or leaked PII.
    Rejects external URLs not on the allowlist and cross-customer emails/card numbers.

    Returns:
        (passed: bool, reason: str | None)
    """
    if not text:
        return True, None

    # 1. URL check: only allow supportflow.ai domains
    for match in _URL_REGEX.finditer(text):
        domain = match.group(1).lower()
        if not any(domain == allowed or domain.endswith("." + allowed) for allowed in _ALLOWED_DOMAINS):
            return False, f"Forbidden external link domain: {domain}"

    # 2. Credit card pattern check
    if _CREDIT_CARD_REGEX.search(text):
        return False, "Detected potential credit card or sensitive numerical sequence"

    # 3. Cross-customer email leakage check
    found_emails = _EMAIL_REGEX.findall(text)
    for email in found_emails:
        clean_email = email.lower()
        if customer_email and clean_email == customer_email.lower():
            continue
        if clean_email.endswith("@supportflow.ai"):
            continue
        return False, f"Detected unauthorized email address leakage: {email}"

    return True, None


def evaluate_auto_send_gate(
    tier: str,
    intent: str | None,
    security_signal: bool,
    answerable: bool,
    citations_count: int,
    top_similarity: float,
    verifier_passed: bool | None,
    outbound_passed: bool,
) -> str:
    """
    Enforce 5-point auto-send gate per section 7.4.

    Returns send_mode:
        - "auto"
        - "ack_only" (for feature requests)
        - "approval"
        - "none"
    """
    # 1. Final tier must be ai_assisted or automated
    tier_eligible = tier in ("ai_assisted", "automated")

    # 2. Intent must be on allowlist (and account_access cannot have security_signal)
    intent_eligible = (
        intent in _AUTO_SEND_INTENT_ALLOWLIST
        and not (intent == "account_access" and security_signal)
    )

    # 3. Retrieval passed (similarity >= 0.20, citations exist) & answerable
    retrieval_eligible = answerable and citations_count > 0 and top_similarity >= 0.20

    # 4. Verifier passed
    verifier_eligible = verifier_passed is True

    # 5. Outbound safety filter passed
    safety_eligible = outbound_passed

    if (
        tier_eligible
        and intent_eligible
        and retrieval_eligible
        and verifier_eligible
        and safety_eligible
    ):
        if intent == "feature_request":
            return "ack_only"
        return "auto"

    if tier == "immediate":
        return "none"

    return "approval"


async def generate_draft_for_ticket(
    db: AsyncSession,
    ticket: Ticket,
    client: LLMClient | None = None,
) -> DraftResponse:
    """
    Execute full RAG drafting pipeline:
    1. Retrieve top-4 KB chunks
    2. Invoke grounded generator
    3. Run verifier pass
    4. Run outbound safety filter
    5. Evaluate auto-send gate
    6. Persist to drafts table
    """
    if client is None:
        client = llm_client

    # Form query from ticket subject + body
    query = ticket.subject or ""
    chunks = await retrieve_relevant_chunks(db, query=query, top_k=4)

    sources = [
        DraftSource(
            chunk_id=c.chunk_id,
            doc=c.doc_title,
            heading=c.heading_path,
            similarity=round(c.similarity, 4),
        )
        for c in chunks
    ]
    top_similarity = sources[0].similarity if sources else 0.0

    # If no chunks retrieved above threshold -> immediate handoff
    if not sources or top_similarity < 0.20:
        draft = Draft(
            ticket_id=ticket.id,
            reply=None,
            sources=[s.model_dump() for s in sources],
            top_similarity=top_similarity,
            answerable=False,
            verifier_passed=None,
            send_mode="approval",
            status="pending",
        )
        db.add(draft)
        await db.flush()

        return DraftResponse(
            ticket_id=str(ticket.id),
            send_mode="approval",
            reply=None,
            sources=sources,
            answerable=False,
            verifier_passed=None,
            handoff=True,
            tier=ticket.tier or "priority",
        )

    # Format context for generator
    knowledge_passages = "\n\n".join(
        f"[Chunk ID: {c.chunk_id}] {c.content}" for c in chunks
    )

    draft_template = _load_prompt(_DRAFT_PROMPT_PATH)
    prompt = draft_template.format(
        knowledge_passages=knowledge_passages,
        subject=ticket.subject or "Support Request",
        customer_message=ticket.subject or "",
    )

    try:
        gen_output = await client.generate_structured(prompt, GeneratorOutput)
    except Exception as e:
        logger.warning("Generator error (%s), routing to handoff", e)
        gen_output = GeneratorOutput(answerable=False, reply=None, citations=[])

    verifier_passed = None
    if gen_output.answerable and gen_output.reply:
        verify_template = _load_prompt(_VERIFY_PROMPT_PATH)
        verify_prompt = verify_template.format(
            knowledge_passages=knowledge_passages,
            proposed_reply=gen_output.reply,
        )
        try:
            ver_output = await client.generate_structured(verify_prompt, VerifierOutput)
            verifier_passed = ver_output.verifier_passed
        except Exception as e:
            logger.warning("Verifier error (%s), defaulting to false", e)
            verifier_passed = False

    # Outbound safety filter
    outbound_passed, filter_reason = outbound_safety_filter(gen_output.reply)

    # Evaluate auto-send gate
    send_mode = evaluate_auto_send_gate(
        tier=ticket.tier or "priority",
        intent=ticket.intent,
        security_signal=("HR1" in (ticket.hard_rule_hits or [])),
        answerable=gen_output.answerable,
        citations_count=len(gen_output.citations),
        top_similarity=top_similarity,
        verifier_passed=verifier_passed,
        outbound_passed=outbound_passed,
    )

    handoff = send_mode in ("approval", "none") or not gen_output.answerable

    # Persist draft
    draft_record = Draft(
        ticket_id=ticket.id,
        reply=gen_output.reply,
        sources=[s.model_dump() for s in sources],
        top_similarity=top_similarity,
        answerable=gen_output.answerable,
        verifier_passed=verifier_passed,
        send_mode=send_mode,
        status="auto_sent" if send_mode == "auto" else "pending",
    )
    db.add(draft_record)
    await db.flush()

    return DraftResponse(
        ticket_id=str(ticket.id),
        send_mode=send_mode,
        reply=gen_output.reply,
        sources=sources,
        answerable=gen_output.answerable,
        verifier_passed=verifier_passed,
        handoff=handoff,
        tier=ticket.tier or "priority",
    )
