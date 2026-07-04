"""LangGraph node implementations.

Each node is a pure-ish async function: reads the state, calls at most one
LLM/tool/retrieval operation, returns ONLY the keys it changed.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.agent.state import MAX_SELF_CHECK_ITERATIONS, AgentState
from app.agent.tools import call_tool
from app.config import get_settings
from app.observability.langfuse_setup import observe, traced_generate
from app.providers.base import system, user
from app.rag.retrieve import retrieve_chunks

log = logging.getLogger("raas.agent")


def _parse_json(text: str) -> dict[str, Any]:
    """Extract the first JSON object from an LLM reply (tolerates code fences)."""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return {}
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return {}


def _step(state: AgentState, name: str) -> list[str]:
    return [*state.get("steps", []), name]


# Shared answer-style contract applied to every user-facing answer. The UI (and
# API consumers) render the answer verbatim as plain text, so stray Markdown like
# **bold** shows its literal asterisks. This keeps output clean and multilingual.
_ANSWER_STYLE = (
    "Answer style:\n"
    "- Write in clear, natural prose. Do NOT use Markdown: no **bold**, *italics*, "
    "`code`, # headings, or tables — the answer is displayed as plain text. "
    'Plain hyphen lists ("- ") are acceptable when listing several items.\n'
    '- Be concise and direct; skip filler openers like "Based on the sources '
    'provided".\n'
    "- Reply in the same language as the user's question."
)


# --------------------------------------------------------------------------- #
# router — does this query need retrieval, a tool, or a direct answer?
# --------------------------------------------------------------------------- #
_ROUTER_PROMPT = """You are the router of a document-QA agent. Classify the user query:

- "docs": needs information from the tenant's ingested documents
- "list_docs": asks what documents/files exist or were uploaded
- "direct": greeting, small talk, or general knowledge that needs no documents

Reply with JSON only: {"route": "docs" | "list_docs" | "direct"}"""


@observe(name="router")
async def router(state: AgentState) -> AgentState:
    resp = await traced_generate(
        "llm:router",
        [system(_ROUTER_PROMPT), user(state["query"])],
        temperature=0.0,
        max_tokens=32,
    )
    route = _parse_json(resp.text).get("route")
    if route not in ("docs", "list_docs", "direct"):
        route = "docs"  # safe default: prefer grounded answers
    log.info("router: %r -> %s", state["query"][:60], route)
    return {"route": route, "current_query": state["query"], "steps": _step(state, "router")}


# --------------------------------------------------------------------------- #
# retrieve — tenant-filtered vector search (ACL enforced in the store layer)
# --------------------------------------------------------------------------- #
@observe(name="retrieve")
async def retrieve(state: AgentState) -> AgentState:
    query = state.get("current_query") or state["query"]
    hits = await retrieve_chunks(tenant_id=state["tenant_id"], query=query)
    docs = [
        {
            "n": i + 1,
            "text": h.text,
            "score": h.score,
            "doc_id": h.doc_id,
            "source": h.source,
            "chunk_index": h.chunk_index,
        }
        for i, h in enumerate(hits)
    ]
    log.info("retrieve: %r -> %d hits", query[:60], len(docs))
    return {"retrieved_docs": docs, "steps": _step(state, "retrieve")}


# --------------------------------------------------------------------------- #
# generate — answer (with [n] citation markers when grounded in docs)
# --------------------------------------------------------------------------- #
_GENERATE_GROUNDED = """Answer the user's question using ONLY the sources below.
Cite every claim with its source number in square brackets, e.g. [1] or [2].
If the sources do not contain the answer, say so explicitly instead of guessing.

{style}
- Keep the [n] citation markers exactly as square-bracketed numbers.

Sources:
{context}"""


@observe(name="generate")
async def generate(state: AgentState) -> AgentState:
    if state.get("route") == "direct":
        resp = await traced_generate(
            "llm:generate_direct",
            [
                system(f"You are a concise, helpful assistant. Answer briefly.\n\n{_ANSWER_STYLE}"),
                user(state["query"]),
            ],
            temperature=0.3,
            max_tokens=256,
        )
        return {"answer": resp.text.strip(), "steps": _step(state, "generate")}

    # Guardrail: hard context budget (token-bomb protection) — stop adding
    # sources once the cap is reached instead of truncating mid-chunk.
    budget = get_settings().max_context_chars
    parts: list[str] = []
    used = 0
    for d in state.get("retrieved_docs", []):
        block = f"[{d['n']}] (from {d['source']}):\n{d['text']}"
        if used + len(block) > budget:
            break
        parts.append(block)
        used += len(block)
    context = "\n\n".join(parts) or "(no sources retrieved)"
    resp = await traced_generate(
        "llm:generate_grounded",
        [
            system(_GENERATE_GROUNDED.format(style=_ANSWER_STYLE, context=context)),
            user(state["query"]),
        ],
        temperature=0.1,
        max_tokens=512,
    )
    return {"answer": resp.text.strip(), "steps": _step(state, "generate")}


# --------------------------------------------------------------------------- #
# self_check — is the answer consistent with the sources? (max 2 retry loops)
# --------------------------------------------------------------------------- #
_SELF_CHECK_PROMPT = """You are a strict verifier. Given sources, a question and an answer,
decide if the answer is fully supported by the sources.

Mark grounded=false in BOTH of these cases:
1. The answer makes claims the sources do not support.
2. The answer states the sources lack the needed information (retrieval may have
   missed relevant chunks — propose a differently-worded retrieval query).

Reply with JSON only:
{"grounded": true/false, "reformulated_query": "<better retrieval query if not grounded, else empty>"}"""


@observe(name="self_check")
async def self_check(state: AgentState) -> AgentState:
    iterations = state.get("self_check_iterations", 0)
    context = "\n\n".join(
        f"[{d['n']}]: {d['text']}" for d in state.get("retrieved_docs", [])
    ) or "(none)"
    resp = await traced_generate(
        "llm:self_check",
        [
            system(_SELF_CHECK_PROMPT),
            user(
                f"Sources:\n{context}\n\nQuestion: {state['query']}\n\n"
                f"Answer: {state.get('answer', '')}"
            ),
        ],
        temperature=0.0,
        max_tokens=128,
    )
    verdict = _parse_json(resp.text)
    grounded = bool(verdict.get("grounded", True))
    updates: AgentState = {
        "grounded": grounded,
        "self_check_iterations": iterations + 1,
        "steps": _step(state, f"self_check#{iterations + 1}:{'ok' if grounded else 'RETRY'}"),
    }
    if not grounded and iterations + 1 < MAX_SELF_CHECK_ITERATIONS + 1:
        reformulated = (verdict.get("reformulated_query") or "").strip()
        if reformulated:
            updates["current_query"] = reformulated
    log.info("self_check: grounded=%s iteration=%d", grounded, iterations + 1)
    return updates


# --------------------------------------------------------------------------- #
# cite — attach provenance for the [n] markers actually used in the answer
# --------------------------------------------------------------------------- #
@observe(name="cite")
async def cite(state: AgentState) -> AgentState:
    docs = state.get("retrieved_docs", [])
    answer = state.get("answer", "")
    used_ns = {int(n) for n in re.findall(r"\[(\d+)\]", answer)}
    cited = [d for d in docs if d["n"] in used_ns] or docs[:1] if docs else []
    citations = [
        {
            "n": d["n"],
            "doc_id": d["doc_id"],
            "source": d["source"],
            "chunk_index": d["chunk_index"],
            "score": round(d["score"], 4),
        }
        for d in cited
    ]
    scores = [c["score"] for c in citations]
    confidence = round(sum(scores) / len(scores), 4) if scores else 0.0
    if not state.get("grounded", True):
        confidence = round(confidence * 0.5, 4)  # penalise unresolved self-check
    return {
        "citations": citations,
        "confidence": confidence,
        "steps": _step(state, "cite"),
    }


# --------------------------------------------------------------------------- #
# list_docs — allowlisted metadata tool (tool-calling path)
# --------------------------------------------------------------------------- #
@observe(name="tool:list_documents")
async def list_docs(state: AgentState) -> AgentState:
    docs = await call_tool("list_documents", tenant_id=state["tenant_id"])
    if docs:
        lines = "\n".join(
            f"- {d['filename']} ({d['chunk_count']} chunks, ingested {d['created_at']})"
            for d in docs
        )
        answer = f"Your tenant has {len(docs)} ingested document(s):\n{lines}"
    else:
        answer = "No documents have been ingested for your tenant yet."
    return {
        "answer": answer,
        "citations": [],
        "confidence": 1.0,
        "steps": _step(state, "tool:list_documents"),
    }
