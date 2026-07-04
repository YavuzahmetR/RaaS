# Eval Report

All numbers below are **measured on live runs** (no mocks) against the golden
dataset: 36 hand-curated question–answer–source triples over a 9-document,
23-chunk corpus (tenant `evalcorp`). The corpus deliberately includes **hard
negatives** — archived 2023 policy versions with different numbers and two
topically-overlapping third-party documents — because a saturated benchmark
(everything ≈ 1.0) proves nothing.

- Generator: DeepSeek `deepseek-chat` · Judge: Gemini `gemini-2.5-flash`
  (different vendor by design → no identity bias)
- Retrieval relevance is judged at document level (robust to chunking changes)
- Reproduce: `docker compose up -d`, ingest `sample_docs/evalcorp/*`, then
  `POST /eval/run` (see below)

## Retrieval metrics (n=36)

| Metric | Baseline (vector-only) | + Cross-encoder rerank | Δ |
|---|---|---|---|
| recall@1 | 0.69 | **0.89** | **+0.20** |
| recall@3 | 0.97 | **1.00** | +0.03 |
| recall@5 | 1.00 | 1.00 | — |
| MRR | 0.84 | **0.94** | **+0.10** |

Rerank: `cross-encoder/ms-marco-MiniLM-L-6-v2` over the top-20 vector
candidates → top-5. The improvement concentrates exactly where hard negatives
bite: rank-1 precision. The archived-2023 distractors frequently outrank the
current policy for the bi-encoder; the cross-encoder resolves most of them.

## Generation metrics (n=36, LLM-as-judge)

| Metric | Baseline | + Rerank | Δ |
|---|---|---|---|
| Faithfulness | 0.97 | 0.94 | −0.03 (noise) |
| Answer relevance | 0.98 | 0.94 | −0.04 (noise) |
| Context relevance | 0.36 | 0.35 | — |
| Self-check retry rate | 0.08 | 0.00 | — |

> The **+ Rerank** column was re-measured after the generation prompt was
> refined for plain-text, language-matched output (`_ANSWER_STYLE` in
> `app/agent/nodes.py`). Faithfulness held at 0.94; answer relevance stayed
> within the n=36 noise band; the cleaner prompt grounded first-try more often,
> so self-check retries fell to 0.00. Artifact:
> `eval/results/20260703T152422Z_generation_api.json`. The Baseline column
> predates the refinement (indicative, not a strict A/B).

**Honest reading:** generation metrics were already near ceiling and did not
move meaningfully — expected, because baseline recall@5 was already 1.00, so the
generator saw the right document either way; the ±0.04 swing is judge variance
at n=36.
Rerank's value here is rank-1 precision (context ordering), which matters as
k shrinks or the corpus grows. Context relevance ≈ 0.35 reflects that ~2 of 5
retrieved chunks are typically relevant on this corpus — a top-k tuning
opportunity, not a generation failure.

## Production metrics (Langfuse, 146 live traces)

| Metric | Value |
|---|---|
| Latency P50 | 5.2 s |
| Latency P95 | 14.6 s |
| Latency P99 | 22.4 s |
| Cost / query (mean) | **$0.00054** |
| Cost / query (max) | $0.00125 |

Latency is LLM-bound (2–4 sequential DeepSeek calls per agentic query:
router → generate → self-check, plus retries). Single LLM call ≈ 1.5 s.

## One-line summary (build-prompt format)

```
recall@1: 0.69 → 0.89 | MRR: 0.84 → 0.94 | faithfulness: 0.97 → 0.94 (flat/noise; recall@5 already 1.0)
```

## How to reproduce

```bash
# retrieval metrics (fast, no LLM)
curl -X POST localhost:8000/eval/run -H "Content-Type: application/json" \
     -d '{"mode":"retrieval","rerank":false}'
curl -X POST localhost:8000/eval/run -H "Content-Type: application/json" \
     -d '{"mode":"retrieval","rerank":true}'

# full generation eval (agent + judge, ~15 min)
curl -X POST localhost:8000/eval/run -H "Content-Type: application/json" \
     -d '{"mode":"generation"}' --max-time 3000
```

Raw per-question results: `eval/results/*.json`.

## Method notes & threats to validity

- The RAGAS metric trio (faithfulness / answer / context relevance) is computed
  by our own judge pipeline (`eval/llm_judge.py`) rather than the `ragas`
  library — see architecture decision D8. Judge model ≠ generator model.
- Dataset and corpus were authored together and pairwise spot-checked; labels
  are document-level, so chunk-boundary changes don't invalidate them.
- n=36 puts ~±0.05 noise on judge-based means; retrieval metrics are exact.
- The judge scores honest "the sources don't contain this" answers as faithful
  when true — refusal handling is explicit in the judge prompt.
