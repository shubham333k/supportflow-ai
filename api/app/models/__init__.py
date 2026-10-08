# Models package — expose all models for Alembic discovery
from api.app.models.base import Base
from api.app.models.tables import (
    AIAnalysis,
    AuditEvent,
    Customer,
    Draft,
    KBChunk,
    KBDocument,
    Message,
    SLATimer,
    Ticket,
)

__all__ = [
    "Base",
    "Customer",
    "Ticket",
    "Message",
    "AIAnalysis",
    "Draft",
    "KBDocument",
    "KBChunk",
    "SLATimer",
    "AuditEvent",
]
