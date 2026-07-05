import type { RefObject } from "react";
import { useEffect, useRef, useState } from "react";
import { queryAgent } from "./lib/api";
import type { Message, SourceChunk, TraceStep } from "./lib/types";

type LandingProps = {
  onEnter: () => void;
};

function Landing({ onEnter }: LandingProps) {
  return (
    <section className="landing-shell">
      <h1>Loupe</h1>
      <p>A deep-research agent that shows its work.</p>
      <button onClick={onEnter}>Enter workspace</button>
    </section>
  );
}

declare global {
  interface Window {
    hcaptcha?: {
      render: (
        container: string | HTMLElement,
        options: {
          sitekey: string;
          callback?: (token: string) => void;
          "expired-callback"?: () => void;
          "error-callback"?: () => void;
          theme?: "light" | "dark" | "auto";
          size?: "normal" | "compact" | "invisible";
        }
      ) => string;
      reset: (widgetId?: string) => void;
    };
  }
}

const starterQuestions = [
  "Explain why hybrid retrieval improves factual grounding in RAG systems.",
  "Compare BM25, DPR, and modern dense retrievers for research-heavy queries.",
  "What changed between early RAG pipelines and agentic retrieval systems?",
  "How should I evaluate embedding quality for an AI research assistant?",
  "When do rerankers matter more than better chunking?",
  "Which papers are most important for understanding retrieval hallucinations?"
];

const truncate = (text: string, limit: number) =>
  text.length > limit ? `${text.slice(0, limit).trim()}...` : text;

const formatAuthors = (authors?: string[] | null) => {
  if (!authors || authors.length === 0) return null;
  if (authors.length <= 2) return authors.join(", ");
  return `${authors[0]} et al.`;
};

const formatMeta = (source: SourceChunk) => {
  const parts = [
    source.section,
    formatAuthors(source.authors),
    source.year ? String(source.year) : null,
    source.source_type,
    source.source
  ].filter(Boolean);
  return parts.join(" | ");
};

type WorkspaceProps = {
  hcaptchaRef: RefObject<HTMLDivElement>;
  hcaptchaSiteKey?: string;
  loading: boolean;
  question: string;
  errorMessage: string | null;
  messages: Message[];
  sources: SourceChunk[];
  trace: TraceStep[];
  onBack: () => void;
  onQuestionChange: (value: string) => void;
  onSend: (value?: string) => void;
};

function Workspace({
  hcaptchaRef,
  hcaptchaSiteKey,
  loading,
  question,
  errorMessage,
  messages,
  sources,
  trace,
  onBack,
  onQuestionChange,
  onSend
}: WorkspaceProps) {
  return (
    <section className="workspace-shell">
      <div className="workspace-backdrop workspace-backdrop-a" />
      <div className="workspace-backdrop workspace-backdrop-b" />

      <header className="workspace-hero">
        <div className="workspace-intro">
          <button className="workspace-back" onClick={onBack}>
            Back
          </button>
          <p className="workspace-eyebrow">Research workspace</p>
          <h2 className="workspace-title">Grounded answers for retrieval-heavy thinking.</h2>
          <p className="workspace-subtitle">
            Explore papers, benchmark tradeoffs, and implementation details with source-backed
            responses and visible retrieval traces.
          </p>
        </div>
        <div className="workspace-prompt-bank">
          <p className="workspace-bank-title">Suggested prompts</p>
          <div className="workspace-prompt-grid">
            {starterQuestions.map((prompt) => (
              <button key={prompt} onClick={() => onSend(prompt)}>
                {prompt}
              </button>
            ))}
          </div>
        </div>
      </header>

      <main className="workspace-layout">
        <section className="chat-panel">
          <div className="chat-panel-head">
            <div>
              <p className="chat-panel-label">Main thread</p>
              <h3>Research dialogue</h3>
            </div>
            <p>Answers cite sources and expose the retrieval path behind them.</p>
          </div>

          <div className="chat-stream">
            {messages.length === 0 ? (
              <div className="chat-empty">
                <h3>Start with a deep question.</h3>
                <p>
                  Try benchmark comparisons, architecture tradeoffs, or source-backed summaries of
                  foundational RAG papers.
                </p>
              </div>
            ) : (
              messages.map((message, index) => (
                <article key={index} className={`message-card ${message.role}`}>
                  <div className="message-meta">
                    <span>{message.role === "user" ? "You" : "Research Assistant"}</span>
                    {message.role === "assistant" && <strong>Grounded answer</strong>}
                  </div>
                  <div className="message-body">{message.content}</div>
                </article>
              ))
            )}
          </div>

          <div className="composer">
            <textarea
              value={question}
              onChange={(event) => onQuestionChange(event.target.value)}
              placeholder="Ask about retrieval methods, RAG evaluation, embedding choices, or agentic search."
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  onSend();
                }
              }}
            />
            <div className="composer-actions">
              <p>Press Enter to send, Shift+Enter for a new line.</p>
              <button onClick={() => onSend()} disabled={loading}>
                {loading ? "Thinking..." : "Send question"}
              </button>
            </div>
          </div>

          {hcaptchaSiteKey && (
            <div className="demo-guardrail">
              <div className="guardrail-copy">
                <strong>Public demo protection</strong>
                <p>This workspace uses hCaptcha and conservative backend limits to protect the free-tier deployment.</p>
              </div>
              <div ref={hcaptchaRef} className="captcha-slot" />
            </div>
          )}
          {errorMessage && <p className="guardrail-error">{errorMessage}</p>}
        </section>

        <aside className="inspector-column">
          <section className="inspector-panel">
            <div className="inspector-head">
              <p className="workspace-eyebrow">Evidence</p>
              <h3>Sources</h3>
            </div>
            {sources.length === 0 ? (
              <p className="muted-copy">The source stack appears after the first answer.</p>
            ) : (
              sources.map((source, index) => {
                const metaLine = formatMeta(source);
                return (
                  <article key={source.chunk_id} className="source-card">
                    <div className="source-card-head">
                      <div>
                        <span className="source-citation">[{index + 1}]</span>
                        <h4>{source.title || "Untitled source"}</h4>
                      </div>
                      <span className="source-score">{source.score.toFixed(3)}</span>
                    </div>
                    {metaLine && <p className="source-meta">{metaLine}</p>}
                    <p className="source-text">{truncate(source.text, 260)}</p>
                    {source.url && (
                      <a className="source-link" href={source.url} target="_blank" rel="noreferrer">
                        Open original
                      </a>
                    )}
                  </article>
                );
              })
            )}
          </section>

          <details className="inspector-panel trace-panel">
            <summary>
              <span>Trace</span>
              <small>retrieval path</small>
            </summary>
            {trace.length === 0 ? (
              <p className="muted-copy">No trace yet.</p>
            ) : (
              trace.map((step, index) => (
                <article key={`${step.name}-${index}`} className="trace-card">
                  <div className="trace-name">{step.name}</div>
                  <pre>{step.detail}</pre>
                </article>
              ))
            )}
          </details>
        </aside>
      </main>
    </section>
  );
}

export default function App() {
  const hcaptchaSiteKey = import.meta.env.VITE_HCAPTCHA_SITE_KEY as string | undefined;
  const hcaptchaRef = useRef<HTMLDivElement | null>(null);
  const [hcaptchaToken, setHcaptchaToken] = useState<string | null>(null);
  const [hcaptchaReady, setHcaptchaReady] = useState<boolean>(!hcaptchaSiteKey);
  const [widgetId, setWidgetId] = useState<string | null>(null);
  const [enteredWorkspace, setEnteredWorkspace] = useState(false);
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [sources, setSources] = useState<SourceChunk[]>([]);
  const [trace, setTrace] = useState<TraceStep[]>([]);
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!hcaptchaSiteKey) return;
    if (window.hcaptcha) {
      setHcaptchaReady(true);
      return;
    }

    const script = document.createElement("script");
    script.src = "https://js.hcaptcha.com/1/api.js?render=explicit";
    script.async = true;
    script.defer = true;
    script.onload = () => setHcaptchaReady(true);
    document.head.appendChild(script);

    return () => {
      document.head.removeChild(script);
    };
  }, [hcaptchaSiteKey]);

  useEffect(() => {
    if (!hcaptchaSiteKey || !hcaptchaReady || !hcaptchaRef.current || !window.hcaptcha || widgetId) {
      return;
    }

    const id = window.hcaptcha.render(hcaptchaRef.current, {
      sitekey: hcaptchaSiteKey,
      theme: "light",
      callback: (token: string) => {
        setHcaptchaToken(token);
        setErrorMessage(null);
      },
      "expired-callback": () => {
        setHcaptchaToken(null);
      },
      "error-callback": () => {
        setHcaptchaToken(null);
        setErrorMessage("Verification failed. Please refresh the demo challenge and try again.");
      },
      size: "normal"
    });
    setWidgetId(id);
  }, [hcaptchaReady, hcaptchaSiteKey, widgetId]);

  const resetHcaptcha = () => {
    if (!window.hcaptcha || !widgetId) return;
    window.hcaptcha.reset(widgetId);
    setHcaptchaToken(null);
  };

  const handleEnterWorkspace = () => {
    setEnteredWorkspace(true);
    window.requestAnimationFrame(() => {
      window.scrollTo({ top: 0, behavior: "smooth" });
    });
  };

  const handleSend = async (value?: string) => {
    const text = (value ?? question).trim();
    if (!text || loading) return;
    if (hcaptchaSiteKey && !hcaptchaToken) {
      setErrorMessage("Please complete the verification challenge before sending a public demo query.");
      return;
    }

    setLoading(true);
    setErrorMessage(null);
    setMessages((prev) => [...prev, { role: "user", content: text }]);
    setQuestion("");

    try {
      const response = await queryAgent(text, 5, hcaptchaToken ?? undefined);
      setMessages((prev) => [...prev, { role: "assistant", content: response.answer }]);
      setSources(response.sources);
      setTrace(response.trace);
    } catch (error) {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: error instanceof Error ? error.message : "Sorry, something went wrong."
        }
      ]);
    } finally {
      resetHcaptcha();
      setLoading(false);
    }
  };

  return (
    <div className="app-shell">
      {!enteredWorkspace ? (
        <Landing onEnter={handleEnterWorkspace} />
      ) : (
        <Workspace
          hcaptchaRef={hcaptchaRef}
          hcaptchaSiteKey={hcaptchaSiteKey}
          loading={loading}
          question={question}
          errorMessage={errorMessage}
          messages={messages}
          sources={sources}
          trace={trace}
          onBack={() => setEnteredWorkspace(false)}
          onQuestionChange={setQuestion}
          onSend={handleSend}
        />
      )}
    </div>
  );
}
