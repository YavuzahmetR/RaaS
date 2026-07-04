import { type FormEvent, useState } from "react";

interface Props {
  tenants: string[];
  tenant: string;
  onTenantChange: (tenant: string) => void;
  streaming: boolean;
  recentQueries: string[];
  onSubmit: (query: string) => void;
}

export function QueryPanel({
  tenants,
  tenant,
  onTenantChange,
  streaming,
  recentQueries,
  onSubmit,
}: Props) {
  const [query, setQuery] = useState("");

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const trimmed = query.trim();
    if (!trimmed || streaming || !tenant.trim()) return;
    onSubmit(trimmed);
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-3">
      <label className="flex flex-col gap-1 text-xs text-dim">
        firma (tenant)
        {tenants.length > 0 ? (
          <select
            value={tenant}
            onChange={(e) => onTenantChange(e.target.value)}
            className="rounded-md border border-line bg-raised px-2 py-1.5 font-mono text-sm text-body"
          >
            {tenants.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        ) : (
          <input
            value={tenant}
            onChange={(e) => onTenantChange(e.target.value)}
            placeholder="demo"
            className="rounded-md border border-line bg-raised px-2 py-1.5 font-mono text-sm text-body placeholder:text-dim/50"
          />
        )}
      </label>

      <label className="flex flex-col gap-1 text-xs text-dim">
        sorgu
        <textarea
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              handleSubmit(e);
            }
          }}
          rows={3}
          placeholder="How many days of annual leave do I get?"
          className="resize-none rounded-md border border-line bg-raised px-3 py-2 text-sm text-body placeholder:text-dim/50"
        />
      </label>

      <button
        type="submit"
        disabled={streaming || !query.trim() || !tenant.trim()}
        className="rounded-md bg-signal px-4 py-2 font-display text-sm font-semibold text-bg transition-opacity disabled:cursor-not-allowed disabled:opacity-40"
      >
        {streaming ? "izleniyor…" : "sorgu gönder"}
      </button>

      {recentQueries.length > 0 && (
        <div className="flex flex-col gap-1.5">
          <span className="text-xs text-dim">son sorgular — {tenant}</span>
          {recentQueries.map((q, i) => (
            <button
              key={`${i}-${q}`}
              type="button"
              onClick={() => setQuery(q)}
              className="truncate rounded border border-line bg-surface px-2 py-1 text-left font-mono text-[11px] text-dim transition-colors hover:border-signal/40 hover:text-body"
              title={q}
            >
              {q}
            </button>
          ))}
        </div>
      )}
    </form>
  );
}
