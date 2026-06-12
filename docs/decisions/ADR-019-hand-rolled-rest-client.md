# ADR-019: Hand-rolled REST client over OpenAPI codegen (incl. fetch-streaming over EventSource)

**Status:** Accepted
**Date:** 2026-06-12 (Week 14, Day 1 — promoted from Week 13 NOTES)
**Decided by:** Veda Arvind

## Context

The VS Code extension (Week 13) consumes the FastAPI REST spine (ADR-016: five
typed capability routes + a read-only `/graph`, all capability routes returning
SSE streams). Two coupled questions had to be answered before the Day-2 client:

1. **Codegen vs hand-rolled** — generate a typed TS client from the server's
   `/openapi.json`, or hand-write a thin one?
2. **How to consume SSE** — the browser `EventSource` API, or `fetch` with a
   streaming body reader?

The standard VS Code idiom for a server-backed extension is OpenAPI codegen, and
the standard browser idiom for SSE is `EventSource`. Both were rejected, for
reasons that turn out to be the same kind of reason: the surface is small and the
streams are POST.

## Decision

Hand-roll a thin, **runtime-vscode-free** client (`client.ts`) with two methods:

- `fetchGraphSummary()` — readiness probe returning a `ProbeResult` discriminated
  union (`ready` / `not-ready` / `unreachable` / `http-error`).
- `streamCapability()` — `POST` + `fetch` streaming body reader → `SSEParser` →
  `Renderer` (ADR-018).

Do **not** use OpenAPI codegen. Consume SSE via the `fetch` streaming body
reader, **not** `EventSource`.

## Alternatives considered

**OpenAPI codegen (rejected)**
- The case for it: idiomatic for large API surfaces; generates request/response
  types and a client straight from the schema; keeps TS types in lockstep with
  the server.
- Why rejected here:
  - The surface is tiny — **two** request models (`CapabilityRequest`,
    `DebugLogRequest`) across five near-identical routes. The generated client
    would be more machinery than the ~2 methods it replaces.
  - Codegen models request/response **JSON**; these routes return **SSE
    streams**, which codegen doesn't represent. The streaming method would be
    hand-written regardless — so codegen would cover only the trivial part.
  - A generator + its versioning would join the build for little gain.
- **Revisit trigger:** the request-model count crosses **~10**, or the routes
  diverge enough that hand-maintained TS types become the larger drift risk.

**`EventSource` for SSE (rejected — folded here as a consequence, not its own ADR)**
- `EventSource` issues **GET** requests with **no body**. The capability routes
  are **POST** carrying a JSON body (the question, or the debug-log reference).
  `EventSource` structurally cannot carry that body, so it is incompatible with
  the route shape locked in ADR-016.
- `fetch` issues the POST and exposes the response as a readable stream; a pure
  `SSEParser` re-frames the byte chunks into `chunk`/`done`/`error` events.
- This is **forced by the POST-route choice** — a consequence, not an independent
  trade-off — which is why it lives inside this ADR rather than its own.

## Trade-offs

- ✅ The client is two small methods, unit-testable with no `vscode` dependency,
  and adds no generator to the build.
- ✅ `fetch`-streaming handles POST+SSE that `EventSource` structurally cannot;
  the frame parser is **pure and unit-tested** (8 vitest cases), mirroring the
  backend debug-log parser discipline (ADR-017).
- ✅ The `ProbeResult` discriminated union makes the three-state readiness model
  explicit at the type level — the extension is the first consumer of the
  503-not-401 precondition decision (ADR-016 / Week-12 gating).
- ❌ Hand-rolled types can drift from the server schema — there is no
  compile-time link between the FastAPI models and the TS bodies. Acceptable at
  two models; the ~10-model trigger is where this flips.
- ❌ Re-implementing SSE framing (vs a library) is code we own and must test;
  mitigated by keeping it pure and unit-tested.

## Consequences

- The TS `RequestBody = CapabilityBody | DebugLogBody` union mirrors the
  backend's `CapabilityRequest` / `DebugLogRequest` asymmetry (ADR-017) **by
  hand** — the two are kept in sync manually until the trigger flips to codegen.
- The pure `SSEParser` is the first automated-tested unit on the TS side and the
  testability anchor for the Renderer seam (ADR-018).
- If hosted/multi-user packaging arrives (downstream of the API-key trigger), the
  codegen and `EventSource`-vs-`fetch` calculus should both be re-run.
