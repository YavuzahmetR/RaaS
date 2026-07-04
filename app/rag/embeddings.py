"""Local embeddings via sentence-transformers — $0 inference, provider-independent.

Model: intfloat/multilingual-e5-base (768 dims). E5 models REQUIRE role prefixes
("query: " / "passage: ") — skipping them measurably degrades retrieval quality,
so the two public functions bake them in and callers never deal with prefixes.

The model is loaded lazily on first use and cached as a module-level singleton
(loading takes seconds and must not happen at import time). Encoding is
CPU-bound, so async callers go through `asyncio.to_thread`.
"""

from __future__ import annotations

import asyncio
import threading

from app.config import get_settings

EMBEDDING_DIM = 768

_model = None
_lock = threading.Lock()


def _get_model():
    global _model
    if _model is None:
        with _lock:
            if _model is None:
                from sentence_transformers import SentenceTransformer

                _model = SentenceTransformer(get_settings().embedding_model)
    return _model


def _encode(texts: list[str]) -> list[list[float]]:
    vectors = _get_model().encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return [v.tolist() for v in vectors]


async def embed_passages(texts: list[str]) -> list[list[float]]:
    """Embed document chunks for indexing (adds the E5 'passage: ' prefix)."""
    return await asyncio.to_thread(_encode, [f"passage: {t}" for t in texts])


async def embed_query(text: str) -> list[float]:
    """Embed a search query (adds the E5 'query: ' prefix)."""
    result = await asyncio.to_thread(_encode, [f"query: {text}"])
    return result[0]
