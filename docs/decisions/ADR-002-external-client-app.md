# ADR-002: External Client App over classic Connected App

**Status:** Accepted
**Date:** 2026-05-27 (Week 4, Day 3)
**Decided by:** Veda Arvind

## Context

Week 4 Day 3 needed a Salesforce Connected App for OAuth 2.0 Web Server Flow.
The Salesforce documentation and most third-party tutorials reference classic
Connected Apps. In newer org versions (mid-2026), the Setup UI no longer
exposes "New Connected App" — only "New External Client App."

External Client Apps were initially launched with limitations on which OAuth
flows they supported (Web Server Flow was supported; username-password was
not). As of May 2026, External Client Apps support Web Server Flow + PKCE +
Refresh Token Rotation, which is the full feature set we need.

## Decision

Use External Client App. Configure it for OAuth 2.0 Web Server Flow with
PKCE required and Refresh Token Rotation enabled.

## Alternatives considered

**Classic Connected App**
- Pros: more documentation, more tutorials, more familiar
- Cons: Salesforce is phasing it out; using a deprecated path on a portfolio
  project signals stale Salesforce knowledge

**JWT Bearer Flow**
- Pros: no user interaction; server-to-server
- Cons: requires uploading a certificate to Salesforce; designed for headless
  integrations, not interactive dev tools; would prevent the "real user logs in"
  demo

## Trade-offs

- ✅ Forward-compatible with Salesforce's direction
- ✅ PKCE is mandatory anyway; might as well use the recommended app type
- ❌ Less third-party documentation; some Stack Overflow answers don't apply
- ❌ 10-minute propagation wait after creating the app (vs ~instant for
  classic Connected Apps) — surprised me on Day 3

## Consequences

- README and setup docs specify External Client App, not Connected App
- Phase 2 multi-tenant will use the same app type; no migration needed
- If we ever need a flow External Client Apps don't support (rare), we'd have
  to revisit