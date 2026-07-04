# RaaS — Agentic RAG-as-a-Service

A self-hostable RAG backend you can actually trust: **every answer is cited,
every request shows its dollar cost, and quality is measured by an eval harness
instead of vibes.** Multi-tenant, guardrailed, and it all comes up with one
`docker compose up`.

> ⚠️ This is a portfolio / reference project, not a managed service. It runs
> single-node and is meant to be read, run locally, and learned from.

## What it does

- **Answers from your own documents, with citations** — ask a question, get an
  answer grounded in the docs you ingested, with `[n]` sources you can check.
- **Shows its work** — a small web console lights up each step of the pipeline
  live (retrieve → rerank → generate → self-check → cite) with the real time and
  cost each step took.
- **Keeps tenants apart** — every document belongs to a tenant, and there is no
  way to search across tenants by accident (it's enforced in the search layer).
- **Defends itself** — prompt-injection filtering, PII redaction, and JWT auth,
  each proven by a test.

## Does it actually work? (measured, live runs — no mocks)

| Metric | Baseline | + Rerank |
|---|---|---|
| recall@1 | 0.69 | **0.89** |
| MRR | 0.84 | **0.94** |
| Faithfulness (LLM-judge) | 0.97 | 0.94 |
| Latency P50 / P95 | 5.2 s / 14.6 s | |
| Cost per query (avg) | **$0.0005** | |
| Guardrail tests | **36/36 passing** | |

Measured on a 36-question golden dataset with deliberate hard negatives; the
judge model (Gemini) is different from the generator (DeepSeek) so it can't grade
its own homework. Full numbers and honest caveats:
[docs/eval_report.md](docs/eval_report.md).

## How it works

```
Ingest:  n8n / upload → PII redaction → chunk → embed (local) → Qdrant + Postgres

Query:   you → guardrails (tenant ACL + injection filter)
              → agent loop:  router → retrieve → rerank → generate
                             → self-check (re-retrieve if not grounded, max 2)
                             → cite → PII redaction → answer
              ↑ every LLM call goes through one adapter (DeepSeek / Gemini /
                Bedrock / Azure) and is traced in Langfuse with its cost
```

## Quickstart (about 5 minutes)

```bash
git clone <repo> && cd raas
cp .env.example .env          # add your DEEPSEEK_API_KEY + GEMINI_API_KEY
docker compose up -d          # qdrant + postgres + langfuse + n8n + api + ui
curl localhost:8000/health

# ingest a doc, then ask about it
curl -F "file=@sample_docs/evalcorp/leave_policy.md" "localhost:8000/ingest?tenant=demo"
curl -X POST localhost:8000/query -H "Content-Type: application/json" \
     -d '{"tenant":"demo","query":"How many days of annual leave do I get?"}'
```

- **Proof console:** http://localhost:8080 — send a query and watch the pipeline
  run step by step, see the cost, and try an injection (`ignore all previous
  instructions...`) to watch it get blocked.
- **Langfuse (traces & cost):** http://localhost:3000
- **n8n (ingestion workflow):** http://localhost:5678

## Switching LLM provider

One environment variable, no code changes:

```bash
LLM_PROVIDER=deepseek   # or: gemini | bedrock | azure
```

Nothing in the code branches on which provider you picked — the choice lives in a
single factory. Bedrock and Azure ship as ready-to-fill stubs, so moving to AWS
or Azure is config plus one method, not a rewrite. Cost is computed inside the
adapter, which is why every trace carries a real dollar figure.

## Security (mapped to the OWASP LLM Top 10)

| Risk | Defense | Proven by |
|---|---|---|
| Prompt injection | regex families (free) + optional LLM classifier | `tests/test_injection.py` |
| Sensitive data leaks | PII redaction at ingest **and** on answers (email, phone, IBAN, cards, TC kimlik) | `tests/test_pii.py` |
| Cross-tenant access | tenant ACL enforced in the retrieval layer — no unfiltered search exists | `tests/test_acl.py` |
| Runaway cost | context/token caps + bounded self-check loop | `app/config.py` |

## Auth

JWT is **on by default** (`AUTH_ENABLED=true`). Tenant endpoints need a Bearer
token whose `tenant_id` matches the request, otherwise 401/403. Grab one from the
demo login (the proof console has a login box), or:

```bash
curl -X POST localhost:8000/auth/token -H "Content-Type: application/json" \
     -d '{"tenant":"evalcorp","password":"<AUTH_DEMO_PASSWORD from .env>"}'
```

`POST /auth/token` stands in for a real identity provider — swapping in
Supabase/OIDC is config, not code. Set `AUTH_ENABLED=false` for a token-free demo.

## Honest limits

- PII detection is regex-only for now; NER (spaCy/Presidio) is the planned next step.
- The LLM injection layer adds ~1s / ~$0.00003 per query; the free regex layer
  alone already blocks the known families.
- n=36 eval means ±0.05 noise on the judge metrics; retrieval metrics are exact.
- Latency is LLM-bound (a few sequential calls) — streaming and parallel judge
  calls are the obvious next wins.
- Single-node Qdrant/Postgres, no high-availability story. Reference impl, not a
  product.

## Repo map

```
app/            FastAPI + agent + rag + guardrails + observability + providers
ui/             proof console (React + Vite + Tailwind, SSE trace)
eval/           golden_dataset.json (36 Q) · retrieval + LLM-judge harness
tests/          test_acl / test_injection / test_pii / test_e2e (36 tests)
sample_docs/    reproducible corpus incl. archived hard negatives
n8n/            ingestion workflow (working export)
docs/           eval_report.md (metrics + caveats)
```

## License

MIT — see [LICENSE](LICENSE). Use it, fork it, learn from it.
