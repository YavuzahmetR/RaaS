import { useCallback, useRef, useState } from "react";

import { streamQuery } from "./api";
import type {
  AnswerResult,
  NodeState,
  PipelineNodeName,
  QuerySummary,
  TraceEvent,
} from "./types";
import { PIPELINE_ORDER } from "./types";

const IDLE_NODE: NodeState = { status: "idle", latencyMs: null, passes: 0, detail: {} };

function freshNodes(): Record<PipelineNodeName, NodeState> {
  return Object.fromEntries(PIPELINE_ORDER.map((n) => [n, { ...IDLE_NODE }])) as Record<
    PipelineNodeName,
    NodeState
  >;
}

function isPipelineNode(name: string): name is PipelineNodeName {
  return (PIPELINE_ORDER as readonly string[]).includes(name);
}

/** Immutable node-map update helper. */
function withNode(
  nodes: Record<PipelineNodeName, NodeState>,
  name: PipelineNodeName,
  next: Partial<NodeState>,
): Record<PipelineNodeName, NodeState> {
  return { ...nodes, [name]: { ...nodes[name], ...next } };
}

/** Which pipeline node is running next, inferred from real routing rules
 *  (mirrors app/agent/graph.py edges — display state, never fake latency). */
function nextRunning(
  event: Extract<TraceEvent, { type: "node" }>,
): PipelineNodeName | null {
  const d = event.detail as Record<string, unknown>;
  switch (event.node) {
    case "router":
      return d.route === "docs" ? "retrieve" : d.route === "direct" ? "generate" : null;
    case "retrieve":
      return null; // rerank event follows in the same frame batch
    case "rerank":
      return "generate";
    case "generate":
      return null; // self_check or cite — decided by the next event
    case "self_check": {
      const grounded = d.grounded !== false;
      const iteration = typeof d.iteration === "number" ? d.iteration : 99;
      return !grounded && iteration < 2 ? "retrieve" : "cite";
    }
    default:
      return null;
  }
}

export interface TraceStreamState {
  nodes: Record<PipelineNodeName, NodeState>;
  streaming: boolean;
  guardrail: "idle" | "checking" | "passed" | "blocked";
  blockedReason: string | null;
  answer: AnswerResult | null;
  summary: QuerySummary | null;
  error: string | null;
}

const INITIAL: TraceStreamState = {
  nodes: freshNodes(),
  streaming: false,
  guardrail: "idle",
  blockedReason: null,
  answer: null,
  summary: null,
  error: null,
};

export function useTraceStream(onFinished: () => void) {
  const [state, setState] = useState<TraceStreamState>(INITIAL);
  const abortRef = useRef<AbortController | null>(null);

  const apply = useCallback((event: TraceEvent) => {
    setState((s) => {
      switch (event.type) {
        case "accepted":
          return { ...s, guardrail: "checking" };
        case "guardrail":
          if (event.blocked) {
            return {
              ...s,
              guardrail: "blocked",
              blockedReason: `${event.layer}: ${event.reason}`,
            };
          }
          return {
            ...s,
            guardrail: "passed",
            nodes: withNode(s.nodes, "router", { status: "running" }),
          };
        case "node": {
          if (!isPipelineNode(event.node)) {
            // tool path (list_docs): the doc-QA pipeline genuinely didn't run
            return s;
          }
          const prev = s.nodes[event.node];
          let nodes = withNode(s.nodes, event.node, {
            status: event.status === "skipped" ? "skipped" : "ok",
            latencyMs: event.status === "skipped" ? null : event.latency_ms,
            passes: prev.passes + (event.status === "skipped" ? 0 : 1),
            detail: event.detail,
          });
          const running = nextRunning(event);
          if (running && nodes[running].status !== "ok") {
            nodes = withNode(nodes, running, { status: "running" });
          } else if (running === "retrieve") {
            // self-check loop re-entry: relight even though it already ran
            nodes = withNode(nodes, "retrieve", { status: "running" });
          }
          return { ...s, nodes };
        }
        case "answer": {
          // Anything that never fired truly didn't run — mark it skipped.
          let nodes = s.nodes;
          for (const name of PIPELINE_ORDER) {
            if (nodes[name].status === "idle" || nodes[name].status === "running") {
              nodes = withNode(nodes, name, { status: "skipped" });
            }
          }
          return { ...s, nodes, answer: event };
        }
        case "summary":
          return {
            ...s,
            summary: {
              totalLatencyMs: event.total_latency_ms,
              costUsd: event.cost_usd,
              llmCalls: event.llm_calls,
              tokens: event.tokens,
            },
          };
        case "error":
          return { ...s, error: event.message };
        case "done":
          return s;
        default:
          return s;
      }
    });
  }, []);

  const run = useCallback(
    async (tenant: string, query: string, token?: string) => {
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;
      setState({ ...INITIAL, nodes: freshNodes(), streaming: true, guardrail: "checking" });
      try {
        await streamQuery(tenant, query, apply, controller.signal, token);
      } catch (e) {
        if (!controller.signal.aborted) {
          setState((s) => ({ ...s, error: e instanceof Error ? e.message : String(e) }));
        }
      } finally {
        setState((s) => ({ ...s, streaming: false }));
        onFinished();
      }
    },
    [apply, onFinished],
  );

  return { state, run };
}
