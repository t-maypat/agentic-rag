// Budget usage meter: calls / tokens / web fetches / cost vs the governor limits (§9).

import type { Mode, Usage } from "../lib/types";

type Props = {
  usage: Usage | null;
  mode: Mode;
};

// Budget limits from budget.py (REVAMP_PLAN §3.1 / resolved Q8).
const LIMITS = {
  llm_calls: 10,
  total_tokens: 80_000,
  web_fetches: 3,
};

function Bar({ label, value, limit, detail }: { label: string; value: number; limit: number; detail: string }) {
  const pct = Math.min(100, Math.round((value / limit) * 100));
  const over = value > limit;
  return (
    <div className="meter-row">
      <div className="meter-head">
        <span className="meter-label">{label}</span>
        <span className="meter-value">{detail}</span>
      </div>
      <div className="meter-track">
        <div className={`meter-fill ${over ? "meter-over" : ""}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

export function UsageMeter({ usage, mode }: Props) {
  if (!usage) {
    return <p className="panel-empty">Budget usage is reported when the run finishes.</p>;
  }
  const tokens = usage.input_tokens + usage.output_tokens;
  const walls = mode === "deep" ? 90 : 25;
  return (
    <div className="usage-meter">
      <Bar
        label="LLM calls"
        value={usage.llm_calls}
        limit={LIMITS.llm_calls}
        detail={`${usage.llm_calls} / ${LIMITS.llm_calls}`}
      />
      <Bar
        label="Tokens"
        value={tokens}
        limit={LIMITS.total_tokens}
        detail={`${tokens.toLocaleString()} / ${LIMITS.total_tokens.toLocaleString()}`}
      />
      <Bar
        label="Web fetches"
        value={usage.web_fetches}
        limit={LIMITS.web_fetches}
        detail={`${usage.web_fetches} / ${LIMITS.web_fetches}`}
      />
      <div className="usage-facts">
        <div>
          <span className="usage-fact-label">Est. cost</span>
          <span className="usage-fact-value">${usage.est_cost_usd.toFixed(4)}</span>
          <span className="usage-fact-note">at list price</span>
        </div>
        <div>
          <span className="usage-fact-label">Wall time</span>
          <span className="usage-fact-value">{(usage.wall_ms / 1000).toFixed(1)}s</span>
          <span className="usage-fact-note">budget {walls}s</span>
        </div>
      </div>
    </div>
  );
}
