// HTTP + SSE client for the Loupe research API (REVAMP_PLAN §6).
// SSE is consumed via fetch + ReadableStream because the endpoints are POSTs.

import { parseSSE } from "./sse";
import type { Health, Mode, ResearchEvent, ThreadSummary } from "./types";

const baseUrl = (import.meta.env.VITE_API_BASE_URL || "http://localhost:8000").replace(/\/$/, "");

export type ResearchBody = {
  question: string;
  mode: Mode;
  thread_id?: string | null;
  captcha_token?: string | null;
};

const KNOWN_EVENTS = new Set([
  "accepted",
  "stage",
  "plan",
  "evidence",
  "interrupt",
  "token",
  "claims",
  "usage",
  "done",
  "error",
]);

async function openStream(path: string, body: unknown, signal?: AbortSignal): Promise<Response> {
  const response = await fetch(`${baseUrl}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify(body),
    signal,
  });
  if (!response.ok || !response.body) {
    let detail = `Request failed (${response.status})`;
    try {
      const payload = await response.json();
      detail = payload.detail || detail;
    } catch {
      // non-JSON body; keep the generic message
    }
    throw new Error(detail);
  }
  return response;
}

async function* readEvents(
  response: Response,
  signal?: AbortSignal
): AsyncGenerator<ResearchEvent> {
  for await (const raw of parseSSE(response.body as ReadableStream<Uint8Array>, signal)) {
    if (!KNOWN_EVENTS.has(raw.event)) continue;
    let data: unknown;
    try {
      data = JSON.parse(raw.data);
    } catch {
      continue; // malformed payload; skip rather than crash the stream
    }
    yield { event: raw.event, data } as ResearchEvent;
  }
}

/** Start a research run. Yields typed SSE events until the stream closes. */
export async function* streamResearch(
  body: ResearchBody,
  signal?: AbortSignal
): AsyncGenerator<ResearchEvent> {
  const response = await openStream("/api/research", body, signal);
  yield* readEvents(response, signal);
}

/** Resume a Deep-mode run paused at the HITL approval interrupt. */
export async function* approveResearch(
  threadId: string,
  approved: boolean,
  signal?: AbortSignal
): AsyncGenerator<ResearchEvent> {
  const response = await openStream(
    `/api/research/${encodeURIComponent(threadId)}/approve`,
    { approved },
    signal
  );
  yield* readEvents(response, signal);
}

/** Recover the last state of a thread (reconnect / page-refresh, §6). */
export async function getThread(threadId: string): Promise<ThreadSummary | null> {
  const response = await fetch(`${baseUrl}/api/threads/${encodeURIComponent(threadId)}`);
  if (response.status === 404) return null;
  if (!response.ok) throw new Error(`Thread lookup failed (${response.status})`);
  return response.json();
}

export async function getHealth(): Promise<Health> {
  const response = await fetch(`${baseUrl}/api/health`);
  if (!response.ok) throw new Error(`Health check failed (${response.status})`);
  return response.json();
}
