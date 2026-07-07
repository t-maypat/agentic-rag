// Deep-mode HITL approval interrupt (§1.1, §6). The stream pauses; the user
// approves or declines live web research before the run resumes.

import type { InterruptEvent } from "../lib/types";

type Props = {
  interrupt: InterruptEvent;
  onApprove: () => void;
  onDecline: () => void;
};

export function ApproveModal({ interrupt, onApprove, onDecline }: Props) {
  return (
    <div className="modal-overlay" role="dialog" aria-modal="true" aria-label="Approve web research">
      <div className="modal-card">
        <span className="modal-eyebrow">Deep research · approval needed</span>
        <h3 className="modal-title">Search the live web?</h3>
        <p className="modal-body">
          {interrupt.message ||
            "This will search the live web and use more budget. Proceed?"}
        </p>
        <div className="modal-actions">
          <button className="btn-secondary" onClick={onDecline}>
            Corpus only
          </button>
          <button className="btn-primary" onClick={onApprove}>
            Approve web search
          </button>
        </div>
      </div>
    </div>
  );
}
