"""Ingestion pipeline: parse (PDF/txt) → chunk → embed → Qdrant + Postgres metadata."""

from __future__ import annotations

import io
import uuid
from dataclasses import dataclass

from app.config import get_settings
from app.rag import metadata, store
from app.rag.chunking import chunk_text
from app.rag.embeddings import embed_passages

SUPPORTED_SUFFIXES = (".pdf", ".txt", ".md")


class IngestError(ValueError):
    """User-facing ingestion failure (bad file type, empty document, ...)."""


def _extract_text(filename: str, payload: bytes) -> str:
    name = filename.lower()
    if name.endswith(".pdf"):
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(payload))
        return "\n\n".join(page.extract_text() or "" for page in reader.pages)
    if name.endswith((".txt", ".md")):
        return payload.decode("utf-8", errors="replace")
    raise IngestError(
        f"Unsupported file type: {filename!r}. Supported: {', '.join(SUPPORTED_SUFFIXES)}"
    )


@dataclass(frozen=True, slots=True)
class IngestResult:
    doc_id: str
    tenant_id: str
    filename: str
    chunk_count: int


async def ingest_document(*, tenant_id: str, filename: str, payload: bytes) -> IngestResult:
    if not tenant_id or not tenant_id.strip():
        raise IngestError("tenant_id is required")
    if not payload:
        raise IngestError("Empty file")

    text = _extract_text(filename, payload)
    if not text.strip():
        raise IngestError(f"No extractable text in {filename!r}")

    # Guardrail: PII is redacted BEFORE embedding, so raw PII never reaches
    # the vector store or LLM context.
    from app.guardrails.pii import redact

    text = redact(text)

    settings = get_settings()
    chunks = chunk_text(text, settings.chunk_size, settings.chunk_overlap)
    if not chunks:
        raise IngestError(f"Chunking produced no chunks for {filename!r}")

    texts = [c.text for c in chunks]
    vectors = await embed_passages(texts)

    doc_id = str(uuid.uuid4())
    count = await store.upsert_chunks(
        tenant_id=tenant_id.strip(),
        doc_id=doc_id,
        source=filename,
        texts=texts,
        vectors=vectors,
    )
    await metadata.record_document(
        doc_id=doc_id,
        tenant_id=tenant_id.strip(),
        filename=filename,
        source="api-upload",
        chunk_count=count,
    )
    return IngestResult(
        doc_id=doc_id, tenant_id=tenant_id.strip(), filename=filename, chunk_count=count
    )
