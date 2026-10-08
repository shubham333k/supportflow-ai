"""
Pydantic schemas for the draft endpoint (POST /tickets/{id}/draft).
"""

from pydantic import BaseModel


class DraftSource(BaseModel):
    """A single KB chunk used in the draft."""

    chunk_id: str
    doc: str
    heading: str | None = None
    similarity: float


class DraftResponse(BaseModel):
    """Returned from POST /tickets/{id}/draft."""

    ticket_id: str
    send_mode: str  # auto | approval | ack_only | none
    reply: str | None = None
    sources: list[DraftSource] = []
    answerable: bool = False
    verifier_passed: bool | None = None
    handoff: bool = False
    tier: str  # may be raised by HR5
