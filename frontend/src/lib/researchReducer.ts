// Pure state machine for a research conversation (REVAMP_PLAN §11).
// No React here so it can be unit-tested directly; the `useResearch` hook wires
// this reducer to useReducer and the SSE stream.

import type {
  ClaimAudit,
  EvidenceChunk,
  InterruptEvent,
  Mode,
  Outcome,
  ResearchEvent,
  StageEvent,
  SubQuestion,
  Usage,
} from "./types";

export type RunPhase = "idle" | "streaming" | "interrupted" | "done" | "error";

export type Turn = {
  id: string;
  question: string;
  mode: Mode;
  answerMd: string | null;
  outcome: Outcome | null;
  claims: ClaimAudit[];
  sources: EvidenceChunk[];
  usage: Usage | null;
  cached: boolean;
};

export type ResearchState = {
  phase: RunPhase;
  threadId: string | null;
  corpusVersion: string | null;
  mode: Mode;
  turns: Turn[];
  // In-flight / most-recent run (drives the investigation panel).
  currentQuestion: string | null;
  streamingAnswer: string;
  stages: StageEvent[];
  subQuestions: SubQuestion[];
  evidence: Record<string, EvidenceChunk[]>;
  claims: ClaimAudit[];
  usage: Usage | null;
  interrupt: InterruptEvent | null;
  error: { code: string; message: string } | null;
  cached: boolean;
};

export const initialState: ResearchState = {
  phase: "idle",
  threadId: null,
  corpusVersion: null,
  mode: "quick",
  turns: [],
  currentQuestion: null,
  streamingAnswer: "",
  stages: [],
  subQuestions: [],
  evidence: {},
  claims: [],
  usage: null,
  interrupt: null,
  error: null,
  cached: false,
};

export type Action =
  | { type: "SUBMIT"; question: string; mode: Mode }
  | { type: "APPROVE_START" }
  | { type: "EVENT"; event: ResearchEvent }
  | { type: "STREAM_ERROR"; message: string }
  | { type: "RECOVERED"; turn: Turn }
  | { type: "RESTORE"; threadId: string; turn: Turn }
  | { type: "RESET" };

function resetRunFields(): Partial<ResearchState> {
  return {
    currentQuestion: null,
    streamingAnswer: "",
    stages: [],
    subQuestions: [],
    evidence: {},
    claims: [],
    usage: null,
    interrupt: null,
    error: null,
    cached: false,
  };
}

export function reducer(state: ResearchState, action: Action): ResearchState {
  switch (action.type) {
    case "SUBMIT":
      return {
        ...state,
        ...resetRunFields(),
        phase: "streaming",
        mode: action.mode,
        currentQuestion: action.question,
      };

    case "APPROVE_START":
      // Resume the paused run: keep the in-flight question, clear the interrupt.
      return { ...state, phase: "streaming", interrupt: null, error: null };

    case "STREAM_ERROR":
      return { ...state, phase: "error", error: { code: "internal", message: action.message } };

    case "RECOVERED":
      return {
        ...state,
        phase: "done",
        currentQuestion: null,
        streamingAnswer: "",
        interrupt: null,
        error: null,
        claims: action.turn.claims,
        turns: [...state.turns, action.turn],
      };

    case "RESTORE":
      // Rehydrate a prior thread after a page reload (§11 recovery).
      return {
        ...state,
        ...resetRunFields(),
        phase: "done",
        threadId: action.threadId,
        claims: action.turn.claims,
        turns: [action.turn],
      };

    case "RESET":
      return { ...initialState };

    case "EVENT":
      return applyEvent(state, action.event);
  }
}

export function applyEvent(state: ResearchState, evt: ResearchEvent): ResearchState {
  switch (evt.event) {
    case "accepted":
      return {
        ...state,
        threadId: evt.data.thread_id,
        mode: evt.data.mode,
        corpusVersion: evt.data.corpus_version,
      };

    case "stage":
      return { ...state, stages: [...state.stages, evt.data] };

    case "plan":
      return { ...state, subQuestions: evt.data.sub_questions };

    case "evidence":
      return {
        ...state,
        evidence: { ...state.evidence, [evt.data.sub_question_id]: evt.data.chunks },
      };

    case "token":
      return { ...state, streamingAnswer: state.streamingAnswer + evt.data.text };

    case "claims":
      return { ...state, claims: evt.data.claims };

    case "usage":
      return { ...state, usage: evt.data };

    case "interrupt":
      return { ...state, phase: "interrupted", interrupt: evt.data };

    case "done": {
      const turn: Turn = {
        id: state.threadId
          ? `${state.threadId}-${state.turns.length}`
          : `turn-${state.turns.length}`,
        question: state.currentQuestion ?? "",
        mode: state.mode,
        answerMd: evt.data.answer_md,
        outcome: evt.data.outcome,
        claims: state.claims,
        sources: evt.data.sources,
        usage: state.usage,
        cached: evt.data.cached,
      };
      return {
        ...state,
        phase: "done",
        currentQuestion: null,
        streamingAnswer: "",
        interrupt: null,
        cached: evt.data.cached,
        turns: [...state.turns, turn],
      };
    }

    case "error":
      return { ...state, phase: "error", error: evt.data };
  }
}
