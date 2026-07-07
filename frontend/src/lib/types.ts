// Wire types mirroring the backend SSE contract (REVAMP_PLAN §6).
// These intentionally match the JSON payloads emitted by the graph nodes so the
// reducer can consume events without translation.

export type Mode = "quick" | "deep";

export type Outcome = "answered" | "refused" | "redirected" | "budget_exceeded";

export type Origin = "corpus" | "web";

export type Trust = "normal" | "low";

export type Verdict = "SUPPORTED" | "PARTIAL" | "UNSUPPORTED";

/** Score map attached to each evidence chunk: {dense, bm25, fused}. */
export type Scores = {
  dense?: number | null;
  bm25?: number | null;
  fused?: number | null;
};

/**
 * EvidenceChunk-lite. The `evidence` event omits `source_id` (assigned later at
 * synthesis time); the `done`/threads payloads include it. Hence optional.
 */
export type EvidenceChunk = {
  id: string;
  source_id?: string;
  doc_title: string;
  section: string | null;
  url: string | null;
  origin: Origin;
  scores: Scores;
  trust: Trust;
  text: string;
};

export type SubQuestion = {
  id: string;
  text: string;
};

export type ClaimAudit = {
  id: string;
  text: string;
  verdict: Verdict;
  evidence_ids: string[];
  note: string;
};

export type Usage = {
  llm_calls: number;
  input_tokens: number;
  output_tokens: number;
  web_fetches: number;
  est_cost_usd: number;
  wall_ms: number;
};

export type StageEvent = {
  node: string;
  status: "start" | "end";
  summary: string;
  elapsed_ms: number;
  iteration: number;
};

// --- SSE event payloads (data of each named event) ---

export type AcceptedEvent = {
  thread_id: string;
  mode: Mode;
  corpus_version: string;
};

export type PlanEvent = { sub_questions: SubQuestion[] };

export type EvidenceEvent = {
  sub_question_id: string;
  chunks: EvidenceChunk[];
};

export type InterruptEvent = { reason: string; message: string };

export type TokenEvent = { text: string };

export type ClaimsEvent = { claims: ClaimAudit[] };

export type DoneEvent = {
  outcome: Outcome;
  answer_md: string | null;
  sources: EvidenceChunk[];
  cached: boolean;
};

export type ErrorCode = "rate_limited" | "captcha_failed" | "budget_exceeded" | "internal";

export type ErrorEvent = { code: ErrorCode; message: string };

/** Discriminated union of every event the client acts on. */
export type ResearchEvent =
  | { event: "accepted"; data: AcceptedEvent }
  | { event: "stage"; data: StageEvent }
  | { event: "plan"; data: PlanEvent }
  | { event: "evidence"; data: EvidenceEvent }
  | { event: "interrupt"; data: InterruptEvent }
  | { event: "token"; data: TokenEvent }
  | { event: "claims"; data: ClaimsEvent }
  | { event: "usage"; data: Usage }
  | { event: "done"; data: DoneEvent }
  | { event: "error"; data: ErrorEvent };

/** GET /api/threads/{id} recovery payload (§6). */
export type ThreadSummary = {
  question: string;
  outcome: Outcome;
  answer_md: string | null;
  claims: ClaimAudit[];
  sources: EvidenceChunk[];
};

export type Health = {
  status: string;
  corpus_version: string;
  chunks: number;
  web_tool: boolean;
  tracing: boolean;
};
