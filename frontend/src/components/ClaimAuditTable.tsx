// Claim audit: per-claim verdict against the cited evidence (§1.2.2, §11).

import type { ClaimAudit, Verdict } from "../lib/types";

type Props = {
  claims: ClaimAudit[];
  onCite: (sourceId: string) => void;
};

const VERDICT_META: Record<Verdict, { label: string; cls: string }> = {
  SUPPORTED: { label: "Supported", cls: "verdict-supported" },
  PARTIAL: { label: "Partial", cls: "verdict-partial" },
  UNSUPPORTED: { label: "Unsupported", cls: "verdict-unsupported" },
};

export function ClaimAuditTable({ claims, onCite }: Props) {
  if (claims.length === 0) {
    return <p className="panel-empty">The claim audit appears after the answer is verified.</p>;
  }

  const counts = claims.reduce(
    (acc, c) => {
      acc[c.verdict] += 1;
      return acc;
    },
    { SUPPORTED: 0, PARTIAL: 0, UNSUPPORTED: 0 } as Record<Verdict, number>
  );

  return (
    <div className="claim-audit">
      <div className="claim-summary">
        {(Object.keys(VERDICT_META) as Verdict[]).map((v) => (
          <span key={v} className={`claim-chip ${VERDICT_META[v].cls}`}>
            {counts[v]} {VERDICT_META[v].label.toLowerCase()}
          </span>
        ))}
      </div>
      <ul className="claim-list">
        {claims.map((claim) => {
          const meta = VERDICT_META[claim.verdict];
          return (
            <li key={claim.id} className={`claim-row ${meta.cls}`}>
              <div className="claim-row-head">
                <span className="claim-verdict-tag">{meta.label}</span>
                <div className="claim-evidence-ids">
                  {claim.evidence_ids.map((id) => (
                    <button
                      key={id}
                      type="button"
                      className="cite-chip cite-chip-sm"
                      onClick={() => onCite(id)}
                    >
                      {id}
                    </button>
                  ))}
                </div>
              </div>
              <p className="claim-text">{claim.text.replace(/\[S\d+\]/g, "").trim()}</p>
              {claim.note && <p className="claim-note">{claim.note}</p>}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
