import type { NodeState, PipelineNodeName } from "../types";
import { PIPELINE_ORDER } from "../types";

const LABELS: Record<PipelineNodeName, string> = {
  router: "router",
  retrieve: "retrieve",
  rerank: "rerank",
  generate: "generate",
  self_check: "self_check",
  cite: "cite",
};

function nodeClasses(status: NodeState["status"]): string {
  switch (status) {
    case "running":
      return "border-signal bg-raised node-running";
    case "ok":
      return "border-signal bg-signal/15";
    case "fail":
      return "border-danger bg-danger/15";
    case "skipped":
      return "border-line border-dashed opacity-40";
    default:
      return "border-line bg-surface";
  }
}

function dotClasses(status: NodeState["status"]): string {
  switch (status) {
    case "running":
      return "bg-signal/60";
    case "ok":
      return "bg-signal";
    case "fail":
      return "bg-danger";
    default:
      return "bg-line";
  }
}

interface Props {
  nodes: Record<PipelineNodeName, NodeState>;
}

/** The signature element: six pipeline stages lighting up on real SSE events,
 *  each stamped with its measured backend latency. No timers, no fakery. */
export function PipelineTrace({ nodes }: Props) {
  return (
    <div className="overflow-x-auto pb-1" role="list" aria-label="Ajan pipeline izi">
      <div className="flex min-w-max items-start gap-0">
        {PIPELINE_ORDER.map((name, i) => {
          const node = nodes[name];
          return (
            <div key={name} className="flex items-start" role="listitem">
              {i > 0 && (
                <div
                  aria-hidden
                  className={`mt-[22px] h-px w-6 sm:w-10 ${
                    node.status === "ok" || node.status === "running"
                      ? "bg-signal/50"
                      : "bg-line"
                  }`}
                />
              )}
              <div className="flex w-[76px] flex-col items-center gap-1.5 sm:w-[92px]">
                <span className="h-4 font-mono text-[11px] text-cost">
                  {node.latencyMs !== null ? `${node.latencyMs}ms` : " "}
                </span>
                <div
                  className={`relative flex h-7 w-7 items-center justify-center rounded-full border-2 transition-colors ${nodeClasses(node.status)}`}
                >
                  <span className={`h-2.5 w-2.5 rounded-full ${dotClasses(node.status)}`} />
                  {node.passes > 1 && (
                    <span className="absolute -right-2 -top-2 rounded-full bg-cost px-1 font-mono text-[10px] font-semibold text-bg">
                      ×{node.passes}
                    </span>
                  )}
                </div>
                <span
                  className={`font-mono text-[11px] ${
                    node.status === "skipped" ? "text-dim/50 line-through" : "text-dim"
                  }`}
                >
                  {LABELS[name]}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
