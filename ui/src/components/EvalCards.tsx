import type { EvalSummary } from "../types";

interface Props {
  summary: EvalSummary | null;
  blockedTotal: number;
}

function metric(value: unknown, digits = 2): string {
  return typeof value === "number" ? value.toFixed(digits) : "—";
}

interface CardProps {
  label: string;
  value: string;
  sub: string;
  accent?: boolean;
}

function Card({ label, value, sub, accent }: CardProps) {
  return (
    <div className="flex min-w-[120px] flex-1 flex-col gap-0.5 rounded-lg border border-line bg-raised px-3 py-2">
      <span className="text-[10px] uppercase tracking-wider text-dim">{label}</span>
      <span className={`font-mono text-xl font-semibold ${accent ? "text-signal" : "text-body"}`}>
        {value}
      </span>
      <span className="truncate font-mono text-[10px] text-dim/60" title={sub}>
        {sub}
      </span>
    </div>
  );
}

/** Metrics read live from eval/results/*.json via /eval/summary — the same
 *  artifacts the eval harness wrote. Nothing hardcoded in the component. */
export function EvalCards({ summary, blockedTotal }: Props) {
  const gen = summary?.generation;
  const ret = summary?.retrieval;
  const base = summary?.retrieval_baseline;

  const recall1 = ret?.metrics["recall@1"];
  const recallBase = base?.metrics["recall@1"];
  const delta =
    typeof recall1 === "number" && typeof recallBase === "number"
      ? ` (temele göre +${(recall1 - recallBase).toFixed(2)})`
      : "";

  return (
    <div className="flex flex-wrap gap-2">
      <Card
        label="sadakat (faithfulness)"
        value={metric(gen?.metrics.faithfulness)}
        sub={gen ? `LLM-yargıç · ${gen.file}` : "önce /eval/run çalıştır"}
        accent
      />
      <Card
        label="yanıt alakası"
        value={metric(gen?.metrics.answer_relevance)}
        sub={gen ? `n=${gen.metrics.n}` : "—"}
      />
      <Card
        label="recall@1"
        value={metric(recall1)}
        sub={ret ? `${ret.metrics.rerank ? "rerank" : "temel"}${delta}` : "—"}
        accent
      />
      <Card label="MRR" value={metric(ret?.metrics.mrr)} sub={ret ? ret.file : "—"} />
      <Card
        label="engellenen enjeksiyon"
        value={String(blockedTotal)}
        sub="canlı sayaç, bu oturum"
      />
    </div>
  );
}
