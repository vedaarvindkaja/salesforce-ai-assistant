// Thin, hand-rolled REST client for the Salesforce Graph API.
//
// Deliberately free of the `vscode` module so it stays unit-testable in plain
// Node (mirrors the backend's pure-parser discipline). The Renderer dependency
// is a type-only import, so it adds no runtime coupling.

import { SSEParser, type ServerSentEvent } from "./sse";
import type { Renderer } from "./renderer";

/** Mirror of the REST `GraphSummary` Pydantic model (routes/graph.py). */
export interface GraphSummary {
  org_key: string;
  node_count: number;
  edge_count: number;
  node_type_counts: Record<string, number>;
  edge_type_counts: Record<string, number>;
}

export type ProbeResult =
  | { status: "ready"; summary: GraphSummary }
  | { status: "not-ready"; detail: string }
  | { status: "unreachable"; detail: string }
  | { status: "http-error"; detail: string };

/** Body for the question-shaped capability routes (CapabilityRequest). */
export interface CapabilityBody {
  question: string;
}

/** Body for the debug-log route (DebugLogRequest) — a log REFERENCE (ADR-017). */
export interface DebugLogBody {
  log_path: string;
  question?: string;
}

/** Any capability request body — streamCapability only serializes it. */
export type RequestBody = CapabilityBody | DebugLogBody;

const GRAPH_PATH = "/api/v1/graph";
const PROBE_TIMEOUT_MS = 5000;

function joinUrl(baseUrl: string, path: string): string {
  return baseUrl.replace(/\/+$/, "") + path;
}

/** Probe API readiness via the zero-cost GET /api/v1/graph. Never throws. */
export async function fetchGraphSummary(baseUrl: string): Promise<ProbeResult> {
  const url = joinUrl(baseUrl, GRAPH_PATH);
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), PROBE_TIMEOUT_MS);

  let response: Response;
  try {
    response = await fetch(url, {
      method: "GET",
      headers: { Accept: "application/json" },
      signal: controller.signal,
    });
  } catch (err) {
    const detail = controller.signal.aborted
      ? `No response within ${PROBE_TIMEOUT_MS / 1000}s from ${baseUrl}.`
      : err instanceof Error
        ? err.message
        : String(err);
    return { status: "unreachable", detail };
  } finally {
    clearTimeout(timer);
  }

  if (response.status === 503) {
    let detail = "metadata graph not loaded";
    try {
      const body = (await response.json()) as { detail?: string };
      if (body?.detail) {
        detail = body.detail;
      }
    } catch {
      // non-JSON body; keep the default detail
    }
    return { status: "not-ready", detail };
  }

  if (!response.ok) {
    return {
      status: "http-error",
      detail: `HTTP ${response.status} ${response.statusText}`,
    };
  }

  const summary = (await response.json()) as GraphSummary;
  return { status: "ready", summary };
}

/**
 * POST to a streaming capability route and push the Server-Sent Events to the
 * renderer as they arrive. POST + fetch streaming body reader (not EventSource:
 * GET-only, browser-only). Never throws: failures go through renderer.error.
 */
export async function streamCapability(
  baseUrl: string,
  path: string,
  body: RequestBody,
  renderer: Renderer,
  signal?: AbortSignal
): Promise<void> {
  const url = joinUrl(baseUrl, path);

  let response: Response;
  try {
    response = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "text/event-stream",
      },
      body: JSON.stringify(body),
      signal,
    });
  } catch (err) {
    if (signal?.aborted) {
      return;
    }
    renderer.error(
      `Can't reach the API at ${baseUrl}. Is it running ` +
        `(uvicorn app.main:app --reload, from backend/)? ` +
        (err instanceof Error ? err.message : String(err))
    );
    return;
  }

  if (response.status === 503) {
    renderer.error("The API is up but the metadata graph isn't loaded (503).");
    return;
  }
  if (response.status === 422) {
    renderer.error("The API rejected the request (422 — invalid input).");
    return;
  }
  if (!response.ok || !response.body) {
    renderer.error(
      `Unexpected response: HTTP ${response.status} ${response.statusText}`
    );
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  const parser = new SSEParser();

  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) {
        break;
      }
      for (const evt of parser.feed(decoder.decode(value, { stream: true }))) {
        dispatch(evt, renderer);
      }
    }
    const tail = decoder.decode();
    if (tail) {
      for (const evt of parser.feed(tail)) {
        dispatch(evt, renderer);
      }
    }
  } catch (err) {
    if (signal?.aborted) {
      return;
    }
    renderer.error(err instanceof Error ? err.message : String(err));
  }
}

function dispatch(evt: ServerSentEvent, renderer: Renderer): void {
  switch (evt.event) {
    case "chunk":
      renderer.appendChunk(evt.data);
      break;
    case "done":
      renderer.done();
      break;
    case "error":
      renderer.error(evt.data);
      break;
  }
}
