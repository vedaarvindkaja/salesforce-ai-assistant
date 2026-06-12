# ADR-018: Renderer seam — dependency inversion at the extension's display boundary

**Status:** Accepted
**Date:** 2026-06-12 (Week 14, Day 1 — promoted from Week 13 NOTES)
**Decided by:** Veda Arvind

## Context

The VS Code extension (Week 13) displays streamed capability responses coming off
the REST spine over SSE. The SSE client emits a fixed sequence of events —
`chunk` (text fragment), `done` (stream complete), `error` — regardless of
*where* that text is shown.

Day 3 needed one render target (an OutputChannel) to prove the streaming spine.
Day 4 needed a second, richer one (a themed Markdown webview — the surface the
Week-14 README screenshots are captured from). More targets are plausible later
(a status-bar quick-peek; a Phase-2 sidebar webview).

Without a seam, the streaming/SSE plumbing would have to be touched every time a
new render target appeared: the Day-4 webview would mean editing the Day-3
streaming loop, and a third target would mean editing it again. Presentation
would be welded to transport.

## Decision

Define a `Renderer` interface — `start(title)`, `appendChunk(text)`, `done()`,
`error(message)` — whose method set mirrors the SSE event shape
(`chunk`/`done`/`error`). The client (`client.ts`) and `streamCapability()` talk
**only** to this interface, never to a concrete render target.

`OutputChannelRenderer` (Day 3) and `WebviewRenderer` (Day 4) both implement it.
`pickRenderer()` selects the implementation from the `salesforceGraph.renderer`
setting at call time. The streaming core, SSE client, and pure SSE parser never
import a render target.

## Alternatives considered

**Render directly from the streaming loop (no interface)**
- Pros: fewest moving parts for a single target.
- Cons: the Day-4 webview forces a rewrite of the streaming code; a third target
  forces another. Couples transport plumbing to presentation; the SSE parser
  ends up knowing about output channels.

**Branch on renderer type inside the streaming loop (`if webview … else …`)**
- Pros: one file, no new type.
- Cons: the loop grows a presentation switch that swells with every target *and*
  every event type; the parser/client accrete UI knowledge they shouldn't have.

## Trade-offs

- ✅ The Day-4 webview was a **renderer swap, not a plumbing change** — the SSE
  parser, client, and streaming core were untouched (verified: Day-4 NOTES).
- ✅ The interface mirrors the wire protocol (`chunk`/`done`/`error`), so there
  is one obvious contract; a new target implements four methods and nothing else.
- ✅ Testability: the pure SSE parser is tested against a fake renderer, so
  parsing is isolated from presentation (the 8 vitest cases, ADR-019).
- ❌ One layer of indirection for what is, today, two implementations — arguably
  YAGNI had the webview never been required.
- ❌ The interface must cover the union of what all renderers need (e.g. a title
  at `start`), which can leak a little presentation concern upward.

## Consequences

- Adding render targets (status-bar peek, Phase-2 sidebar) is an implementation,
  not a refactor.
- The `chunk`/`done`/`error` contract is now a small internal compatibility
  surface between the client and its renderers.
- The OutputChannel-first-then-webview **delivery sequence** (Day 3 → Day 4) was
  made cheap by this seam. That sequencing is a *consequence* of this decision,
  not an independent decision — it stays in NOTES, not its own ADR.
- Mirrors the backend's `_capability_response` seam (transport-uniform capability
  handling): the same dependency-inversion instinct applied on the TS side.
