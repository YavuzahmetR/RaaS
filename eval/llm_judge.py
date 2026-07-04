"""LLM-as-judge metrics: faithfulness, answer relevance, context relevance.

The judge model is DIFFERENT from the generation model by configuration
(generation: DeepSeek -> judge: JUDGE_PROVIDER, default Gemini) to avoid
identity bias: a model grading its own output systematically inflates scores.

Each metric is scored 0-10 by the judge with a reason, then normalised to 0-1.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any

from app.config import get_settings
from app.providers.base import Message, system, user
from app.providers.factory import get_provider

log = logging.getLogger("raas.eval")

# Backoff schedule for transient judge-API failures (503 high demand, 429).
_RETRY_DELAYS_S = (5, 15, 45)

_FAITHFULNESS = """You are an impartial evaluator. Score how faithful the ANSWER is
to the SOURCES on a 0-10 scale: 10 = every claim is directly supported; 0 = fabricated.
An answer that honestly states the sources lack the information scores 10 IF the
sources indeed lack it. Reply JSON only: {"score": 0-10, "reason": "<short>"}"""

_ANSWER_RELEVANCE = """You are an impartial evaluator. Score 0-10 how well the ANSWER
addresses the QUESTION (completeness and directness, regardless of factual accuracy).
Reply JSON only: {"score": 0-10, "reason": "<short>"}"""

_CONTEXT_RELEVANCE = """You are an impartial evaluator. Given a QUESTION and N retrieved
CONTEXT chunks, count how many chunks contain information relevant to answering it.
Reply JSON only: {"relevant_count": <int>, "reason": "<short>"}"""


def _judge():
    s = get_settings()
    return get_provider(s.judge_provider)


async def _judge_generate(messages: list[Message], **kwargs: Any):
    """Judge call with exponential backoff: a single transient 503/429 must
    not kill a 36-item eval run. Non-transient errors propagate immediately."""
    last_exc: Exception | None = None
    for attempt, delay in enumerate((0, *_RETRY_DELAYS_S)):
        if delay:
            await asyncio.sleep(delay)
        try:
            return await _judge().generate(messages, **kwargs)
        except Exception as e:  # provider-specific error classes vary
            status = getattr(e, "code", None) or getattr(e, "status_code", None)
            if status not in (429, 503):
                raise
            last_exc = e
            log.warning("judge API %s, retry %d/%d", status, attempt + 1, len(_RETRY_DELAYS_S))
    raise last_exc  # type: ignore[misc]


def _parse(text: str) -> dict[str, Any]:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return {}
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return {}


async def judge_faithfulness(answer: str, contexts: list[str]) -> float:
    src = "\n\n".join(f"[{i+1}] {c}" for i, c in enumerate(contexts)) or "(none)"
    resp = await _judge_generate(
        [system(_FAITHFULNESS), user(f"SOURCES:\n{src}\n\nANSWER:\n{answer}")],
        temperature=0.0,
        max_tokens=256,
    )
    score = _parse(resp.text).get("score")
    return round(float(score) / 10, 4) if score is not None else 0.0


async def judge_answer_relevance(question: str, answer: str) -> float:
    resp = await _judge_generate(
        [system(_ANSWER_RELEVANCE), user(f"QUESTION:\n{question}\n\nANSWER:\n{answer}")],
        temperature=0.0,
        max_tokens=256,
    )
    score = _parse(resp.text).get("score")
    return round(float(score) / 10, 4) if score is not None else 0.0


async def judge_context_relevance(question: str, contexts: list[str]) -> float:
    if not contexts:
        return 0.0
    src = "\n\n".join(f"[{i+1}] {c}" for i, c in enumerate(contexts))
    resp = await _judge_generate(
        [system(_CONTEXT_RELEVANCE), user(f"QUESTION:\n{question}\n\nCONTEXTS ({len(contexts)}):\n{src}")],
        temperature=0.0,
        max_tokens=256,
    )
    count = _parse(resp.text).get("relevant_count")
    if count is None:
        return 0.0
    return round(min(float(count), len(contexts)) / len(contexts), 4)
