import type { GuardrailLogEvent } from "../types";

interface Props {
  events: GuardrailLogEvent[];
  blockedTotal: number;
}

function timeOf(ts: number): string {
  return new Date(ts * 1000).toLocaleTimeString("tr-TR", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

export function GuardrailLog({ events, blockedTotal }: Props) {
  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-baseline justify-between">
        <h2 className="font-display text-sm font-semibold text-body">güvenlik kaydı</h2>
        <span className="font-mono text-[11px] text-dim">
          engellenen: <span className="text-danger">{blockedTotal}</span>
        </span>
      </div>
      {events.length === 0 ? (
        <p className="font-mono text-xs text-dim/60">
          henüz kontrol yok — bir sorgu gönder (ya da prompt injection dene)
        </p>
      ) : (
        <ul className="flex max-h-52 flex-col gap-1 overflow-y-auto">
          {events.map((e, i) => (
            <li
              key={`${e.ts}-${i}`}
              className="flex items-center gap-2 rounded border border-line bg-surface px-2 py-1 font-mono text-[11px]"
            >
              <span
                aria-label={e.blocked ? "engellendi" : "geçti"}
                className={`h-2 w-2 shrink-0 rounded-full ${e.blocked ? "bg-danger" : "bg-signal"}`}
              />
              <span className="shrink-0 text-dim">{timeOf(e.ts)}</span>
              <span className="shrink-0 text-dim/70">{e.tenant}</span>
              {e.blocked ? (
                <span className="shrink-0 font-semibold text-danger">
                  ENGELLENDİ · {e.layer}:{e.reason}
                </span>
              ) : (
                <span className="shrink-0 text-signal/80">geçti</span>
              )}
              <span className="truncate text-dim/60" title={e.query_preview}>
                {e.query_preview}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
