// Live agent timeline: one row per node execution, iterations grouped as loops (§11).

import type { StageEvent } from "../lib/types";

type Props = {
  stages: StageEvent[];
  active: boolean;
};

const NODE_LABELS: Record<string, string> = {
  intake: "Intake",
  plan: "Plan",
  retrieve: "Retrieve",
  grade: "Grade",
  rewrite: "Rewrite",
  synthesize: "Synthesize",
  verify: "Verify",
  finalize: "Finalize",
};

type Row = {
  node: string;
  iteration: number;
  summary: string;
  elapsed_ms: number | null;
  done: boolean;
};

// Fold start/end pairs into a single row per (node, iteration). A `start` opens a
// row; the matching `end` fills in its summary/elapsed. Repeated nodes across
// rewrite loops carry distinct iterations, so they render as separate rows.
function foldRows(stages: StageEvent[]): Row[] {
  const rows: Row[] = [];
  const openRow = new Map<string, number>();
  for (const s of stages) {
    const key = `${s.node}#${s.iteration}`;
    if (s.status === "start") {
      openRow.set(key, rows.length);
      rows.push({
        node: s.node,
        iteration: s.iteration,
        summary: "",
        elapsed_ms: null,
        done: false,
      });
      continue;
    }
    const at = openRow.get(key);
    if (at !== undefined && rows[at] && !rows[at].done) {
      rows[at].summary = s.summary;
      rows[at].elapsed_ms = s.elapsed_ms;
      rows[at].done = true;
      openRow.delete(key);
    } else {
      // `end` without a tracked `start` (e.g. after recovery) — show standalone.
      rows.push({
        node: s.node,
        iteration: s.iteration,
        summary: s.summary,
        elapsed_ms: s.elapsed_ms,
        done: true,
      });
    }
  }
  return rows;
}

export function AgentTimeline({ stages, active }: Props) {
  const rows = foldRows(stages);

  if (rows.length === 0) {
    return <p className="panel-empty">The agent timeline appears as the run executes.</p>;
  }

  return (
    <ol className="timeline">
      {rows.map((row, i) => {
        const running = active && !row.done && i === rows.length - 1;
        return (
          <li key={`${row.node}-${row.iteration}-${i}`} className="timeline-row">
            <span
              className={`timeline-dot ${row.done ? "dot-done" : running ? "dot-active" : "dot-pending"}`}
            />
            <div className="timeline-body">
              <div className="timeline-head">
                <span className="timeline-node">{NODE_LABELS[row.node] ?? row.node}</span>
                {row.iteration > 0 && <span className="timeline-loop">loop {row.iteration}</span>}
                {row.elapsed_ms !== null && (
                  <span className="timeline-ms">{row.elapsed_ms} ms</span>
                )}
              </div>
              {row.summary && <p className="timeline-summary">{row.summary}</p>}
              {running && <p className="timeline-summary timeline-running">working…</p>}
            </div>
          </li>
        );
      })}
    </ol>
  );
}
