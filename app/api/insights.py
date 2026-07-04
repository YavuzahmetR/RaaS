"""Read-only insight endpoints for the proof UI.

- /guardrails/log  — recent injection-check events (pass + block, ring buffer)
- /eval/summary    — latest *real* eval harness results from eval/results/*.json
- /tenants         — distinct tenants that have ingested documents

The eval summary deliberately reads the same JSON artifacts the harness wrote
(`/eval/run` → eval.common.save_result); nothing is hardcoded in the UI.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Query

from app.guardrails.events import blocked_count, recent_events
from app.rag import metadata
from eval.common import RESULTS_DIR

router = APIRouter(tags=["proof-ui"])


@router.get("/guardrails/log")
async def guardrails_log(limit: int = Query(default=25, ge=1, le=100)) -> dict:
    return {"events": recent_events(limit), "blocked_total": blocked_count()}


@router.get("/tenants")
async def tenants() -> dict:
    return {"tenants": await metadata.list_tenants()}


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None  # a corrupt artifact should not take the endpoint down


def _latest(files: list[Path], *, want_rerank: bool | None = None) -> dict[str, Any] | None:
    """Newest matching result. Filenames sort chronologically (UTC stamp prefix)."""
    for path in sorted(files, reverse=True):
        data = _load_json(path)
        if data is None:
            continue
        metrics = data.get("metrics", {})
        if want_rerank is not None and bool(metrics.get("rerank")) != want_rerank:
            continue
        return {"file": path.name, "metrics": metrics}
    return None


@router.get("/eval/summary")
async def eval_summary() -> dict:
    """Latest measured eval metrics, straight from the harness artifacts."""
    if not RESULTS_DIR.is_dir():
        return {"retrieval": None, "retrieval_baseline": None, "generation": None}
    retrieval_files = list(RESULTS_DIR.glob("*retrieval*.json"))
    generation_files = list(RESULTS_DIR.glob("*generation*.json"))
    return {
        "retrieval": _latest(retrieval_files, want_rerank=True)
        or _latest(retrieval_files),
        "retrieval_baseline": _latest(retrieval_files, want_rerank=False),
        "generation": _latest(generation_files),
    }
