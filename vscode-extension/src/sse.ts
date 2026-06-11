// Pure Server-Sent Events frame parser. No I/O, no vscode, no fetch — just text
// in, parsed events out — so it's unit-testable in plain Node (the same
// discipline as the backend's pure debuglog parser).
//
// SSE wire format (what sse-starlette emits for our capability routes):
//   event: chunk\n
//   data: <text fragment>\n
//   \n                          <- a blank line terminates a frame
// A single logical value spanning newlines is sent as MULTIPLE data: lines,
// which the spec says to rejoin with "\n". Comment lines (": ...", e.g. the
// heartbeat pings sse-starlette sends during quiet tool-call turns) and unknown
// fields are ignored.

export interface ServerSentEvent {
  event: string; // defaults to "message" if no event: field is present
  data: string; // all data: lines for the frame, joined with "\n"
}

/**
 * Incremental parser: SSE arrives in arbitrary byte chunks that don't align to
 * frame boundaries, so feed() buffers partial frames across calls and returns
 * only the complete events seen so far. Stateful by necessity (the buffer);
 * the parsing itself is pure.
 */
export class SSEParser {
  private buffer = "";

  feed(chunk: string): ServerSentEvent[] {
    // Normalize CRLF to LF so the "\n\n" frame boundary check is reliable
    // regardless of the server's line endings.
    this.buffer = (this.buffer + chunk).replace(/\r\n/g, "\n");

    const events: ServerSentEvent[] = [];
    let boundary: number;
    while ((boundary = this.buffer.indexOf("\n\n")) !== -1) {
      const rawFrame = this.buffer.slice(0, boundary);
      this.buffer = this.buffer.slice(boundary + 2);
      const parsed = this.parseFrame(rawFrame);
      if (parsed) {
        events.push(parsed);
      }
    }
    return events;
  }

  private parseFrame(raw: string): ServerSentEvent | null {
    let event = "message";
    const dataLines: string[] = [];

    for (const line of raw.split("\n")) {
      if (line === "" || line.startsWith(":")) {
        continue; // blank line or comment (": ping" heartbeat) — ignore
      }
      const colon = line.indexOf(":");
      const field = colon === -1 ? line : line.slice(0, colon);
      let value = colon === -1 ? "" : line.slice(colon + 1);
      if (value.startsWith(" ")) {
        value = value.slice(1); // spec: strip one leading space after the colon
      }
      if (field === "event") {
        event = value;
      } else if (field === "data") {
        dataLines.push(value);
      }
      // id / retry / unknown fields: ignored.
    }

    if (dataLines.length === 0 && event === "message") {
      return null; // nothing meaningful (e.g. a pure comment frame)
    }
    return { event, data: dataLines.join("\n") };
  }
}
