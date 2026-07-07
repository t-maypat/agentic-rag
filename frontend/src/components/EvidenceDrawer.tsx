// Evidence panel: cited sources (S1..Sn) plus per-sub-question retrieved chunks,
// each with dense/bm25/fused scores and origin/trust badges (§11).

import { useEffect, useRef } from "react";
import type { EvidenceChunk, SubQuestion } from "../lib/types";

type Props = {
  subQuestions: SubQuestion[];
  evidence: Record<string, EvidenceChunk[]>;
  sources: EvidenceChunk[];
  focusedSourceId: string | null;
};

function fmt(n: number | null | undefined): string {
  return typeof n === "number" ? n.toFixed(3) : "—";
}

function ChunkCard({
  chunk,
  label,
  highlight,
  cardRef,
}: {
  chunk: EvidenceChunk;
  label?: string;
  highlight?: boolean;
  cardRef?: React.Ref<HTMLDivElement>;
}) {
  return (
    <div ref={cardRef} className={`chunk-card ${highlight ? "chunk-focus" : ""}`}>
      <div className="chunk-head">
        <div className="chunk-title-row">
          {label && <span className="source-tag">{label}</span>}
          <span className="chunk-title">{chunk.doc_title}</span>
        </div>
        <div className="chunk-badges">
          <span className={`badge badge-${chunk.origin}`}>{chunk.origin}</span>
          {chunk.trust === "low" && <span className="badge badge-low">low trust</span>}
        </div>
      </div>
      {chunk.section && <p className="chunk-section">{chunk.section}</p>}
      <p className="chunk-text">{chunk.text}</p>
      <div className="chunk-scores">
        <span>dense {fmt(chunk.scores.dense)}</span>
        <span>bm25 {fmt(chunk.scores.bm25)}</span>
        <span className="score-fused">fused {fmt(chunk.scores.fused)}</span>
      </div>
      {chunk.url && (
        <a className="chunk-link" href={chunk.url} target="_blank" rel="noreferrer">
          open source ↗
        </a>
      )}
    </div>
  );
}

export function EvidenceDrawer({ subQuestions, evidence, sources, focusedSourceId }: Props) {
  const focusRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (focusedSourceId && focusRef.current) {
      focusRef.current.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  }, [focusedSourceId]);

  const hasEvidence = Object.keys(evidence).length > 0;
  const subById = new Map(subQuestions.map((s) => [s.id, s]));
  const groupIds = Object.keys(evidence);

  if (sources.length === 0 && !hasEvidence) {
    return <p className="panel-empty">Evidence appears here as the agent retrieves it.</p>;
  }

  return (
    <div className="evidence-drawer">
      {sources.length > 0 && (
        <section className="evidence-section">
          <h4 className="evidence-subhead">Cited sources</h4>
          {sources.map((chunk) => (
            <ChunkCard
              key={chunk.source_id ?? chunk.id}
              chunk={chunk}
              label={chunk.source_id}
              highlight={chunk.source_id === focusedSourceId}
              cardRef={chunk.source_id === focusedSourceId ? focusRef : undefined}
            />
          ))}
        </section>
      )}

      {groupIds.map((sqId) => (
        <section key={sqId} className="evidence-section">
          <h4 className="evidence-subhead">
            {subById.get(sqId)?.text ?? sqId}
            <span className="evidence-count">{evidence[sqId].length}</span>
          </h4>
          {evidence[sqId].map((chunk) => (
            <ChunkCard key={chunk.id} chunk={chunk} />
          ))}
        </section>
      ))}
    </div>
  );
}
