# REST API Reference

The REST API is the HTTP transport for the Salesforce Graph platform — and the
spine the VS Code extension rides. It is built on FastAPI, streams answers over
Server-Sent Events (SSE), and is one of four transports over a shared
intelligence core (see [`architecture.md`](architecture.md)).

**Base URL (local):** `http://127.0.0.1:8000`
Start it from the `backend/` directory:

```bash
uvicorn app.main:app --reload
```

**Scope:** Phase 1 is local / single-user. There is **no caller authentication** —
access is gated only by server *readiness* (a `503` until the metadata graph is
built). API-key auth and rate limiting are parked (trigger: more than one user).
Interactive OpenAPI docs are served at `/docs`.

---

## Readiness — `GET /api/v1/graph`

A zero-cost readiness probe and graph summary: no Claude call, no streaming.
Returns `200` with a `GraphSummary`, or `503` if the graph isn't loaded. The VS
Code extension uses this as its connection probe.

**`GraphSummary`**

| Field | Type | Meaning |
|---|---|---|
| `org_key` | string | The org the graph was built from (its `instance_url`). |
| `node_count` | int | Total nodes in the graph. |
| `edge_count` | int | Total edges in the graph. |
| `node_type_counts` | object<string,int> | Per-node-type breakdown (e.g. `ApexClass`, `Object`, `Flow`). |
| `edge_type_counts` | object<string,int> | Per-edge-type breakdown (e.g. `REFERENCES`, `CALLS`). |

```bash
curl http://127.0.0.1:8000/api/v1/graph
```

```json
{
  "org_key": "https://your-org.my.salesforce.com",
  "node_count": 57,
  "edge_count": 172,
  "node_type_counts": { "ApexClass": 31, "ApexTrigger": 4, "Object": 18, "Flow": 4 },
  "edge_type_counts": { "REFERENCES": 120, "CALLS": 38, "USES_OBJECT": 14 }
}
```

If the graph isn't loaded:

```json
{ "detail": "metadata graph not loaded" }
```
(HTTP `503` — see [Errors](#errors). The counts above are illustrative.)

---

## Capabilities (streaming) — `POST /api/v1/{capability}`

Five capability routes. Four take a question; `debug-log-analysis` takes a log
*reference*. All stream the answer as SSE.

| Route | Body | What it does |
|---|---|---|
| `POST /api/v1/metadata-qa` | `CapabilityRequest` | Q&A over the metadata graph. |
| `POST /api/v1/apex-explain` | `CapabilityRequest` | Explain Apex with graph-aware dependencies. |
| `POST /api/v1/soql-generate` | `CapabilityRequest` | Natural language → SOQL grounded in your schema. |
| `POST /api/v1/deployment-impact` | `CapabilityRequest` | Blast-radius of a change from the dependency graph. |
| `POST /api/v1/debug-log-analysis` | `DebugLogRequest` | Root-cause a debug log against the graph + source. |

### Request bodies

**`CapabilityRequest`** (the four question-shaped routes):

```json
{ "question": "Which Apex classes reference AccountTriggerHandler?" }
```

- `question` — string, **required**, non-empty.

**`DebugLogRequest`** (`debug-log-analysis` only — a log reference, not a bare
question; ADR-017):

```json
{ "log_path": "/srv/logs/case_insert.log", "question": "why did the insert fail?" }
```

- `log_path` — string, **required**. A path readable by the server (absolute, or
  relative to `backend/`). The raw log is parsed and correlated **server-side**;
  only structured prose reaches the model.
- `question` — string, optional. Focuses the analysis.

### Worked example — deployment impact

```bash
curl -N -X POST http://127.0.0.1:8000/api/v1/deployment-impact \
  -H "Content-Type: application/json" \
  -d '{"question": "What breaks if I change the Opportunity object?"}'
```

The response is an SSE stream (`-N` disables curl's buffering so chunks print as
they arrive):

```
event: chunk
data: Changing Opportunity affects 6 components

event: chunk
data:  across 2 hops: OpportunityTrigger → TriggerDispatcher → ...

event: done
data:
```

The other three question routes behave identically; `debug-log-analysis` differs
only in its request body.

---

## SSE event reference

The capability routes stream Server-Sent Events via `sse-starlette`. Three event
types:

| `event:` | `data:` | Meaning |
|---|---|---|
| `chunk` | a text fragment | Append to the answer as it streams. |
| `done` | *(empty)* | The stream completed successfully. |
| `error` | an error message | The agentic loop failed; the stream ends. |

Notes:

- **Heartbeats.** Comment lines (`: ping`) are sent during quiet agentic
  tool-call turns to keep the connection alive. Clients ignore them.
- **Cancellation.** A client disconnect cancels the Claude loop server-side — an
  abandoned request stops burning tokens rather than running to completion.
- **Multi-line values.** A single logical value spanning newlines is sent as
  multiple `data:` lines, rejoined with `\n` (per the SSE spec).

A reference consumer is the extension's pure frame parser,
`vscode-extension/src/sse.ts` (8 unit tests).

---

## Errors

| Status | When | Body |
|---|---|---|
| `422` | Empty/missing `question` (or `log_path`). | Pydantic validation error. |
| `503` | Graph not loaded (readiness). | `{"detail": "metadata graph not loaded"}` |
| `error` event | The agentic loop raised mid-stream. | `event: error` / `data: <message>` — the HTTP status is already `200`, so the failure surfaces *in-stream*, not as an HTTP error code. |

`503` is a **precondition** (server readiness), not `401` — re-authenticating
won't fix it; the graph simply hasn't been built. Build it with
`python -m scripts.extract_to_cache` (see the project README Quickstart). This is
the 503-not-401 decision (ADR-016).

---

## The other transports

This API is one of four transports over the same intelligence core. For the **MCP
server** (Claude Desktop / Claude Code / Augment AI), see
[`mcp-server.md`](mcp-server.md). For the **CLI** and **VS Code extension**, see
the [project README](../README.md). All share one graph loader and one capability
registry, so a capability behaves identically across every transport.
