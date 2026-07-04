"""Retrieval-only metrics: recall@k and MRR, independent of generation.

Relevance is judged at the document level: a hit counts if it comes from the
golden item's labelled source document. Document-level labels are robust to
chunking changes, so the same dataset keeps working while chunking is tuned.

Run inside the api container (uses internal retrieval directly):
    python -m eval.retrieval_eval [--limit N] [--rerank on|off|both]
"""

from __future__ import annotations

import argparse
import asyncio
from typing import Any

from app.rag.retrieve import retrieve_chunks
from eval.common import load_dataset, save_result

K_VALUES = (1, 3, 5)


async def _eval_one(
    tenant: str, item: dict[str, Any], use_rerank: bool, top_k: int
) -> dict[str, Any]:
    hits = await retrieve_chunks(
        tenant_id=tenant, query=item["question"], top_k=top_k, use_rerank=use_rerank
    )
    sources = [h.source for h in hits]
    first_rank = next((i + 1 for i, s in enumerate(sources) if s == item["source"]), None)
    return {
        "id": item["id"],
        "expected": item["source"],
        "got": sources,
        "first_rank": first_rank,
    }


async def run_retrieval_eval(
    *, use_rerank: bool, limit: int | None = None, top_k: int = 5
) -> dict[str, Any]:
    tenant, items = load_dataset(limit)
    rows = [await _eval_one(tenant, item, use_rerank, top_k) for item in items]

    n = len(rows)
    metrics: dict[str, Any] = {"n": n, "rerank": use_rerank}
    for k in K_VALUES:
        hits_at_k = sum(1 for r in rows if r["first_rank"] is not None and r["first_rank"] <= k)
        metrics[f"recall@{k}"] = round(hits_at_k / n, 4)
    metrics["mrr"] = round(
        sum(1.0 / r["first_rank"] for r in rows if r["first_rank"] is not None) / n, 4
    )
    misses = [r["id"] for r in rows if r["first_rank"] is None or r["first_rank"] > top_k]
    return {"metrics": metrics, "misses": misses, "rows": rows}


def _fmt(m: dict[str, Any]) -> str:
    return (
        f"rerank={'ON ' if m['rerank'] else 'OFF'} | n={m['n']} | "
        + " | ".join(f"recall@{k}: {m[f'recall@{k}']:.2f}" for k in K_VALUES)
        + f" | MRR: {m['mrr']:.2f}"
    )


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--rerank", choices=["on", "off", "both"], default="off")
    args = parser.parse_args()

    modes = [False, True] if args.rerank == "both" else [args.rerank == "on"]
    results = {}
    for mode in modes:
        res = await run_retrieval_eval(use_rerank=mode, limit=args.limit)
        results["rerank_on" if mode else "rerank_off"] = res
        print(_fmt(res["metrics"]))
        if res["misses"]:
            print(f"  misses (not in top-5): {res['misses']}")
    path = save_result("retrieval", results)
    print(f"saved -> {path}")


if __name__ == "__main__":
    asyncio.run(main())
