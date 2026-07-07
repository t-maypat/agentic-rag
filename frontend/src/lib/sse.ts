// Minimal SSE parser over a fetch ReadableStream.
//
// We use fetch + ReadableStream (not native EventSource) because /api/research is
// a POST with a JSON body. sse-starlette emits `event:`/`data:` blocks separated
// by a blank line, plus `:`-prefixed comment lines for keep-alive pings — those
// are ignored here.

export type RawEvent = { event: string; data: string };

/**
 * Read an SSE response body, yielding one {event, data} per complete block.
 * `data` is the concatenation of all `data:` lines (newline-joined).
 */
export async function* parseSSE(
  body: ReadableStream<Uint8Array>,
  signal?: AbortSignal
): AsyncGenerator<RawEvent> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  // Event blocks are separated by a blank line: "\n\n" or (sse-starlette) "\r\n\r\n".
  const boundary = /\r?\n\r?\n/;
  let buffer = "";

  try {
    while (true) {
      if (signal?.aborted) return;
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      let m = boundary.exec(buffer);
      while (m !== null) {
        const block = buffer.slice(0, m.index);
        buffer = buffer.slice(m.index + m[0].length);
        const parsed = parseBlock(block);
        if (parsed) yield parsed;
        m = boundary.exec(buffer);
      }
    }
    // Flush any trailing block without a terminating blank line.
    const parsed = parseBlock(buffer);
    if (parsed) yield parsed;
  } finally {
    reader.releaseLock();
  }
}

function parseBlock(block: string): RawEvent | null {
  let event = "message";
  const dataLines: string[] = [];
  for (const rawLine of block.split("\n")) {
    const line = rawLine.replace(/\r$/, "");
    if (!line || line.startsWith(":")) continue; // blank or comment (ping)
    if (line.startsWith("event:")) {
      event = line.slice(6).trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice(5).replace(/^ /, ""));
    }
  }
  if (dataLines.length === 0) return null;
  return { event, data: dataLines.join("\n") };
}
