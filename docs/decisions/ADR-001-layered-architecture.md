# ADR-001: Layered architecture (salesforce / intelligence / interfaces)

**Status:** Accepted
**Date:** 2026-05-26 (Week 4, Day 1)
**Decided by:** Veda Arvind

## Context

Week 3 ended with a flat `app/services/` and `app/routes/` structure. Sufficient
for one REST API consumer with three endpoints. Week 4 began the strategic pivot
to a developer intelligence platform with multiple future consumers (MCP server,
VS Code extension, CLI) and multiple Salesforce APIs (REST, Tooling, Metadata).

The flat structure would not scale. Where does an MCP server live? `app/services/mcp.py`
next to `app/services/salesforce.py`? That conflates data-layer code with
consumer-facing code.

## Decision

Reorganize into three top-level packages:

- `app/salesforce/` — data layer. Knows how to talk to Salesforce.
- `app/intelligence/` — domain layer (reserved; populated Weeks 5-9). Metadata
  graph, code parsers, Claude orchestration.
- `app/interfaces/` — consumer-facing layer. REST API now, MCP server later,
  CLI later.

Each layer depends only on layers below it. Interfaces depend on intelligence
and salesforce; intelligence depends on salesforce; salesforce depends on nothing
internal.

## Alternatives considered

**Flat folders by file type** (`models/`, `services/`, `routes/`)
- Pros: simple, conventional FastAPI tutorial structure
- Cons: doesn't scale past one consumer; no place for graph/parser code

**Feature folders** (`accounts/`, `apex/`, `flows/` each with their own models +
routes + clients)
- Pros: locality — everything about accounts in one place
- Cons: cuts across the natural seam of "data layer vs consumer layer";
  shared infrastructure (auth, HTTP client) becomes awkward

## Trade-offs

- ✅ Clear seams for adding new consumers (MCP, VS Code) without disturbing
  existing code
- ✅ Forces honest thinking about what's domain logic vs delivery mechanism
- ❌ Three levels of nesting before reaching actual code files
- ❌ Beginner-confusing: "why are my routes 4 directories deep"

## Consequences

- Tooling API client (Week 5) goes in `app/salesforce/tooling_api.py`, not in
  a new top-level module
- MCP server (Week 11) goes in `app/interfaces/mcp_server/`, parallel to
  `app/interfaces/rest_api/`
- `app/intelligence/` stays empty until Week 5 — that's fine, the placeholder
  documents intent