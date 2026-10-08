"""
Knowledge base ingestion, heading-based chunking, and vector retrieval.
Implements section 8 of the implementation plan:
- Heading-based markdown chunking (H2/H3)
- Embedding generation (768 dimensions, L2-normalized)
- Cosine similarity vector search
- Idempotent document ingestion via content hash
"""

import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.app.integrations.llm import llm_client
from api.app.models.tables import KBChunk, KBDocument

logger = logging.getLogger(__name__)

KB_DIR_DEFAULT = Path(__file__).resolve().parent.parent.parent.parent / "kb"


@dataclass
class ParsedChunk:
    """A heading-chunk parsed from a markdown document."""

    index: int
    heading_path: str
    content: str


@dataclass
class RetrievedChunk:
    """A retrieved knowledge chunk with cosine similarity score."""

    chunk_id: str
    doc_id: str
    doc_title: str
    heading_path: str
    content: str
    similarity: float


def parse_markdown_by_headings(content: str, filename: str) -> list[ParsedChunk]:
    """
    Split markdown by H2 (##) and H3 (###) headings.
    Prefixes each chunk with the document title and heading path per section 8.2.
    """
    lines = content.splitlines()
    doc_title = filename.replace(".md", "").replace("-", " ").title()

    # Extract H1 if present
    for line in lines:
        if line.startswith("# "):
            doc_title = line[2:].strip()
            break

    chunks: list[ParsedChunk] = []
    current_heading = "Overview"
    current_lines: list[str] = []
    chunk_idx = 0

    def _flush_chunk():
        nonlocal chunk_idx, current_lines
        body = "\n".join(current_lines).strip()
        if body:
            full_content = f"[Document: {doc_title} > Section: {current_heading}]\n{body}"
            chunks.append(
                ParsedChunk(
                    index=chunk_idx,
                    heading_path=f"{doc_title} > {current_heading}",
                    content=full_content,
                )
            )
            chunk_idx += 1
        current_lines = []

    for line in lines:
        if line.startswith("# ") and not current_lines:
            continue
        if line.startswith("## ") or line.startswith("### "):
            _flush_chunk()
            current_heading = line.lstrip("#").strip()
        else:
            current_lines.append(line)

    _flush_chunk()
    return chunks


def compute_content_hash(text: str) -> str:
    """Compute SHA-256 hash of document text to detect modifications."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


async def ingest_kb_document(
    db: AsyncSession,
    file_path: Path,
) -> tuple[KBDocument, bool]:
    """
    Ingest or update a single markdown document into the database.
    Skips if content hash has not changed.

    Returns:
        (document, was_updated)
    """
    filename = file_path.name
    with open(file_path, encoding="utf-8") as f:
        content = f.read()

    new_hash = compute_content_hash(content)

    # Check existing document
    stmt = select(KBDocument).where(KBDocument.filename == filename)
    res = await db.execute(stmt)
    doc = res.scalar_one_or_none()

    if doc is not None and doc.content_hash == new_hash:
        return doc, False

    parsed_chunks = parse_markdown_by_headings(content, filename)
    doc_title = filename.replace(".md", "").replace("-", " ").title()
    for line in content.splitlines():
        if line.startswith("# "):
            doc_title = line[2:].strip()
            break

    if doc is None:
        doc = KBDocument(
            filename=filename,
            title=doc_title,
            doc_type="policy",
            version=1,
            content_hash=new_hash,
            chunk_count=len(parsed_chunks),
            status="ready",
        )
        db.add(doc)
        await db.flush()
    else:
        doc.title = doc_title
        doc.version += 1
        doc.content_hash = new_hash
        doc.chunk_count = len(parsed_chunks)
        doc.status = "ready"
        # Delete old chunks
        await db.execute(delete(KBChunk).where(KBChunk.document_id == doc.id))
        await db.flush()

    # Generate embeddings and insert chunks
    for chunk in parsed_chunks:
        embedding = await llm_client.generate_embedding(chunk.content)
        kb_chunk = KBChunk(
            document_id=doc.id,
            chunk_index=chunk.index,
            heading_path=chunk.heading_path,
            content=chunk.content,
            embedding=embedding,
        )
        db.add(kb_chunk)

    await db.flush()
    return doc, True


async def ingest_all_kb_files(
    db: AsyncSession,
    kb_dir: Path | None = None,
) -> dict[str, Any]:
    """Scan and ingest all .md files in the kb directory."""
    target_dir = kb_dir or KB_DIR_DEFAULT
    if not target_dir.exists():
        raise FileNotFoundError(f"KB directory {target_dir} does not exist.")

    md_files = list(target_dir.glob("*.md"))
    processed = 0
    updated = 0

    for file_path in md_files:
        _, was_upd = await ingest_kb_document(db, file_path)
        processed += 1
        if was_upd:
            updated += 1

    await db.commit()
    logger.info("Ingested %d KB files (%d updated)", processed, updated)
    return {"total_files": processed, "updated_files": updated}


async def retrieve_relevant_chunks(
    db: AsyncSession,
    query: str,
    top_k: int = 4,
    similarity_threshold: float = 0.20,
) -> list[RetrievedChunk]:
    """
    Retrieve top-k knowledge base chunks using cosine similarity.
    Calculates dot product across L2-normalized embeddings.
    """
    query_emb = await llm_client.generate_embedding(query)

    # Fetch all chunks with their document titles
    stmt = (
        select(KBChunk, KBDocument.title)
        .join(KBDocument, KBChunk.document_id == KBDocument.id)
    )
    result = await db.execute(stmt)
    rows = result.all()

    scored: list[RetrievedChunk] = []

    for chunk, doc_title in rows:
        emb = chunk.embedding
        if not emb:
            continue
        # If stored as string / list in SQLite or pgvector
        if isinstance(emb, str):
            import json
            emb = json.loads(emb)

        # Dot product of normalized vectors = cosine similarity
        sim = sum(q * c for q, c in zip(query_emb, emb, strict=False))
        scored.append(
            RetrievedChunk(
                chunk_id=str(chunk.id),
                doc_id=str(chunk.document_id),
                doc_title=doc_title or "",
                heading_path=chunk.heading_path or "",
                content=chunk.content,
                similarity=float(sim),
            )
        )

    scored.sort(key=lambda x: x.similarity, reverse=True)
    return [c for c in scored[:top_k] if c.similarity >= similarity_threshold]
