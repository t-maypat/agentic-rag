// Stream state machine for a research conversation (REVAMP_PLAN §11).
// Plain React: useReducer drives the SSE event stream; no external state lib.
// The pure reducer lives in ../lib/researchReducer so it can be unit-tested.

import { useCallback, useEffect, useReducer, useRef } from "react";
import { approveResearch, getThread, streamResearch } from "../lib/api";
import { initialState, reducer } from "../lib/researchReducer";
import type { Mode, ResearchEvent } from "../lib/types";

export type { ResearchState, RunPhase, Turn } from "../lib/researchReducer";

const THREAD_STORAGE_KEY = "loupe_thread_id";

export function useResearch() {
  const [state, dispatch] = useReducer(reducer, initialState);
  const abortRef = useRef<AbortController | null>(null);
  const recoveredRef = useRef(false);
  const threadIdRef = useRef<string | null>(null);
  const modeRef = useRef<Mode>("quick");

  // Keep refs of live values (reducer state is stale inside the long-lived
  // `drain` closure) and persist the thread id so a reload can recover (§11).
  useEffect(() => {
    threadIdRef.current = state.threadId;
    try {
      if (state.threadId) sessionStorage.setItem(THREAD_STORAGE_KEY, state.threadId);
    } catch {
      // sessionStorage unavailable (e.g. privacy mode) — recovery just won't persist.
    }
  }, [state.threadId]);

  useEffect(() => {
    modeRef.current = state.mode;
  }, [state.mode]);

  // On first mount, rehydrate the last thread's final state if one is stored.
  useEffect(() => {
    let stored: string | null = null;
    try {
      stored = sessionStorage.getItem(THREAD_STORAGE_KEY);
    } catch {
      stored = null;
    }
    if (!stored) return;
    const threadId = stored;
    let cancelled = false;
    getThread(threadId)
      .then((summary) => {
        if (cancelled || !summary) return;
        dispatch({
          type: "RESTORE",
          threadId,
          turn: {
            id: `${threadId}-restored`,
            question: summary.question,
            mode: "quick",
            answerMd: summary.answer_md,
            outcome: summary.outcome,
            claims: summary.claims,
            sources: summary.sources,
            usage: null,
            cached: false,
          },
        });
      })
      .catch(() => {
        // Stale/expired thread (ephemeral disk) — start fresh.
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const drain = useCallback(
    async (stream: AsyncGenerator<ResearchEvent>): Promise<void> => {
      let sawTerminal = false;
      try {
        for await (const event of stream) {
          if (event.event === "done" || event.event === "error") sawTerminal = true;
          dispatch({ type: "EVENT", event });
        }
        if (sawTerminal) recoveredRef.current = false;
      } catch (err) {
        if (abortRef.current?.signal.aborted) return;
        // Reconnect ONCE via the thread summary to recover a completed run (§11).
        const id = threadIdRef.current;
        if (id && !recoveredRef.current && !sawTerminal) {
          recoveredRef.current = true;
          try {
            const summary = await getThread(id);
            if (summary) {
              dispatch({
                type: "RECOVERED",
                turn: {
                  id: `${id}-recovered`,
                  question: summary.question,
                  mode: modeRef.current,
                  answerMd: summary.answer_md,
                  outcome: summary.outcome,
                  claims: summary.claims,
                  sources: summary.sources,
                  usage: null,
                  cached: false,
                },
              });
              return;
            }
          } catch {
            // fall through to a stream error
          }
        }
        dispatch({
          type: "STREAM_ERROR",
          message: err instanceof Error ? err.message : "The connection was lost.",
        });
      }
    },
    []
  );

  const submit = useCallback(
    (question: string, mode: Mode, captchaToken?: string | null) => {
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;
      recoveredRef.current = false;
      dispatch({ type: "SUBMIT", question, mode });
      const stream = streamResearch(
        { question, mode, thread_id: threadIdRef.current, captcha_token: captchaToken ?? null },
        controller.signal
      );
      void drain(stream);
    },
    [drain]
  );

  const approve = useCallback(
    (approved: boolean) => {
      const id = threadIdRef.current;
      if (!id) return;
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;
      dispatch({ type: "APPROVE_START" });
      const stream = approveResearch(id, approved, controller.signal);
      void drain(stream);
    },
    [drain]
  );

  const reset = useCallback(() => {
    abortRef.current?.abort();
    try {
      sessionStorage.removeItem(THREAD_STORAGE_KEY);
    } catch {
      // ignore
    }
    dispatch({ type: "RESET" });
  }, []);

  return { state, submit, approve, reset };
}
