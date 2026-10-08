"""
Classifier service for SupportFlow AI.
Cleans untrusted customer text, fills classify prompt, executes with LLM,
validates output with one retry, and falls back to a fail-safe state on failure.
"""

import logging
import re
from pathlib import Path

from api.app.integrations.llm import LLMClient, llm_client
from api.app.schemas.analysis import ClassifierOutput, EntityExtraction

logger = logging.getLogger(__name__)

_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "classify_v1.md"
_PROMPT_TEMPLATE: str | None = None
_HTML_TAG_REGEX = re.compile(r"<[^>]+>")


def _load_prompt_template() -> str:
    global _PROMPT_TEMPLATE
    if _PROMPT_TEMPLATE is None:
        if not _PROMPT_PATH.exists():
            raise FileNotFoundError(f"Prompt template missing at {_PROMPT_PATH}")
        with open(_PROMPT_PATH, encoding="utf-8") as f:
            _PROMPT_TEMPLATE = f.read()
    return _PROMPT_TEMPLATE


def sanitize_customer_text(text: str, max_chars: int = 4000) -> str:
    """
    Sanitize customer text:
    - Strip HTML tags
    - Truncate length
    - Normalize whitespace
    """
    # Remove HTML tags
    clean = _HTML_TAG_REGEX.sub(" ", text)
    # Normalize excessive newlines/spaces
    clean = re.sub(r"\s+", " ", clean).strip()
    # Cap length to prevent unbounded token usage
    return clean[:max_chars]


def create_fail_safe_output(summary: str = "Classifier failed - safely routed for manual triage.") -> ClassifierOutput:
    """Fail-safe fallback matching section 6.2 (triggers HR4 -> priority + manual review)."""
    return ClassifierOutput(
        intent="other",
        sub_intent="classifier_fallback",
        sentiment="neutral",
        urgency="high",
        previous_contact_mentioned=False,
        security_signal=False,
        legal_or_privacy_signal=False,
        threat_flag=False,
        entities=EntityExtraction(),
        summary=summary,
        requires_human=True,
        language="en",
        confidence=0.0,
    )


async def classify_ticket_message(
    body: str,
    subject: str | None = None,
    client: LLMClient | None = None,
) -> tuple[ClassifierOutput, bool]:
    """
    Classify an inbound customer message.

    Returns:
        (analysis: ClassifierOutput, is_fallback: bool)
    """
    if client is None:
        client = llm_client

    full_message = f"Subject: {subject}\n\n{body}" if subject else body
    sanitized = sanitize_customer_text(full_message)

    template = _load_prompt_template()
    prompt = template.format(customer_message=sanitized)

    # Attempt 1
    try:
        output = await client.generate_structured(prompt, ClassifierOutput)
        return output, False
    except Exception as first_exc:
        logger.warning("Classifier attempt 1 failed: %s. Retrying once...", first_exc)

    # Attempt 2 (One retry per section 6.2)
    try:
        output = await client.generate_structured(prompt, ClassifierOutput)
        return output, False
    except Exception as second_exc:
        logger.error(
            "Classifier attempt 2 failed: %s. Falling back to fail-safe manual review state.",
            second_exc,
        )

    # Fail safe: never drop or misroute a message
    return create_fail_safe_output(), True
