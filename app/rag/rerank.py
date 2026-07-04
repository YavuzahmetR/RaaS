"""Cross-encoder reranking — the measured improvement of the eval harness.

A bi-encoder (e5) retrieves a wide candidate set fast; the cross-encoder scores
each (query, chunk) pair jointly and re-orders them. Slower per pair, so it only
sees the top candidates. Enabled via RERANK_ENABLED (or per-request override);
before/after impact is measured in eval/ and reported in docs/eval_report.md.
"""

from __future__ import annotations

import asyncio
import math
import threading

from app.rag.store import Hit

RERANK_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
# Candidate pool multiplier: rerank sees top_k * FETCH_MULTIPLIER vector hits.
FETCH_MULTIPLIER = 4

_model = None
_lock = threading.Lock()


def _sigmoid(x: float) -> float:
    """Map a cross-encoder logit to a relevance probability in (0, 1).

    ms-marco cross-encoders are trained with a relevance objective, so
    sigmoid(logit) IS the calibrated P(relevant) — the semantically correct
    normalisation. Monotonic, so it never changes ranking; it only bounds the
    score (raw logits can be ~-12..+12, which is why confidence used to exceed
    1.0). Numerically stable for both signs.
    """
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    z = math.exp(x)
    return z / (1.0 + z)


def _get_model():
    global _model
    if _model is None:
        with _lock:
            if _model is None:
                from sentence_transformers import CrossEncoder

                _model = CrossEncoder(RERANK_MODEL)
    return _model


def _score(query: str, hits: list[Hit]) -> list[Hit]:
    scores = _get_model().predict([(query, h.text) for h in hits], show_progress_bar=False)
    ranked = sorted(zip(hits, scores, strict=True), key=lambda p: float(p[1]), reverse=True)
    # Replace the vector score with the cross-encoder relevance probability
    # (sigmoid of the logit): 0-1, calibrated, and consistent with the cosine
    # scores of the no-rerank path — so confidence is always a real 0-1 value.
    return [
        Hit(
            text=h.text,
            score=_sigmoid(float(s)),
            doc_id=h.doc_id,
            source=h.source,
            chunk_index=h.chunk_index,
        )
        for h, s in ranked
    ]


async def rerank(query: str, hits: list[Hit], top_k: int) -> list[Hit]:
    if not hits:
        return []
    ranked = await asyncio.to_thread(_score, query, hits)
    return ranked[:top_k]
