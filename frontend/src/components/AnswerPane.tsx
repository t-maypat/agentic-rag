// Renders a single assistant turn: streamed markdown answer with citation chips
// and per-sentence verdict underlines, or the refusal card variant (§11).

import { useMemo } from "react";
import { normalizeClaim, renderMarkdown } from "../lib/markdown";
import type { ClaimAudit, Outcome, Verdict } from "../lib/types";

type Props = {
  answerMd: string | null;
  outcome: Outcome | null;
  claims: ClaimAudit[];
  streaming: boolean;
  cached: boolean;
  onCite: (sourceId: string) => void;
};

const REFUSAL_COPY: Record<string, { title: string; body: string }> = {
  refused: {
    title: "I can't answer this reliably",
    body: "The evidence I found doesn't hold up well enough to answer with confidence. The best sources and sub-questions are shown in the investigation panel.",
  },
  budget_exceeded: {
    title: "I ran out of budget before I could verify this",
    body: "The run hit its call/token/time budget. Any partial draft is unverified, so I'm holding back rather than presenting unchecked claims.",
  },
};

export function AnswerPane({ answerMd, outcome, claims, streaming, cached, onCite }: Props) {
  const verdicts = useMemo(() => {
    const map = new Map<string, Verdict>();
    for (const c of claims) map.set(normalizeClaim(c.text), c.verdict);
    return map;
  }, [claims]);

  const isRefusal = outcome === "refused" || outcome === "budget_exceeded";

  if (isRefusal && !answerMd) {
    const copy = REFUSAL_COPY[outcome] ?? REFUSAL_COPY.refused;
    return (
      <div className="refusal-card">
        <span className="refusal-badge">Refused</span>
        <h3>{copy.title}</h3>
        <p>{copy.body}</p>
      </div>
    );
  }

  const content = answerMd ?? "";

  return (
    <div className={`answer-card ${outcome === "redirected" ? "answer-card-redirect" : ""}`}>
      {isRefusal && <span className="refusal-badge">Refused · partial</span>}
      {cached && <span className="cached-badge">cached</span>}
      <div className="md-prose">
        {renderMarkdown(content, { verdicts, onCite })}
        {streaming && <span className="stream-caret" aria-hidden />}
      </div>
    </div>
  );
}
