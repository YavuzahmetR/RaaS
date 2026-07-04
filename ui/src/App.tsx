import { useCallback, useEffect, useState } from "react";

import { fetchEvalSummary, fetchGuardrailLog, fetchTenants, fetchToken } from "./api";
import { AnswerCard } from "./components/AnswerCard";
import { CostSummary } from "./components/CostSummary";
import { EvalCards } from "./components/EvalCards";
import { GuardrailLog } from "./components/GuardrailLog";
import { PipelineTrace } from "./components/PipelineTrace";
import { QueryPanel } from "./components/QueryPanel";
import type { EvalSummary, GuardrailLogEvent } from "./types";
import { useTraceStream } from "./useTraceStream";

const GUARDRAIL_POLL_MS = 5000;
const RECENT_LIMIT = 5;

export default function App() {
  const [tenants, setTenants] = useState<string[]>([]);
  const [tenant, setTenant] = useState("demo");
  const [token, setToken] = useState("");
  const [password, setPassword] = useState("");
  const [sessionTenant, setSessionTenant] = useState<string | null>(null);
  const [loginError, setLoginError] = useState<string | null>(null);
  const [loggingIn, setLoggingIn] = useState(false);
  const [recent, setRecent] = useState<Record<string, string[]>>({});
  const [guardrailEvents, setGuardrailEvents] = useState<GuardrailLogEvent[]>([]);
  const [blockedTotal, setBlockedTotal] = useState(0);
  const [evalSummary, setEvalSummary] = useState<EvalSummary | null>(null);

  const refreshGuardrails = useCallback(() => {
    fetchGuardrailLog()
      .then((r) => {
        setGuardrailEvents(r.events);
        setBlockedTotal(r.blocked_total);
      })
      .catch(() => undefined); // panel simply stays stale if the API is down
  }, []);

  const { state, run } = useTraceStream(refreshGuardrails);

  useEffect(() => {
    fetchTenants()
      .then((r) => {
        setTenants(r.tenants);
        if (r.tenants.length > 0) setTenant((t) => (r.tenants.includes(t) ? t : r.tenants[0]));
      })
      .catch(() => undefined);
    fetchEvalSummary()
      .then(setEvalSummary)
      .catch(() => undefined);
    refreshGuardrails();
    const id = setInterval(refreshGuardrails, GUARDRAIL_POLL_MS);
    return () => clearInterval(id);
  }, [refreshGuardrails]);

  async function handleLogin() {
    setLoggingIn(true);
    setLoginError(null);
    try {
      const res = await fetchToken(tenant, password);
      setToken(res.access_token);
      setSessionTenant(res.tenant);
    } catch (e) {
      setToken("");
      setSessionTenant(null);
      setLoginError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoggingIn(false);
    }
  }

  function handleTenantChange(next: string) {
    setTenant(next);
    // A token is tenant-scoped: switching tenants invalidates the session.
    if (sessionTenant && next !== sessionTenant) {
      setToken("");
      setSessionTenant(null);
    }
  }

  function handleSubmit(query: string) {
    setRecent((r) => ({
      ...r,
      [tenant]: [query, ...(r[tenant] ?? []).filter((q) => q !== query)].slice(0, RECENT_LIMIT),
    }));
    void run(tenant, query, token);
  }

  const gen = evalSummary?.generation?.metrics;
  const ret = evalSummary?.retrieval?.metrics;

  return (
    <div className="mx-auto flex min-h-screen max-w-6xl flex-col gap-4 px-4 py-5">
      {/* header */}
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-line pb-4">
        <div className="flex items-baseline gap-3">
          <h1 className="font-display text-2xl font-bold tracking-tight text-body">
            Ra<span className="text-signal">a</span>S
          </h1>
          <span className="hidden text-xs text-dim sm:inline">
            agentic RAG · kanıt konsolu — her ışık gerçek bir backend olayı
          </span>
        </div>
        <div className="flex items-center gap-4 font-mono text-[11px] text-dim">
          {typeof gen?.faithfulness === "number" && (
            <span>
              sadakat <span className="text-signal">{gen.faithfulness.toFixed(2)}</span>
            </span>
          )}
          {typeof ret?.["recall@1"] === "number" && (
            <span>
              recall@1 <span className="text-signal">{ret["recall@1"].toFixed(2)}</span>
            </span>
          )}
        </div>
      </header>

      {/* main grid */}
      <main className="grid flex-1 grid-cols-1 gap-4 lg:grid-cols-[280px_1fr]">
        {/* left: query panel */}
        <section
          aria-label="Sorgu paneli"
          className="h-fit rounded-xl border border-line bg-surface p-4"
        >
          <QueryPanel
            tenants={tenants}
            tenant={tenant}
            onTenantChange={handleTenantChange}
            streaming={state.streaming}
            recentQueries={recent[tenant] ?? []}
            onSubmit={handleSubmit}
          />
          <div className="mt-3 flex flex-col gap-2 border-t border-line pt-3">
            <span className="text-xs text-dim">oturum (JWT)</span>
            {sessionTenant ? (
              <div className="flex items-center justify-between gap-2">
                <span className="font-mono text-[11px] text-signal">
                  ✓ giriş yapıldı: {sessionTenant}
                </span>
                <button
                  type="button"
                  onClick={() => {
                    setToken("");
                    setSessionTenant(null);
                  }}
                  className="rounded border border-line px-2 py-0.5 font-mono text-[10px] text-dim hover:text-body"
                >
                  çıkış
                </button>
              </div>
            ) : (
              <>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") void handleLogin();
                  }}
                  placeholder="demo şifresi (.env AUTH_DEMO_PASSWORD)"
                  className="rounded-md border border-line bg-raised px-2 py-1.5 font-mono text-[11px] text-body placeholder:text-dim/50"
                />
                <button
                  type="button"
                  onClick={() => void handleLogin()}
                  disabled={loggingIn || !password.trim()}
                  className="rounded-md border border-signal/40 px-3 py-1.5 font-display text-xs font-semibold text-signal transition-opacity disabled:opacity-40"
                >
                  {loggingIn ? "giriş yapılıyor…" : "token al"}
                </button>
                {loginError && (
                  <span className="font-mono text-[10px] text-danger">{loginError}</span>
                )}
              </>
            )}
          </div>
        </section>

        {/* right: trace + result + guardrails */}
        <div className="flex flex-col gap-4">
          <section
            aria-label="Pipeline izi"
            className="rounded-xl border border-line bg-surface p-4"
          >
            <div className="mb-3 flex items-center justify-between">
              <h2 className="font-display text-sm font-semibold text-body">pipeline izi</h2>
              <span
                className={`font-mono text-[11px] ${
                  state.guardrail === "blocked"
                    ? "text-danger"
                    : state.guardrail === "passed"
                      ? "text-signal"
                      : "text-dim"
                }`}
              >
                {state.guardrail === "idle" && "sorgu bekleniyor"}
                {state.guardrail === "checking" && "güvenlik kontrolü…"}
                {state.guardrail === "passed" && "güvenlik ✓ geçti"}
                {state.guardrail === "blocked" && "güvenlik ✗ ENGELLENDİ"}
              </span>
            </div>
            <PipelineTrace nodes={state.nodes} />
            <div className="mt-4 border-t border-line pt-4">
              <CostSummary summary={state.summary} />
            </div>
          </section>

          {(state.answer || state.blockedReason || state.error) && (
            <section
              aria-label="Yanıt"
              className="rounded-xl border border-line bg-surface p-4"
            >
              <AnswerCard
                result={state.answer}
                blockedReason={state.blockedReason}
                error={state.error}
              />
            </section>
          )}

          <section
            aria-label="Güvenlik kaydı"
            className="rounded-xl border border-line bg-surface p-4"
          >
            <GuardrailLog events={guardrailEvents} blockedTotal={blockedTotal} />
          </section>
        </div>
      </main>

      {/* eval strip */}
      <footer className="border-t border-line pt-4">
        <div className="mb-2 flex items-baseline gap-2">
          <h2 className="font-display text-sm font-semibold text-body">hislerle değil, ölçümle</h2>
          <span className="font-mono text-[10px] text-dim/60">
            kaynak: eval/results/*.json → /eval/summary
          </span>
        </div>
        <EvalCards summary={evalSummary} blockedTotal={blockedTotal} />
      </footer>
    </div>
  );
}
