"""
Knowledge base endpoints — ingest, search, and document status.
"""

import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.app.core.security import verify_api_key
from api.app.models.database import get_db
from api.app.models.tables import KBDocument
from api.app.schemas.drafts import DraftSource
from api.app.services.rag import ingest_all_kb_files, retrieve_relevant_chunks

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/kb", tags=["Knowledge Base"], dependencies=[Depends(verify_api_key)])


@router.post("/ingest")
async def ingest_kb(
    db: AsyncSession = Depends(get_db),
):
    """Scan and index all markdown files from the kb/ directory."""
    result = await ingest_all_kb_files(db)
    return {"status": "ok", **result}


@router.get("/search", response_model=list[DraftSource])
async def search_kb(
    q: str = Query(..., min_length=1, description="Search query"),
    top_k: int = Query(4, ge=1, le=10),
    threshold: float = Query(0.40, ge=0.0, le=1.0),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve top knowledge chunks for a query using cosine similarity."""
    chunks = await retrieve_relevant_chunks(
        db, query=q, top_k=top_k, similarity_threshold=threshold
    )
    return [
        DraftSource(
            chunk_id=c.chunk_id,
            doc=c.doc_title,
            heading=c.heading_path,
            similarity=round(c.similarity, 4),
        )
        for c in chunks
    ]


@router.get("/documents")
async def list_kb_documents(
    db: AsyncSession = Depends(get_db),
):
    """List all indexed documents with version and chunk counts."""
    stmt = select(KBDocument).order_by(KBDocument.filename)
    res = await db.execute(stmt)
    docs = res.scalars().all()
    return [
        {
            "id": str(d.id),
            "filename": d.filename,
            "title": d.title,
            "version": d.version,
            "chunk_count": d.chunk_count,
            "status": d.status,
            "updated_at": d.updated_at.isoformat() if d.updated_at else None,
        }
        for d in docs
    ]
