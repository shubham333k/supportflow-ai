"""
POST /api/v1/messages/ingest — idempotent message ingestion.
"""

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.app.core.security import verify_api_key
from api.app.models.database import get_db
from api.app.schemas.messages import IngestMessageRequest, IngestMessageResponse
from api.app.services.tickets import ingest_message

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/messages", tags=["Messages"], dependencies=[Depends(verify_api_key)])


@router.post("/ingest", response_model=IngestMessageResponse)
async def ingest(
    payload: IngestMessageRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Idempotent message ingestion.

    - Upsert customer (DB + later HubSpot contact)
    - Match ticket by thread_id or create one
    - Store inbound message (unique on external_message_id)
    - Returns {ticket_id, is_duplicate, is_reopen}
    """
    return await ingest_message(db, payload)
