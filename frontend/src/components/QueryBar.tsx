// Composer: question input + Quick/Deep toggle + hCaptcha slot (§11).

import type { RefObject } from "react";
import type { Mode } from "../lib/types";

type Props = {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  mode: Mode;
  onModeChange: (mode: Mode) => void;
  disabled: boolean;
  captchaEnabled: boolean;
  captchaRef: RefObject<HTMLDivElement>;
  captchaSatisfied: boolean;
  hint?: string | null;
};

const MODES: { value: Mode; label: string; blurb: string }[] = [
  { value: "quick", label: "Quick", blurb: "Corpus only · ~15s" },
  { value: "deep", label: "Deep", blurb: "Web + planning · ~90s" },
];

export function QueryBar({
  value,
  onChange,
  onSubmit,
  mode,
  onModeChange,
  disabled,
  captchaEnabled,
  captchaRef,
  captchaSatisfied,
  hint,
}: Props) {
  const canSend = value.trim().length > 0 && !disabled && (!captchaEnabled || captchaSatisfied);

  return (
    <div className="query-bar">
      <div className="mode-toggle" role="tablist" aria-label="Research depth">
        {MODES.map((m) => (
          <button
            key={m.value}
            role="tab"
            aria-selected={mode === m.value}
            className={`mode-pill ${mode === m.value ? "mode-pill-active" : ""}`}
            onClick={() => onModeChange(m.value)}
            disabled={disabled}
            title={m.blurb}
          >
            <span className="mode-pill-label">{m.label}</span>
            <span className="mode-pill-blurb">{m.blurb}</span>
          </button>
        ))}
      </div>

      <div className="composer">
        <textarea
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder="Ask a research question about retrieval, RAG, embeddings, or agentic search…"
          rows={2}
          maxLength={500}
          disabled={disabled}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              if (canSend) onSubmit();
            }
          }}
        />
        <div className="composer-footer">
          <span className="composer-hint">
            {hint ?? "Enter to send · Shift+Enter for a new line"}
          </span>
          <button className="send-btn" onClick={onSubmit} disabled={!canSend}>
            {disabled ? "Researching…" : "Send"}
          </button>
        </div>
      </div>

      {captchaEnabled && (
        <div className="captcha-row">
          <span className="captcha-note">Public demo · verify to send</span>
          <div ref={captchaRef} />
        </div>
      )}
    </div>
  );
}
