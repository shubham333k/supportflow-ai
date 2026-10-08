"""
Pydantic schemas for the AI analysis endpoint (POST /tickets/{id}/analyze).
Section 6.2 of the plan — classifier output, validated with one retry.
"""

from pydantic import BaseModel, Field


class EntityExtraction(BaseModel):
    """Extracted business entities matching section 6.2."""

    amount: str | float | None = None
    order_id: str | None = None
    product: str | None = None


class ClassifierOutput(BaseModel):
    """Structured output the LLM must return (section 6.2)."""

    intent: str = Field(
        ...,
        pattern=(
            r"^(billing_issue|refund_request|account_access|subscription_change|"
            r"technical_issue|product_question|feature_request|complaint|"
            r"sales_question|security_issue|general_question|other)$"
        ),
    )
    sub_intent: str | None = None
    sentiment: str = Field(
        ...,
        pattern=r"^(positive|neutral|negative|frustrated|angry)$",
    )
    urgency: str = Field(
        ...,
        pattern=r"^(low|medium|high|critical)$",
    )
    previous_contact_mentioned: bool = False
    security_signal: bool = False
    legal_or_privacy_signal: bool = False
    threat_flag: bool = False
    entities: EntityExtraction = Field(default_factory=EntityExtraction)
    summary: str = ""
    requires_human: bool = False
    language: str = "en"
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class ScoreBreakdown(BaseModel):
    """Explainable breakdown stored with every analysis (section 7.1)."""

    urgency: int = 0
    sentiment: int = 0
    customer: int = 0
    issue: int = 0
    prior_failed: int = 0
    sla_risk: int = 0
    threat: int = 0


class AnalyzeResponse(BaseModel):
    """Returned from POST /tickets/{id}/analyze."""

    ticket_id: str
    score: int
    tier: str
    intent: str | None = None
    breakdown: ScoreBreakdown
    hard_rule_hits: list[str] = []
    needs_manual_review: bool = False
