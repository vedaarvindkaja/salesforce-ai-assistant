# Architecture Decision Records

This is the decision trail for the Salesforce metadata-graph platform — the
choices with real trade-offs and long-term consequences, recorded as they were
made.

An entry earns a place here only if it passed the **"is this ADR-worthy?"** test:
a genuine alternative was on the table, the trade-off mattered, and a future
reader would otherwise ask *"why was it done this way?"* Routine extensions
(adding a second body-bearing metadata type, wrapping a tested query engine in a
tool) were deliberately kept **out** — padding the log with trivia would blunt
the signal.

## Where the records live

- **Standalone files** (`ADR-NNN-*.md` in this folder): ADR-001–003 and
  ADR-018–019.
- **Inline in the development journal** ([`NOTES.md`](../../NOTES.md), search
  `ADR-0NN`): ADR-004–017. These were recorded in the journal as they were
  decided, before the standalone-file convention resumed at 018.

Promoting the journal-recorded ADRs (004–017) into standalone files is a tracked
pre-launch task — **trigger: before the public repo link (Week 15), or if a
reviewer trips on it.** Until then this index is the single entry point to all of
them.

All ADRs are **Accepted** unless an annotation says otherwise. Italic notes mark
records that a later decision *superseded* or *refined*.

## Index

| ADR | Decision | Where |
|-----|----------|-------|
| [ADR-001](ADR-001-layered-architecture.md) | Layered architecture — `salesforce` / `intelligence` / `interfaces`; each layer depends only downward. | file |
| [ADR-002](ADR-002-external-client-app.md) | OAuth via an External Client App, not a classic Connected App (Salesforce's forward path). | file |
| [ADR-003](ADR-003-layered-http-client.md) | Split `SalesforceClient` into a shared HTTP layer + per-API layer (composition over inheritance). | file |
| [ADR-004](../../NOTES.md) | SQLite **per-operation** connections for the cache — the deliberate opposite of ADR-003 (a stateless resource needs no persistent connection). | NOTES |
| [ADR-005](../../NOTES.md) | Cache partition key = org `instance_url` via `load_tokens()` (a key must be explicit, never best-effort). | NOTES |
| [ADR-006](../../NOTES.md) | String-scan before AST parse for reference analysis v1 (ship the useful 80% with named limits). *Refined: the Week-7 Apex parser added CALLS/USES_OBJECT alongside — it did not replace the string-scan, which still backs REFERENCES edges.* | NOTES |
| [ADR-007](../../NOTES.md) | Case-insensitive reference matching — Apex is case-insensitive, so it is *correct*, not merely convenient. | NOTES |
| [ADR-008](../../NOTES.md) | `MetadataGraph` wraps networkx rather than subclassing or using it raw. *Superseded in part by ADR-011 — the DiGraph choice here became a MultiDiGraph.* | NOTES |
| [ADR-009](../../NOTES.md) | REFERENCES edges reuse the `ReferenceAnalyzer` (O(N²) accepted at this scale). *Refined: Week-6 profiling traced the cost to per-op SQLite I/O churn, not regex.* | NOTES |
| [ADR-010](../../NOTES.md) | Derive Object nodes from parser output, not the Tooling API; field-grain deferred (the FIELD-node trigger). | NOTES |
| [ADR-011](../../NOTES.md) | `MultiDiGraph` — parallel typed edges (REFERENCES + CALLS between the same pair) coexist without data loss. *Supersedes the DiGraph implied by ADR-008.* | NOTES |
| [ADR-012](../../NOTES.md) | Flow extraction via Metadata API `readMetadata` SOAP (not Tooling `Flow.Metadata`, not `retrieve()`). | NOTES |
| [ADR-013](../../NOTES.md) | Shared name resolution + edge labels in `graph/naming.py` (single source, so the CLI and Claude describe an edge identically). | NOTES |
| [ADR-014](../../NOTES.md) | Tool-pull context strategy (Option B) over pre-loaded/compressed context; tool-call observability to stderr. *Still tool-pull; revival trigger unmet.* | NOTES |
| [ADR-015](../../NOTES.md) | Shared graph loader `bootstrap.load_graph` — one pure, timing-agnostic loader; CLI / MCP / REST each own their lifecycle at the edge. | NOTES |
| [ADR-016](../../NOTES.md) | REST capability surface — explicit typed routes over one parametrized route. *Four at decision time; now **five** (debug-log-analysis, Week 12) + read-only `/graph`.* | NOTES |
| [ADR-017](../../NOTES.md) | Debug-log capability takes a log **reference**, parsed/correlated server-side; Claude receives structured prose, never the raw log. | NOTES |
| [ADR-018](ADR-018-renderer-seam.md) | Renderer seam — dependency inversion at the extension's display boundary (OutputChannel + webview behind one `chunk`/`done`/`error` interface). | file |
| [ADR-019](ADR-019-hand-rolled-rest-client.md) | Hand-rolled REST client over OpenAPI codegen (incl. fetch-streaming over EventSource). *Revisit trigger: ~10 request models.* | file |

## Reading the trail

The supersessions and refinements are the point, not noise: ADR-008 → ADR-011
(DiGraph proved lossy under parallel typed edges and was replaced) and the
ADR-003 ↔ ADR-004 contrast (persistent connection where state must survive,
per-operation where it need not) are the two clearest examples of decisions
that were revisited with evidence rather than left to ossify.
