import type { QuerySummary } from "../types";

interface Props {
  summary: QuerySummary | null;
}

/** Big mono numbers: the measured total latency + real USD cost of the LAST
 *  query, straight from the provider adapter's per-call accounting. */
export function CostSummary({ summary }: Props) {
  return (
    <div className="flex flex-wrap items-baseline gap-x-8 gap-y-2">
      <div className="flex flex-col">
        <span className="text-[11px] uppercase tracking-wider text-dim">sorgu maliyeti</span>
        <span className="font-mono text-3xl font-semibold text-cost">
          {summary ? `$${summary.costUsd.toFixed(5)}` : "—"}
        </span>
      </div>
      <div className="flex flex-col">
        <span className="text-[11px] uppercase tracking-wider text-dim">toplam süre</span>
        <span className="font-mono text-3xl font-semibold text-body">
          {summary ? `${(summary.totalLatencyMs / 1000).toFixed(1)}s` : "—"}
        </span>
      </div>
      <div className="flex flex-col">
        <span className="text-[11px] uppercase tracking-wider text-dim">llm çağrısı</span>
        <span className="font-mono text-xl text-body">
          {summary ? summary.llmCalls : "—"}
        </span>
      </div>
      <div className="flex flex-col">
        <span className="text-[11px] uppercase tracking-wider text-dim">token giriş/çıkış</span>
        <span className="font-mono text-xl text-body">
          {summary ? `${summary.tokens.prompt}/${summary.tokens.completion}` : "—"}
        </span>
      </div>
    </div>
  );
}
