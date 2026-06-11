// Thin, hand-rolled REST client for the Salesforce Graph API.
//
// Deliberately free of the `vscode` module so it stays unit-testable in plain
// Node later (mirrors the backend's pure-parser discipline: this is I/O glue,
// not editor coupling). All vscode interaction lives in extension.ts.
//
// Python/Apex bridge: think of this as an Apex class wrapping
// Http/HttpRequest/HttpResponse that hands back a typed result wrapper instead
// of a raw response. Callers switch on result.status; they never inspect status
// codes or catch exceptions themselves.

/** Mirror of the REST `GraphSummary` Pydantic model (routes/graph.py). */
export interface GraphSummary {
  org_key: string;
  node_count: number;
  edge_count: number;
  node_type_counts: Record<string, number>;
  edge_type_counts: Record<string, number>;
}

/**
 * The states the API can be in. A discriminated union: the `status` field tells
 * the caller which other fields exist (TypeScript's version of a sealed result
 * type / tagged enum). The compiler forces the caller to handle each case.
 */
export type ProbeResult =
  | { status: "ready"; summary: GraphSummary } // 200: graph loaded
  | { status: "not-ready"; detail: string } // 503: server up, graph absent
  | { status: "unreachable"; detail: string } // fetch threw: server down/timeout
  | { status: "http-error"; detail: string }; // any other non-OK status

const GRAPH_PATH = "/api/v1/graph";
const TIMEOUT_MS = 5000;

/**
 * Probe API readiness via the zero-cost GET /api/v1/graph. Never throws: every
 * failure mode is mapped to a ProbeResult variant so the caller branches
 * declaratively. The AbortController bounds a hung connection (like
 * HttpRequest.setTimeout in Apex / a cancellation token).
 */
export async function fetchGraphSummary(baseUrl: string): Promise<ProbeResult> {
  const url = baseUrl.replace(/\/+$/, "") + GRAPH_PATH;

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);

  let response: Response;
  try {
    response = await fetch(url, {
      method: "GET",
      headers: { Accept: "application/json" },
      signal: controller.signal,
    });
  } catch (err) {
    // Network-level failure: connection refused (uvicorn not running) or the
    // abort above fired. This is the "server down / unreachable" branch.
    const detail = controller.signal.aborted
      ? `No response within ${TIMEOUT_MS / 1000}s from ${baseUrl}.`
      : err instanceof Error
        ? err.message
        : String(err);
    return { status: "unreachable", detail };
  } finally {
    clearTimeout(timer);
  }

  if (response.status === 503) {
    // Precondition gate (503-not-401): server is up, graph isn't loaded.
    let detail = "metadata graph not loaded";
    try {
      const body = (await response.json()) as { detail?: string };
      if (body?.detail) {
        detail = body.detail;
      }
    } catch {
      // Non-JSON body; keep the default detail.
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
