import { useState } from "react";
import { queryAgent } from "./lib/api";
import type { Message, SourceChunk, TraceStep } from "./lib/types";

const starterQuestions = [
  "Explain Retrieval-Augmented Generation and why it improves factuality.",
  "Compare DPR and BM25 for keyword-heavy research queries.",
  "What does FiD change about multi-passage answer synthesis?",
  "Summarize ReAct and why it matters for tool-using agents.",
  "When does HyDE improve retrieval quality?",
  "Which benchmarks help evaluate embedding models for retrieval?"
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

export default function App() {
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [sources, setSources] = useState<SourceChunk[]>([]);
  const [trace, setTrace] = useState<TraceStep[]>([]);
  const [loading, setLoading] = useState(false);

  const handleSend = async (value?: string) => {
    const text = (value ?? question).trim();
    if (!text || loading) return;

    setLoading(true);
    setMessages((prev) => [...prev, { role: "user", content: text }]);
    setQuestion("");

    try {
      const response = await queryAgent(text, 5);
      setMessages((prev) => [...prev, { role: "assistant", content: response.answer }]);
      setSources(response.sources);
      setTrace(response.trace);
    } catch (error) {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "Sorry, something went wrong." }
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page">
      <header className="hero">
        <div>
          <p className="eyebrow">AI Research Assistant</p>
          <h1>Research RAG Studio</h1>
          <p className="subtitle">
            Grounded answers over a curated corpus of AI, LLM, and retrieval research.
          </p>
          <div className="hero-metrics">
            <div>
              <span>Corpus</span>
              <strong>30+ papers and technical docs</strong>
            </div>
            <div>
              <span>Retrieval</span>
              <strong>Hybrid dense + BM25 with trace</strong>
            </div>
            <div>
              <span>LLM</span>
              <strong>Gemini-backed synthesis</strong>
            </div>
          </div>
        </div>
        <div className="hero-card">
          <p className="card-title">Suggested research questions</p>
          <div className="prompt-grid">
            {starterQuestions.map((prompt) => (
              <button key={prompt} onClick={() => handleSend(prompt)}>
                {prompt}
              </button>
            ))}
          </div>
        </div>
      </header>

      <main className="layout">
        <section className="chat">
          <div className="chat-header">
            <span className="badge">Research Agent</span>
            <p>Ask about papers, retrieval methods, or evaluation frameworks.</p>
          </div>
          <div className="chat-body">
            {messages.length === 0 ? (
              <div className="empty">
                <h3>Start with a research question</h3>
                <p>Answers are grounded in sources with traceable retrieval steps.</p>
              </div>
            ) : (
              messages.map((message, index) => (
                <div key={index} className={`message ${message.role}`}>
                  <div className="role">
                    {message.role === "user" ? "You" : "Research Assistant"}
                  </div>
                  {message.role === "assistant" && (
                    <div className="answer-label">Answer</div>
                  )}
                  <div className="content">{message.content}</div>
                </div>
              ))
            )}
          </div>
          <div className="chat-input">
            <input
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder="Ask about RAG, retrieval papers, or evaluation tradeoffs"
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  handleSend();
                }
              }}
            />
            <button onClick={() => handleSend()} disabled={loading}>
              {loading ? "Thinking..." : "Send"}
            </button>
          </div>
        </section>

        <aside className="side">
          <div className="panel">
            <h3>Sources</h3>
            {sources.length === 0 ? (
              <p className="muted">Sources appear after the first answer.</p>
            ) : (
              sources.map((source, index) => {
                const metaLine = formatMeta(source);
                return (
                  <div key={source.chunk_id} className="source">
                    <div className="source-header">
                      <div>
                        <span className="citation">[{index + 1}]</span>
                        <h4>{source.title || "Untitled"}</h4>
                      </div>
                      <span className="score">{source.score.toFixed(3)}</span>
                    </div>
                    {metaLine && <p className="source-meta">{metaLine}</p>}
                    <p className="source-snippet">{truncate(source.text, 260)}</p>
                    {source.url && (
                      <a className="source-link" href={source.url} target="_blank" rel="noreferrer">
                        Open source
                      </a>
                    )}
                  </div>
                );
              })
            )}
          </div>
          <details className="panel trace-panel">
            <summary>Trace</summary>
            {trace.length === 0 ? (
              <p className="muted">No trace yet.</p>
            ) : (
              trace.map((step, index) => (
                <div key={`${step.name}-${index}`} className="trace">
                  <div className="trace-title">{step.name}</div>
                  <pre>{step.detail}</pre>
                </div>
              ))
            )}
          </details>
        </aside>
      </main>
    </div>
  );
}
