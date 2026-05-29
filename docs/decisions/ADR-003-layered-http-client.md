# ADR-003: Split SalesforceClient into HTTP layer + API layer

**Status:** Accepted
**Date:** 2026-05-29 (Week 5, Day 1)
**Decided by:** Veda Arvind

## Context

Week 4 produced `SalesforceClient` in `app/salesforce/rest_api.py`. It does two
jobs:

1. **HTTP lifecycle** — owns httpx client, attaches Bearer headers, refreshes
   on 401, retries, persists rotated tokens.
2. **REST API operations** — builds `/services/data/v60.0/query` URLs, parses
   `SalesforceQueryResponse`.

Week 5 introduces a Tooling API client. Tooling needs job 1 verbatim but a
different job 2 (different URL paths, different response shapes). Weeks 7-9
will add more consumers: Apex parser, deployment impact analyzer, Claude tool
use. By Week 11 there are 3+ consumers of the HTTP lifecycle.

## Decision

Extract `SalesforceHTTPClient` from `SalesforceClient`. It owns the httpx
client, token state, and refresh-on-401 logic, and exposes a `request(method,
path, ...)` method. Rename the existing `SalesforceClient` to `RestAPIClient`
and have it hold a `SalesforceHTTPClient` instance (composition). The new
`ToolingAPIClient` (Week 5 Day 2) holds the same `SalesforceHTTPClient`
instance.

Both API clients receive the HTTP client via constructor — they don't create
their own.

## Alternatives considered

**Subclass (Option A)** — `ToolingAPIClient(SalesforceClient)` overrides URL paths
- Pros: minimal change to Week 4 code
- Cons: wrong "is-a" relationship (Tooling is a sibling of REST, not a kind
  of REST); Pythonic style prefers composition over inheritance; subclass
  inherits methods like `query()` that don't apply

**Composition without refactor (Option B)** — `ToolingAPIClient` holds a
`SalesforceClient` and reaches into it for HTTP calls
- Pros: no refactor needed
- Cons: requires exposing internal methods on `SalesforceClient`; couples
  Tooling client to REST client's incidental shape; circular ownership
  feels wrong

**Refactor to shared HTTP client (Option C — chosen)**
- Pros: clean separation; each consumer gets the same auth infrastructure;
  matches the layered architecture from ADR-001
- Cons: refactor cost; risk of breaking Week 4's tests if done sloppily

## Trade-offs

- ✅ Future consumers (Metadata API, bulk API, etc.) add zero auth code
- ✅ Tests for the HTTP layer (refresh, retry, rotation) live in one place
- ✅ Mock + real swap stays at the HTTP layer; API layer is shared
- ❌ One more level of indirection — `RestAPIClient` → `SalesforceHTTPClient`
  → `httpx.AsyncClient`
- ❌ Refactor touches `dependencies.py`, `main.py` lifespan, and 5 tests

## Consequences

- `SalesforceClient` becomes `RestAPIClient` (rename)
- New file: `app/salesforce/http_client.py` with `SalesforceHTTPClient`
- `app/salesforce/rest_api.py` shrinks to just the REST-specific methods
- New file Week 5 Day 2: `app/salesforce/tooling_api.py` with `ToolingAPIClient`
- Mock client (`MockSalesforceClient`) stays as-is for now — it doesn't need
  the layered structure because it doesn't do real HTTP. Phase 2 may revisit
  this for symmetry.

### Mock client asymmetry (explicit)

`MockSalesforceClient` stays monolithic — it does not get split into a mock
HTTP client + mock REST client. Reasoning:

- The mock does not perform HTTP, so a "mock HTTP layer" would be ceremony
  without function
- Duck typing means consumers don't care about internal class structure;
  asymmetric mock + symmetric real is fine as long as each side is
  internally coherent
- Day 6 of Week 5 will add `MockToolingAPIClient` as a parallel monolithic
  mock (not as part of a mock HTTP layer)

Revisit in Phase 2 if multi-tenant testing requires modeling the HTTP
lifecycle (token refresh races, per-user session state, etc.).

## Failure mode considered

The refactor is mechanical but not trivial — it touches the HTTP client,
both API client shapes, the FastAPI lifespan, dependency injection, and
five tests. Two failure modes to watch for:

**Scope discovery.** If during the refactor we find that `SalesforceClient`
has hidden coupling we didn't anticipate (e.g., test fixtures reaching into
private attributes, dependency injection assuming a specific shape), the
right response is to slow down and address it cleanly — not to revert to
composition-without-refactor. Quality of foundation matters more than
finishing Day 1 today.

**Genuine ambiguity.** If we hit a design question the ADR doesn't answer
(e.g., "should the HTTP client expose response objects or just response
bodies?"), pause and decide explicitly rather than picking the fastest
path. Add the sub-decision to this ADR or write a new one.

What we explicitly reject: timeboxing the refactor and falling back to a
lesser design because we ran out of clock. Phase 1 builds the foundation
for Phase 2+; every shortcut now compounds across future consumers
(Metadata API, MCP server, VS Code extension). A right-sized refactor
today saves a much larger one later.

If the refactor genuinely requires more than one Day 1 session — for
example, it surfaces that `MockSalesforceClient` should also be split
for symmetry — that's fine. Day 1 becomes Day 1-2, Tooling client work
shifts to Day 3+. The 20-hour Week 5 budget has slack for this.