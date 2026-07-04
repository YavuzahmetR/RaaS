/** Backend access. Everything goes through relative /api/* — the vite dev
 *  proxy and the nginx container both rewrite it to the FastAPI service. */

import type { EvalSummary, GuardrailLogEvent, TraceEvent } from "./types";

const API = "/api";

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API}${path}`);
  if (!res.ok) {
    throw new Error(`${path} failed: HTTP ${res.status}`);
  }
  return (await res.json()) as T;
}

export function fetchTenants(): Promise<{ tenants: string[] }> {
  return getJson("/tenants");
}

export function fetchGuardrailLog(): Promise<{
  events: GuardrailLogEvent[];
  blocked_total: number;
}> {
  return getJson("/guardrails/log?limit=25");
}

export function fetchEvalSummary(): Promise<EvalSummary> {
  return getJson("/eval/summary");
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  tenant: string;
}

/** Demo login: exchange (tenant, password) for a tenant-scoped Bearer JWT. */
export async function fetchToken(tenant: string, password: string): Promise<TokenResponse> {
  const res = await fetch(`${API}/auth/token`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ tenant, password }),
  });
  if (!res.ok) {
    const detail = await res.json().then((d) => d.detail).catch(() => null);
    throw new Error(typeof detail === "string" ? detail : `HTTP ${res.status}`);
  }
  return (await res.json()) as TokenResponse;
}

/**
 * POST /query/stream and deliver each SSE event as it arrives.
 * EventSource only supports GET, so this parses the fetch body stream by hand
 * (visible in the network tab — the acceptance criterion for "no fake timer").
 */
export async function streamQuery(
  tenant: string,
  query: string,
  onEvent: (event: TraceEvent) => void,
  signal?: AbortSignal,
  token?: string,
): Promise<void> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  // Only sent when the user supplies a token (i.e. AUTH_ENABLED on the backend);
  // left off entirely for the default token-free demo.
  if (token && token.trim()) {
    headers.Authorization = `Bearer ${token.trim()}`;
  }
  const res = await fetch(`${API}/query/stream`, {
    method: "POST",
    headers,
    body: JSON.stringify({ tenant, query }),
    signal,
  });
  if (!res.ok || !res.body) {
    throw new Error(`stream failed: HTTP ${res.status}`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    // SSE frames are separated by a blank line; keep the trailing partial.
    const frames = buffer.split("\n\n");
    buffer = frames.pop() ?? "";
    for (const frame of frames) {
      const data = frame
        .split("\n")
        .filter((line) => line.startsWith("data: "))
        .map((line) => line.slice(6))
        .join("");
      if (!data) continue;
      try {
        onEvent(JSON.parse(data) as TraceEvent);
      } catch {
        // A malformed frame should not kill the stream consumer.
      }
    }
  }
}
