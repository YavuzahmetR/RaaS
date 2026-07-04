"""Generation-quality eval: faithfulness, answer relevance, context relevance.

NOTE ON NAMING — this module computes the three core RAGAS metrics but through
our own judge pipeline (eval/llm_judge.py, Gemini) instead of the `ragas`
library. Decision per the project fallback ladder: ragas pins a heavy
langchain/datasets dependency stack with recurring version conflicts, while the
underlying metrics are straightforward to compute with an independent judge —
and using a judge model different from the generator is a stronger setup than
ragas' default (avoids identity bias).

Runs the FULL pipeline per golden item (agent query end to end), then judges:
    python -m eval.run_ragas [--limit N]
"""

from __future__ import annotations

import argparse
import asyncio
import statistics
from typing import Any

from app.agent.graph import run_agent
from eval.common import load_dataset, save_result
from eval.llm_judge import (
    judge_answer_relevance,
    judge_context_relevance,
    judge_faithfulness,
)


async def _eval_one(tenant: str, item: dict[str, Any]) -> dict[str, Any]:
    state = await run_agent(query=item["question"], tenant_id=tenant)
    answer = state.get("answer", "")
    contexts = [d["text"] for d in state.get("retrieved_docs", [])]

    faith = await judge_faithfulness(answer, contexts)
    ans_rel = await judge_answer_relevance(item["question"], answer)
    ctx_rel = await judge_context_relevance(item["question"], contexts)
    return {
        "id": item["id"],
        "faithfulness": faith,
        "answer_relevance": ans_rel,
        "context_relevance": ctx_rel,
        "grounded": state.get("grounded"),
        "self_check_iterations": state.get("self_check_iterations"),
        "answer": answer,
    }


async def run_generation_eval(limit: int | None = None) -> dict[str, Any]:
    tenant, items = load_dataset(limit)
    rows = []
    for i, item in enumerate(items, 1):
        row = await _eval_one(tenant, item)
        rows.append(row)
        print(
            f"[{i}/{len(items)}] {row['id']}: faith={row['faithfulness']:.2f} "
            f"ans_rel={row['answer_relevance']:.2f} ctx_rel={row['context_relevance']:.2f}"
        )

    metrics = {
        "n": len(rows),
        "faithfulness": round(statistics.mean(r["faithfulness"] for r in rows), 4),
        "answer_relevance": round(statistics.mean(r["answer_relevance"] for r in rows), 4),
        "context_relevance": round(statistics.mean(r["context_relevance"] for r in rows), 4),
        "self_check_retry_rate": round(
            sum(1 for r in rows if (r["self_check_iterations"] or 0) > 1) / len(rows), 4
        ),
    }
    return {"metrics": metrics, "rows": rows}


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    result = await run_generation_eval(args.limit)
    m = result["metrics"]
    print("-" * 70)
    print(
        f"n={m['n']} | faithfulness: {m['faithfulness']:.2f} | "
        f"answer_relevance: {m['answer_relevance']:.2f} | "
        f"context_relevance: {m['context_relevance']:.2f}"
    )
    path = save_result("generation", result)
    print(f"saved -> {path}")


if __name__ == "__main__":
    asyncio.run(main())
