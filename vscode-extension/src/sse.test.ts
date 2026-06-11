import { describe, it, expect } from "vitest";

import { SSEParser } from "./sse";

describe("SSEParser", () => {
  it("parses a single chunk event", () => {
    const p = new SSEParser();
    expect(p.feed("event: chunk\ndata: Hello\n\n")).toEqual([
      { event: "chunk", data: "Hello" },
    ]);
  });

  it("joins multiple data lines with newline", () => {
    const p = new SSEParser();
    expect(p.feed("event: chunk\ndata: line one\ndata: line two\n\n")).toEqual([
      { event: "chunk", data: "line one\nline two" },
    ]);
  });

  it("buffers a frame split across two feeds", () => {
    const p = new SSEParser();
    expect(p.feed("event: chunk\nda")).toEqual([]);
    expect(p.feed("ta: split\n\n")).toEqual([{ event: "chunk", data: "split" }]);
  });

  it("emits multiple frames from one feed", () => {
    const p = new SSEParser();
    expect(p.feed("event: chunk\ndata: a\n\nevent: chunk\ndata: b\n\n")).toEqual([
      { event: "chunk", data: "a" },
      { event: "chunk", data: "b" },
    ]);
  });

  it("ignores comment/heartbeat lines", () => {
    const p = new SSEParser();
    expect(p.feed(": ping\n\nevent: chunk\ndata: x\n\n")).toEqual([
      { event: "chunk", data: "x" },
    ]);
  });

  it("parses the terminal done event with empty data", () => {
    const p = new SSEParser();
    expect(p.feed("event: done\ndata: \n\n")).toEqual([
      { event: "done", data: "" },
    ]);
  });

  it("normalizes CRLF line endings", () => {
    const p = new SSEParser();
    expect(p.feed("event: chunk\r\ndata: crlf\r\n\r\n")).toEqual([
      { event: "chunk", data: "crlf" },
    ]);
  });

  it("surfaces an error event", () => {
    const p = new SSEParser();
    expect(p.feed("event: error\ndata: boom\n\n")).toEqual([
      { event: "error", data: "boom" },
    ]);
  });
});
