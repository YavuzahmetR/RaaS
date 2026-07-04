import type { AnswerResult } from "../types";

interface Props {
  result: AnswerResult | null;
  blockedReason: string | null;
  error: string | null;
}

function groundedLabel(grounded: boolean | null): string {
  if (grounded === true) return "evet";
  if (grounded === false) return "hayır";
  return "yok";
}

export function AnswerCard({ result, blockedReason, error }: Props) {
  if (error) {
    return (
      <div className="rounded-lg border border-danger/50 bg-danger/10 px-4 py-3 font-mono text-sm text-danger">
        hata: {error}
      </div>
    );
  }
  if (blockedReason) {
    return (
      <div className="rounded-lg border border-danger/50 bg-danger/10 px-4 py-3">
        <span className="font-display text-sm font-semibold text-danger">
          sorgu güvenlik tarafından engellendi
        </span>
        <p className="mt-1 font-mono text-xs text-danger/80">{blockedReason}</p>
      </div>
    );
  }
  if (!result) return null;

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2 font-mono text-[11px]">
        <span className="rounded bg-raised px-2 py-0.5 text-dim">rota: {result.route}</span>
        <span
          className={`rounded px-2 py-0.5 ${
            result.grounded === false ? "bg-danger/20 text-danger" : "bg-signal/15 text-signal"
          }`}
        >
          dayanaklı: {groundedLabel(result.grounded)}
        </span>
        <span className="rounded bg-raised px-2 py-0.5 text-cost">
          güven: {result.confidence.toFixed(2)}
        </span>
        <span className="rounded bg-raised px-2 py-0.5 text-dim">
          self_check ×{result.self_check_iterations}
        </span>
      </div>
      <p className="whitespace-pre-wrap text-sm leading-relaxed text-body">{result.answer}</p>
      {result.citations.length > 0 && (
        <div className="flex flex-col gap-1">
          <span className="text-[11px] uppercase tracking-wider text-dim">kaynaklar</span>
          {result.citations.map((c) => (
            <div
              key={`${c.n}-${c.chunk_index}`}
              className="flex items-center gap-2 font-mono text-[11px] text-dim"
            >
              <span className="text-signal">[{c.n}]</span>
              <span className="text-body/80">{c.source}</span>
              <span>parça {c.chunk_index}</span>
              <span className="text-cost">skor {c.score.toFixed(3)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
