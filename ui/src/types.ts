/** Wire types mirroring app/api/stream.py's SSE protocol — kept in one place. */

export type PipelineNodeName =
  | "router"
  | "retrieve"
  | "rerank"
  | "generate"
  | "self_check"
  | "cite";

export const PIPELINE_ORDER: readonly PipelineNodeName[] = [
  "router",
  "retrieve",
  "rerank",
  "generate",
  "self_check",
  "cite",
] as const;

export type TraceEvent =
  | { type: "accepted"; tenant: string; query: string }
  | {
      type: "guardrail";
      guardrail: string;
      blocked: boolean;
      layer: string;
      reason: string;
      latency_ms: number;
    }
  | {
      type: "node";
      node: string;
      status: "ok" | "skipped" | "fail";
      latency_ms: number;
      detail: Record<string, unknown>;
    }
  | {
      type: "answer";
      answer: string;
      citations: Citation[];
      confidence: number;
      route: string | null;
      grounded: boolean | null;
      self_check_iterations: number;
      steps: string[];
    }
  | {
      type: "summary";
      total_latency_ms: number;
      cost_usd: number;
      llm_calls: number;
      tokens: { prompt: number; completion: number };
    }
  | { type: "done"; outcome: "ok" | "blocked" }
  | { type: "error"; stage?: string; message: string };

export interface Citation {
  n: number;
  doc_id: string;
  source: string;
  chunk_index: number;
  score: number;
}

export type NodeStatus = "idle" | "running" | "ok" | "skipped" | "fail";

export interface NodeState {
  status: NodeStatus;
  latencyMs: number | null;
  passes: number; // >1 when the self-check loop re-entered the node
  detail: Record<string, unknown>;
}

export interface GuardrailLogEvent {
  ts: number;
  tenant: string;
  guardrail: string;
  blocked: boolean;
  layer: string;
  reason: string;
  query_preview: string;
}

export interface EvalMetricsFile {
  file: string;
  metrics: Record<string, number | boolean>;
}

export interface EvalSummary {
  retrieval: EvalMetricsFile | null;
  retrieval_baseline: EvalMetricsFile | null;
  generation: EvalMetricsFile | null;
}

export interface AnswerResult {
  answer: string;
  citations: Citation[];
  confidence: number;
  route: string | null;
  grounded: boolean | null;
  self_check_iterations: number;
  steps: string[];
}

export interface QuerySummary {
  totalLatencyMs: number;
  costUsd: number;
  llmCalls: number;
  tokens: { prompt: number; completion: number };
}
