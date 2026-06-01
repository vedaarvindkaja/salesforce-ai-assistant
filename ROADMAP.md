# Phase 1 Roadmap — AI Metadata Graph for Salesforce Developers

> A focused 15-week execution plan for building a developer-focused Salesforce
> intelligence platform. Open-core strategy. Portfolio-ready by Week 15.

**Document version:** 1.0
**Created:** Week 3 completion (Week 4 starting point)
**Builder:** Veda Arvind
**Target ship date:** Week 15 (public launch)
**Time commitment:** 15-20 hours/week

---

## Table of contents

1. [Strategic context](#1-strategic-context)
2. [What we're building](#2-what-were-building)
3. [Architecture overview](#3-architecture-overview)
4. [Week-by-week roadmap](#4-week-by-week-roadmap)
5. [What carries forward from Weeks 1-3](#5-what-carries-forward-from-weeks-1-3)
6. [Definition of Done — Phase 1](#6-definition-of-done--phase-1)
7. [Risks and mitigations](#7-risks-and-mitigations)
8. [Phase 2+ ideas (deferred)](#8-phase-2-ideas-deferred)
9. [Reference materials](#9-reference-materials)

---

## 1. Strategic context

### Vision (long term)
AI-native Salesforce intelligence platform serving developers, admins, sales,
support, and managers through one shared intelligence core. Cross-system context
fusion across Salesforce, Slack, JIRA, Email, Deployments.

### Phase 1 scope (this document)
**Developer persona only.** Build the core "metadata graph" intelligence layer
that becomes the foundation for everything in Phase 2+. Ship a usable product
for Salesforce developers within 15 weeks.

### Why developer-first
1. Strongest differentiation — Salesforce's official AI tools target business users
2. Easier to evaluate quality — developers can immediately tell when output is wrong
3. Your 10 years of Salesforce dev experience is direct domain advantage
4. Smaller, focused scope = faster to ship
5. Better technical portfolio narrative

### Strategic constraints
- **Portfolio-first.** Currently job-hunting; project must be demoable by Week 15.
- **Solo builder.** 15-20 hours/week, evenings and weekends.
- **Open core.** Open-source MCP server + metadata extractor; proprietary advanced features.
- **No multi-tenant in Phase 1.** Runs locally for a single developer's orgs.
- **No cross-system integration yet.** Salesforce-only, deep and excellent.

### Strategic decisions made
| Decision | Choice | Reason |
|---|---|---|
| Persona | Developers only | Differentiation + your domain expertise |
| Timeline | 15 weeks portfolio-first | Active job hunt requires demoable artifact |
| Strategy | Open core | Community credibility + business potential later |
| Auth | OAuth 2.0 Web Server Flow | What real dev tools use; not username-password |
| Architecture | Layered (core → modules → interfaces) | Scalable for Phase 2+ |
| Multi-persona | Deferred to Phase 2 | Avoid scope creep |

---

## 2. What we're building

### Product positioning (Phase 1)

> **"The AI metadata graph for Salesforce developers. Ask questions about your
> org's structure, dependencies, Apex, and metadata in natural language.
> Open-source MCP server + VS Code extension."**

### Five MVP capabilities

These are the only features Phase 1 ships. Quality over breadth.

#### Capability 1 — Metadata Q&A
Ask natural language questions about org structure and dependencies.

Example queries:
- *"What objects depend on Account.CustomField__c?"*
- *"Which profiles have edit access to Opportunity.Amount?"*
- *"Show me all custom fields on Contact created in the last 30 days"*

Returns: Structured answer with traced dependencies.

#### Capability 2 — Apex explanation and refactoring
Paste in Apex code, get intelligent analysis.

Example queries:
- *"Explain this trigger"*
- *"Refactor this for bulk safety"*
- *"What records could this query return in production?"*

Returns: Explanation + suggested improvements with full metadata context.

#### Capability 3 — SOQL generation with metadata awareness
Natural language → SOQL that respects org-specific schema.

Example queries:
- *"Find Opportunities created last quarter for accounts with no contacts"*
- *"List all custom fields on Account that contain 'priority' in the name"*

Returns: Valid SOQL that uses actual field names from your org.

#### Capability 4 — Deployment impact analysis
"If I deploy this change set, what could break?"

Example workflow:
1. User provides change set or list of components
2. System traces all dependencies via metadata graph
3. Identifies affected Apex, Flows, validation rules, etc.
4. Returns risk assessment

#### Capability 5 — Debug log analysis
Paste debug log → get root cause analysis.

Example workflow:
1. User pastes a debug log
2. System parses, identifies errors
3. Cross-references against metadata graph + Apex source
4. Returns root cause with code context

### Out of scope for Phase 1 (deferred)

❌ Sales/Service/Admin features (Phase 2)
❌ Cross-system context (Slack, JIRA, etc.) (Phase 3)
❌ Multi-tenant SaaS (Phase 2)
❌ Web app for non-developers (Phase 2)
❌ Vector memory / RAG (Phase 2)
❌ Multi-agent orchestration (Phase 4)
❌ Mobile/Slack interfaces (Phase 3+)
❌ Real-time metadata streaming (Phase 2)

---

## 3. Architecture overview

### Layered architecture

```
┌────────────────────────────────────────────────────────────────┐
│                    USER-FACING INTERFACES                       │
├────────────────────────────────────────────────────────────────┤
│  VS Code Ext  │  MCP Server (stdio)  │  REST API  │  CLI       │
│  (TypeScript) │  (for Cursor/Claude) │  (FastAPI) │  (testing) │
└──────┬─────────────┬────────────────────┬───────────┬──────────┘
       │             │                    │           │
       └─────────────┴────────────────────┴───────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────────────┐
│              ORCHESTRATION LAYER (Python)                       │
│  Receives requests, builds context, calls Claude with tools     │
└──────────────────────────┬─────────────────────────────────────┘
                           │
            ┌──────────────┼──────────────┐
            ▼              ▼              ▼
┌────────────────┐ ┌──────────────┐ ┌──────────────────────┐
│ METADATA GRAPH │ │ CODE INTEL   │ │ CONTEXT RETRIEVAL    │
│ Objects/Fields │ │ Apex parser  │ │ Token-efficient      │
│ Relationships  │ │ Flow XML     │ │ context building     │
│ Dependencies   │ │ Triggers     │ │ for Claude           │
└───────┬────────┘ └──────┬───────┘ └─────────┬────────────┘
        │                 │                   │
        └─────────────────┼───────────────────┘
                          │
                          ▼
┌────────────────────────────────────────────────────────────────┐
│              SALESFORCE DATA LAYER                              │
│  Metadata API + Tooling API + REST API                          │
│  OAuth 2.0 Web Server Flow                                      │
│  SQLite local cache, 24h TTL                                    │
└─────────────────────────────────────────────────────────────────┘

                  ┌──────────────────────┐
                  │     CLAUDE API       │
                  │  (called from        │
                  │   orchestration)     │
                  └──────────────────────┘
```

### Target folder structure (end of Phase 1)

```
salesforce-ai-assistant/
│
├── backend/                          # Python backend
│   ├── app/
│   │   ├── salesforce/               # Salesforce data layer
│   │   │   ├── auth.py               # OAuth 2.0 flow
│   │   │   ├── metadata_api.py       # Metadata API client
│   │   │   ├── tooling_api.py        # Tooling API client
│   │   │   ├── rest_api.py           # REST API (existing, refactored)
│   │   │   └── mocks/                # All mocks live here
│   │   │       ├── metadata_mock.py
│   │   │       ├── tooling_mock.py
│   │   │       └── rest_mock.py
│   │   │
│   │   ├── intelligence/             # The core moat
│   │   │   ├── graph/                # Metadata graph
│   │   │   │   ├── extractor.py
│   │   │   │   ├── builder.py
│   │   │   │   ├── query.py
│   │   │   │   └── storage.py
│   │   │   ├── code/                 # Apex/Flow analysis
│   │   │   │   ├── apex_parser.py
│   │   │   │   ├── flow_analyzer.py
│   │   │   │   └── dependency_tracker.py
│   │   │   ├── context/              # Context window builder
│   │   │   │   ├── retrieval.py
│   │   │   │   ├── compression.py
│   │   │   │   └── templates.py
│   │   │   └── orchestration/        # Claude integration
│   │   │       ├── claude_client.py
│   │   │       ├── tool_definitions.py
│   │   │       └── capabilities.py   # The 5 capabilities
│   │   │
│   │   ├── interfaces/               # Multiple ways to consume
│   │   │   ├── mcp_server/           # MCP protocol
│   │   │   ├── rest_api/             # FastAPI endpoints
│   │   │   │   ├── main.py
│   │   │   │   ├── dependencies.py
│   │   │   │   └── routes/
│   │   │   └── cli/                  # CLI for testing
│   │   │
│   │   └── models/                   # Pydantic models
│   │       ├── salesforce.py
│   │       ├── graph.py
│   │       └── intelligence.py
│   │
│   ├── tests/
│   │   ├── unit/
│   │   ├── integration/
│   │   └── evals/                    # Evaluation harness
│   │
│   └── requirements.txt
│
├── vscode-extension/                 # TypeScript extension (Week 13)
│   ├── src/
│   ├── package.json
│   └── README.md
│
├── evals/                            # Evaluation test cases
│   ├── test_cases/
│   │   ├── metadata_qa/
│   │   ├── apex_explanation/
│   │   ├── soql_generation/
│   │   ├── deployment_impact/
│   │   └── debug_log_analysis/
│   ├── runners/
│   └── reports/
│
├── docs/                             # Documentation
│   ├── architecture/
│   ├── api/
│   ├── screenshots/
│   └── tutorials/
│
├── README.md                         # Project overview
├── NOTES.md                          # Development journal
├── CHANGELOG.md                      # Track major changes
├── ROADMAP.md                        # This document
├── LICENSE                           # MIT for open-source parts
└── .gitignore
```

### Tech stack

**Backend (Python)**
- Python 3.11+
- FastAPI (async web framework)
- Pydantic v2 (data validation)
- httpx (async HTTP client)
- simple-salesforce or aiohttp (Salesforce REST)
- networkx (graph operations)
- antlr4-python3-runtime or custom parser (Apex parsing)
- aiosqlite (local cache)
- pytest + pytest-asyncio (testing)
- anthropic (Claude API client)
- mcp (MCP protocol Python SDK)

**Frontend (TypeScript)**
- VS Code Extension API
- TypeScript 5+
- esbuild (bundling)

**Data**
- SQLite (local metadata cache)
- JSON files (for graph snapshots during dev)

**AI**
- Claude API (Sonnet 4.6 for most queries; Opus 4.7 for complex reasoning)
- Tool use for structured outputs
- MCP protocol for protocol-level integration

---

## 4. Week-by-week roadmap

### Phase 0 — Foundation refresh

#### Week 4 — Architecture pivot + OAuth (15 hours)

**Goal:** Reorient the existing codebase toward the new vision and fix auth properly.

**Day 1-2 (4 hours)** — Folder structure refactor
- Reorganize existing files into new structure (salesforce/, intelligence/, interfaces/)
- Move `services/salesforce.py` → `salesforce/rest_api.py`
- Move `services/salesforce_mock.py` → `salesforce/mocks/rest_mock.py`
- Move `routes/accounts.py` → `interfaces/rest_api/routes/accounts.py`
- Update all imports
- Verify 14 tests still pass

**Day 3-4 (5 hours)** — OAuth 2.0 setup
- Create classic Connected App in Salesforce (not External Client App)
- Implement OAuth 2.0 Web Server Flow
- Build `salesforce/auth.py` with token management
- Refresh token logic for long-lived sessions

**Day 5 (3 hours)** — Wire OAuth to existing endpoints
- Update lifespan in main.py to use real auth
- Test existing endpoints with real Salesforce
- Update mock auth to match new interface

**Day 6 (2 hours)** — Documentation
- Update README with new vision and positioning
- Add CHANGELOG.md entry documenting the pivot
- Update NOTES.md with Week 4 retrospective

**Day 7 (1 hour)** — Commit + reflect
- Final commit and push
- Plan Week 5

**Deliverables:**
- ✅ Existing endpoints work with real Salesforce OAuth
- ✅ Folder structure aligned with new vision
- ✅ All 14 existing tests passing
- ✅ Documentation reflects new direction
- ✅ Connected App working in Salesforce

---

### Phase 1A — Metadata graph (the moat)

#### Week 5 — Metadata extraction + first intelligence query (20 hours)

**Goal:** Extract Apex from a real org into a local cache, then ship the
first query that produces an *insight* — not just stored data. (Plan
pivoted from broad metadata extraction to a working vertical slice:
extract → cache → analyze → answer.)

**Day 1-2 (6 hours)** — Tooling API client ✅
- `salesforce/tooling_api.py` with 6 typed query methods
- Layered HTTP client refactor (ADR-003)
- Real-org verified, 29 tests passing

**Day 3 (4 hours)** — Storage layer ✅
- `intelligence/graph/storage.py` — SQLite flat extraction cache (Option A)
- Keyed on (org_key, metadata_type, record_id); upsert semantics
- Per-operation connection lifecycle (ADR-004)
- 6 hermetic tests

**Day 4 (6 hours)** — First intelligence query ✅
- `scripts/extract_to_cache.py` — real Apex → cache; org_key = instance_url (ADR-005)
- `intelligence/analyzer.py` — reference analyzer (insight A: "what references X?")
- String-scan before AST parse (ADR-006); AST parser deferred to Week 7
- 5 hermetic tests; verified against real org (42 classes)

**Day 5 (4 hours)** — Deepen the slice ✅
- Extended reference analyzer to Apex triggers (multi-type scan)
- Fixed case-sensitivity bug — Apex is case-insensitive (ADR-007)
- Added scripts/list_cached.py cache inspector
- ValidationRule expansion: OUT of Week 5 scope (breadth, not depth) — parked
- 44 tests passing; verified against real org (42 classes + 1 trigger)

**Deliverables:**
- ✅ Tooling API client working with real Salesforce
- ✅ SQLite flat extraction cache (MetadataCache) — SQLite only, no JSON output
- ✅ Reference analyzer producing ranked impact-analysis answers (insight A)
- ✅ Real-org extraction verified (42 Apex classes cached + scanned)
- ✅ 44 tests passing (hermetic)
- ⬜ Metadata API (SOAP) client — NOT built; Tooling API covered Phase 1 needs
- ⬜ Mock org generation — NOT built; hermetic synthetic fixtures used instead

**ADRs this week:** ADR-004 (connection lifecycle), ADR-005 (cache partition
key), ADR-006 (string-scan before AST), ADR-007 (case-insensitive matching).
Full reasoning in NOTES.md.

#### Week 6 — Graph construction (20 hours) ✅ — completed in ~16h (a day early)

**Goal:** Convert extracted metadata into a queryable graph.

Plan reconciled against reality at week start (as in Week 5): the original
plan assumed a cache containing Objects, Fields, Flows, and ValidationRules.
The real cache holds only ApexClass + ApexTrigger, so node/edge scope was
narrowed to what could actually be populated and tested. Field/relationship
edges moved to Week 7 (they depend on the Apex parser). Day order also shifted
— query API (planned Day 5) was pulled forward once the builder landed early.

**Day 1 (Day 1-2 budget)** — Graph data model ✅
- `intelligence/graph/models.py` — NodeType/EdgeType enums, Node/Edge Pydantic
  models, MetadataGraph (typed wrapper over networkx.DiGraph), GraphStats
- Scoped to 2 populatable node types (ApexClass, ApexTrigger) + REFERENCES
  edge; other 7 node / 6 edge types stubbed as enum values for Week 7-8
- ADR-008 (MetadataGraph wraps networkx, not subclass/raw)
- 16 hermetic tests

**Day 2 (Day 3-4 budget)** — Graph builder ✅
- `intelligence/graph/builder.py` — cache → MetadataGraph. Nodes per record;
  REFERENCES edges built by reusing the reference analyzer (ADR-009),
  self-edges excluded
- `scripts/verify_graph.py` — real-org build report
- Real-org verified: 43 nodes (42 classes + 1 trigger), 87 edges, 268 ms
  (well under the <5s / 1000-item target). Hubs = framework core
  (TriggerActionFlow, TriggerBase, MetadataTriggerHandler)
- 11 hermetic tests
- DEFERRED to Week 7: field references (formula fields, validation rules),
  master-detail/lookup edges — no Object/Field data in cache yet. Builder is
  type-agnostic; Week 7 adds node types without touching traversal/query code

**Day 3 (Day 5 work, pulled forward)** — Graph query API ✅
- `intelligence/graph/query.py` — QueryEngine (synchronous; graph is in-memory)
- API: what_depends_on, what_does_it_depend_on (both direct + --transitive via
  networkx ancestors/descendants), find_path (returns edges w/ line numbers),
  find_by_name (case-insensitive), find_orphaned, find_never_referenced (NEW —
  in==0/out>0, added from Day 2's real-org finding)
- 18 hermetic tests

**Day 6** — CLI ✅
- `app/interfaces/cli.py` (ADR-001 interfaces/ layer — product surface, not
  scripts/ plumbing). argparse; 7 commands; pure-function handlers
- Real-org demo verified: depends-on/dependencies/path/find/orphans/
  never-referenced/stats all answer against the live org in <0.5s
- 23 tests

**Day 7 (1 hour)** — Commit, push, ROADMAP update, refresh Project knowledge,
plan Week 7

**Deliverables:**
- ✅ Working graph of metadata relationships (43 nodes, 87 edges, real org)
- ✅ Query API for dependency traversal (6 queries, direct + transitive)
- ✅ CLI command: `python -m app.interfaces.cli depends-on TriggerActionFlow`
  (and 6 more) — replaces the planned `intelligence.cli query "..."` form
- ✅ Performance benchmark documented (268 ms; profiled as I/O-bound, not regex)
- ⬜ Graph snapshot persistence + incremental refresh — PARKED. Option A (rebuild
  from cache on startup, ~0.3s) chosen; persistence (Option B) deferred to
  Phase 2 unless build time becomes a problem
- ⬜ REST `/graph/` route — PARKED to Week 7+ (add when the VS Code consumer
  exists; avoids a premature graph-lifecycle decision)

**ADRs this week:** ADR-008 (MetadataGraph wraps networkx), ADR-009 (edges via
analyzer reuse, O(N²) accepted at scale). Full reasoning in NOTES.md.

**Test count:** 44 → 112 (+68 across models/builder/query/cli).

#### Week 7 — Apex parser, code intelligence, field + Flow graph (20 hours) ✅ — completed, ~18h

**Goal (as planned):** Add Apex source understanding to the graph; add
Object/Field nodes plus field/relationship edges deferred from Week 6.

**What actually shipped (reconciled):** Apex parser, Object nodes, code edges,
AND the full Flow vertical slice (planned as a Day-5 trim candidate, but built
in full because time allowed). Field-level nodes were consciously NOT built —
the derive-vs-extract decision (ADR-010) settled on deriving Object nodes from
references, and field nodes proved to be Phase-2-shaped (field-node explosion,
authoritative extraction). The field-impact headline was delivered at the
OBJECT level (`impact Opportunity`), which serves the demo without the field-node
cost. Flow analysis became the week's marquee feature instead.

**Day 1** — Test-class classifier ✅
- `is_test` node attribute (name ends Test/Tests OR body has @isTest); module-
  level function. `--no-tests` filter on never-referenced. Real org: 15 never-
  referenced → 3 production once tests excluded. 106 tests.

**Day 2** — Apex pattern parser ✅
- `intelligence/code/apex_parser.py` — SOQL/DML/field-ref/class-call extraction.
  Three real-org fixes: comment stripping, PascalCase class-ref filter, DML
  `new` skip. 148 tests.
- DECISION: derive-vs-extract settled → Option B (derive). ADR-010.

**Day 3** — Object nodes + CALLS/USES_OBJECT edges; MultiDiGraph migration ✅
- Pass 3 `_add_parser_edges`: derived Object nodes (obj:<name>, source=derived),
  CALLS (Apex→Apex), USES_OBJECT (Apex→Object). Noise filter.
- DECISION: DiGraph → MultiDiGraph after a failing Week-6 test caught silent
  edge loss (a CALLS edge overwrote a REFERENCES edge between the same pair).
  ADR-011 — the week's strongest interview story.
- Real org: 50 nodes, 166 edges. REFERENCES held at 87 (proof of no loss). 156 tests.

**Day 4** — impact command + incoming_edges ✅
- `query.py`: `incoming_edges()` returns Edge objects (first query to return
  edges not nodes) so impact can show HOW a dependency exists.
- `cli.py`: `impact` command. Real org: `impact TriggerBase` shows 30 refs with
  method-level precision (parallel CALLS + REFERENCES edges, ADR-011 payoff). 169 tests.

**Day 5** — Flow vertical slice ✅ (planned as trim candidate; built in full)
- `salesforce/metadata_api.py` — Metadata SOAP client, readMetadata(Flow),
  OAuth token as sessionId, synchronous (not retrieve/poll/zip). ADR-012.
- `intelligence/code/flow_parser.py` — Flow XML → triggering object, apex
  actions, subflows. actionType=apex filter; xsi-namespace fix.
- `builder.py` pass 4 — Flow nodes + Flow→Object/Apex/Flow edges, reusing
  USES_OBJECT/CALLS so impact works for free.
- `cli.py` — via-driven impact labels (Flow action / subflow / Flow trigger).
- Real org: 57 nodes (43 Apex + 8 Object + 6 Flow), 172 edges. THE PAYOFF:
  `impact PricingFlowAction` → the Flow that invokes it, explaining its Week-6
  "never-referenced" status. Sole orphan (Approval Orchestrator) confirmed a
  correct finding, not a bug. 201 tests.

**Deliverables (honest checks):**
- ✅ Test-vs-production classification + query filtering
- ✅ Apex pattern parser (SOQL/DML/field/class refs)
- ✅ Object nodes + Apex→Object/Apex edges (MultiDiGraph, ADR-011)
- ✅ Headline demo at OBJECT level: `impact Opportunity` traces the classes that
  query it; `impact PricingFlowAction` shows the Flow that invokes it
- ✅ Flow analyzer — FULL slice (extraction + parser + edges), exceeded plan
- ◻ FIELD nodes/edges — consciously NOT built; derive decision (ADR-010) kept to
  objects; field-level is Phase-2-shaped. Field-impact served at object grain
- ◻ Dependency tracker — folded into query.py (incoming_edges + impact), no
  separate module, as the Day-6 note anticipated
- ⬜ Flow record-operation edges (recordLookups/Creates/Updates) — deferred to
  Week 8; the Flow equivalent of Apex SOQL/DML extraction
- ⬜ Master-detail/lookup + validation-rule edges — still deferred (need
  CustomField/ValidationRule extraction)
- ⬜ Full ANTLR AST — Phase 2

**ADRs this week:** ADR-010 (derive Object nodes), ADR-011 (MultiDiGraph),
ADR-012 (Flow via readMetadata SOAP). Full reasoning in NOTES.md.

**Test count:** 112 → 201 (+89 across classifier/parser/builder/query/cli/
metadata_api/flow_parser).

---

### Phase 1B — Claude integration

#### Week 8 — Orchestration layer (15 hours)

#### Week 8 — Orchestration layer (15 hours)

#### Week 8 — Orchestration layer (15 hours) ✅ — completed, ~13h

**Goal (as planned):** Make the graph queryable through Claude — Claude client,
tool definitions, context builder, first end-to-end example.

**What actually shipped (reconciled):** All of it, plus the week reshaped once
the Day-1 reconciliation confirmed the tools were mostly thin wrappers over the
already-built QueryEngine. The freed time went where the plan under-budgeted:
a shared naming module (so CLI and tools describe edges identically) and a
proper architectural decision on context strategy (tool-pull vs pre-loaded).
The planned "context builder + compression" became a thin tool-pull system-
prompt builder; retrieval/compression machinery was deliberately deferred with
the pre-loaded model (Option B). The graph was richer than the original Week-8
assumption (Apex + Object + Flow already live from Week 7), so orchestration
reasoned over a real metadata graph from day one.

**Day 1** — Claude client ✅
- `intelligence/orchestration/claude_client.py` — async AsyncAnthropic wrapper;
  streaming via messages.stream(); agentic tool loop (stream → tool_use →
  dispatch concurrently → feed back → repeat); SessionUsage cost tracking;
  max_iterations guard. Model: claude-sonnet-4-6. Smoke-tested, not yet live.

**Day 2** — Shared naming module + graph-query tools ✅
- `intelligence/graph/naming.py` — resolve_one/fmt_node/edge labels extracted
  from cli.py so CLI and tools are single-sourced (ADR-013). cli.py refactored
  to import from it (behavior-preserving, aliases keep test paths).
- `intelligence/orchestration/tool_definitions.py` — 5 graph-query tools
  (find_dependencies, find_references_to, analyze_impact, find_by_name,
  graph_health) as thin async wrappers over QueryEngine; build_tools() factory
  → (schemas, handler_map). Lightly-structured text returns (tool-pull).
- 21 hermetic tests incl. a direction guard (dependencies/references can't be
  silently inverted).

**Day 3** — get_source content-retrieval tool ✅
- 6th tool: raw Apex Body (class/trigger, by record_id) or Flow XML (by
  DeveloperName, since Flow node ids are synthetic). Object → "no source"
  (derived, ADR-010). 12k-char truncation guardrail. cache/org_key now optional
  on build_tools (get_source only when present). One tool, not the planned two
  (asymmetry hidden behind one tool; tool-shape choice, not ADR-worthy).
- Tests 21 → 30. Live-verified: pulled real PricingFlowAction Apex + the full
  Opportunity_Sales_Orchestration_Flow XML through the tool.

**Day 5** — Tool-pull system-prompt builder ✅
- `intelligence/orchestration/system_prompt.py` — build_system_prompt(graph):
  role + live orientation (counts by node/edge type) + edge semantics + how-to-
  reason + a KNOWN LIMITATIONS block (no fields, object-grain only, Flow record
  operations not edged). Orientation, not data — every specific comes via a tool.
- ADR-014: tool-pull (Option A) over pre-loaded context (Option B). Structural
  consequence: no intelligence/context/ package; builder lives in orchestration/;
  retrieval.py/compression.py deferred to Option B with an explicit revival
  trigger. 8 tests.

**Day 6** — First end-to-end live call ✅
- `app/interfaces/ask_cli.py` — separate AI entry point (vs the deterministic
  cli.py): wires system prompt + tools + client; streams the answer; announces
  tool calls on stderr (ADR-014 observability); reports cost. 7 tests (parser +
  wrapper; live call verified manually).
- THE PAYOFF, narrated live: asked how PricingFlowAction is invoked despite
  looking never-referenced — Claude called find_references_to + find_dependencies
  + analyze_impact, found the Flow-action edge, and explained the metadata-wire-
  vs-code-call distinction (+ "deleting it breaks the Flow step silently at
  runtime"). The Week-7 thesis, answered by Claude from natural language.
  ~$0.024/query (Sonnet 4.6).

**Deliverables (honest checks):**
- ✅ Claude client — streaming, agentic tool loop, cost tracking
- ✅ Six tools (5 graph-query + get_source), all hermetically tested + live-verified
- ✅ Tool-pull system-prompt builder (orientation, not data)
- ✅ First working end-to-end example (ask CLI, real org + Claude)
- ✅ Cost tracking infrastructure — SessionUsage; ~$0.024/query measured
- ◻ "Context builder + compression" (planned Day 5) → became a thin system-prompt
  builder; retrieval/compression are Option-B machinery, deliberately deferred
- ⬜ Flow record-operation edges (carried from Week 7) — STILL parked, now with
  Day-3 real-org evidence (the orchestration flow's recordLookups on Opportunity
  is a real dependency the graph misses). Not a Week-8 blocker
- ⬜ Per-capability model routing (Sonnet vs Opus by task) — noted as Phase-2 idea
- ⬜ Pre-loaded context / names-index (Option B) — deferred; revival trigger in
  ADR-014. Day-6 showed one over-fetch (find_by_name warm-up on an exact name) —
  watching for a pattern across Week 9's capabilities

**ADRs this week:** ADR-013 (shared naming module — layering discipline),
ADR-014 (tool-pull orchestration over pre-loaded context). Full reasoning in NOTES.md.

**Test count:** 230 → 275 (+45 across naming/tools/get_source/system_prompt/ask).
Note: Week 7 close was recorded as 201, but the suite measured 230 at Week 8
start — the +29 predate this week's work; reconcile the running total via
`git log` (see Week 8 Day 2 NOTES).

---
## Week 9 — The MVP Capabilities (COMPLETE, rescoped 5→4)

### Outcome vs plan
Plan: build 5 developer-facing capabilities on the Week-8 orchestration layer.
Delivered: 4 capabilities, each proven live against the real org, each with a
clean portfolio entry-point wrapper. Capability 5 (debug log) PARKED by explicit
Day-1 decision — its honest version (parser + analyze_debug_log tool correlating
log events to graph nodes) is 2-3 days and doesn't fit Week-15 pressure; its
descoped version (paste-and-ask) doesn't exercise the metadata graph, so it's
portfolio-thin. Four graph-exercising capabilities > five where one is hollow.

### The real engineering (what the week actually was)
Not "wrote four system prompts." The week was: (1) a capability-routing
ARCHITECTURE (mode-dispatch) that made capabilities 2-4 cheap to add, and (2) a
deterministic-audit FINDING that surfaced where the AI over-narrates and what to
fix in Week 10. The capabilities were mostly prompt + 3-line wrapper over the
proven Week-8 layer — which is precisely what Day-1 triage predicted.

### What shipped, by day
- Day 1 — Mode-dispatch core. ask_cli.py gained --mode + CAPABILITY_REGISTRY
  (mode → (prompt_builder, tool_subset)); tool-subsetting owned by ask_cli, not
  build_tools (factory stays pure). 3 capability prompt builders (apex/soql/
  impact) on a shared _shared_orientation. Chose mode-dispatch over a
  capabilities.py abstraction (premature for a 3-tuple). Test reconciliation:
  275 baseline confirmed, 201→230 Week-7 gap explained via git log. 21 new tests.
- Day 2 — Capability 2 (Apex explanation/refactoring). Live-verified: graph-
  grounded explanation, flagged TriggerDispatcher as DEAD CODE (zero inbound
  refs — graph-only insight), self-discovered the org's 2nd trigger framework.
  ask_apex.py. Costliest capability ($0.088, source-heavy).
- Day 3 — Capability 3 (SOQL generation). Live-verified: per-field provenance
  held (grounded fields vs platform-prior fields vs verify-caveat fields).
  Grounding confirmed genuine (OpportunitySelector is real). ask_soql.py.
  Documented the field boundary (ADR-010): custom/queried fields grounded in
  source; standard fields rest on platform priors, NOT org verification.
- Day 4 — Capability 4 (deployment impact). Live-verified: all 5 structured
  sections, correct HIGH rating, Flow-vs-Apex insight reproduced generatively.
  get_source-free exclusion held. Cheapest non-qa capability ($0.0298).
  ask_impact.py.

### Entry-point wrappers (Day-1 amendment, delivered inline not deferred)
ask_apex.py / ask_soql.py / ask_impact.py — 3-line wrappers, main(default_mode=).
Built inline with each capability per the Week-8 review amendment (portfolio
insurance against Week-14 crunch), NOT deferred to Week 14. qa keeps the bare
ask_cli entry. Clean portfolio surface: `python -m app.interfaces.ask_impact "..."`.

### Capability 1 (Metadata Q&A) — status
Structurally complete since Week 8. One-shot Q&A for Phase 1. Multi-turn /
session state explicitly parked to Week 13+ (decided Day 1; do not half-build
session state mid-stream).

### THE FINDING (Day 4) — deterministic CLI audits the probabilistic AI
Ran cli.py as ground truth against impact-mode's PricingFlowAction analysis:
every NODE and EDGE Claude named was real (DIRECT, RELIES ON, TRANSITIVE all
verified against deterministic queries). The skeleton is exact. What over-ran
the graph was the interpretive PROSE — "core pricing logic" (never read it),
"if its query interface changes" (inferred mechanism). For a DEPLOYMENT tool
this is the riskiest place to over-narrate. The cli.py/ask_cli split (ADR-001,
deterministic vs probabilistic) proved its worth: the deterministic surface can
AUDIT the AI's claims. Architecture feature, not AI bug.

### Carried into Week 10 (NEW this week)
- COUPLED FIX (do in order): Refinement #10 (add edge labels to
  find_dependencies output) is now LOAD-BEARING, not optional — Claude
  over-narrates mechanism partly BECAUSE find_dependencies strips the via-label.
  ORDER: do #10 first, re-run the PricingFlowAction impact query, check if
  over-narration self-corrects, THEN tighten the impact prompt only for what
  remains. Do not band-aid the prompt before fixing the data.

### Carried forward (unchanged from Week 8)
- Capability 5 (debug log) — parked, revisit Week 12 (build real version if
  slack exists, else four capabilities stands).
- Flow record-operation edges (recordLookups→Object) — still parked.
- FIELD nodes (ADR-010) — Phase 2; the SOQL field boundary is the live evidence.
- REST /graph/ route — Week 13. Graph persistence — Phase 2. ANTLR AST — Phase 2.
- Per-capability model routing (Sonnet vs Opus) — Phase 2 idea.

### Option-B (ADR-014) decision status — still tool-pull, watching
Over-fetch warm-up count stays at 2 (apex + qa, on exact names). Key Week-9
insight: 3 of 4 capability prompts induce find_by_name in step 1 BY DESIGN, so
find_by_name-then-act is mostly designed behavior across the MVP — the warm-up
signal is now harder to isolate, which is itself Option-B-relevant. Cost data
banked: qa ~$0.024, soql $0.037, impact $0.030, apex $0.088 (apex costliest;
cost is SOURCE-READING not discovery, so pre-loading wouldn't help apex). No
revival trigger met. Tool-pull holds into Week 10.

### Tests
296 passing (275 Week-8 baseline + 21 Day-1). Days 2-4 added no tests
(capabilities covered by Day-1 prompt/registry tests + manual live verification;
live API calls are not unit-tested by design — cost + non-determinism).

### Cost ledger
~$0.18 total across Week-9 live verification runs (4 capability tests + a couple
of re-runs). $5 prepaid credit; comfortable margin. apex is the budget watch-item
at $0.088/query.

---

#### Week 10 — Prompt quality + lightweight eval harness (15 hours) ✅ — completed, ~12h

**Goal (as planned):** Build evaluation harness, iterate prompts to 90%+ pass rate.

**What actually shipped (reconciled):** Eval discovery was done inline during
Week 9 — live verification against the real org every day, deterministic CLI
auditing the AI's claims. The "run 100 cases, find failures, iterate" loop was
the mechanism; Week 9 already completed a pass of it. Week 10 therefore focused
on the specific diagnosed failure (impact-mode over-narration) and a lightweight
regression harness rather than a general-purpose eval framework.

**Day 1** — Refinement #10: edge labels on find_dependencies ✅
- `QueryEngine.outgoing_edges()` — outward mirror of `incoming_edges()`.
  Returns full Edge objects (via/method attributes) for outgoing direction.
  Inserted after `incoming_edges` in the Edge-level queries block.
- `find_dependencies` handler updated — direct mode calls `outgoing_edges()`
  and emits `via {relation}{detail}` per dependency. Transitive stays
  node-list-only: per-hop labels across multi-hop chains are noise.
- 8 new tests: 6 QueryEngine (mirrors incoming_edges test structure),
  2 tool_definitions (label present in direct output; no via in transitive).
- Suite: 296 → 304 passing.
- Root cause of impact-mode over-narration: find_dependencies stripped the
  via-label, forcing Claude to guess mechanism. Now Claude sees
  "via method call (publishPricingEvent())" and has no reason to invent prose.

**Day 2** — Live re-run + self-correction assessment ✅
- Re-ran the exact Week-9-Day-4 PricingFlowAction impact query.
- VERDICT: over-narration self-corrected without prompt changes.
  RELIES ON table (the failure site): Week 9 said "core pricing logic",
  "if its query interface changes" — inferred from node name, no graph basis.
  Week 10: "CALLS byIds() method + name reference", "CALLS publishPricingEvent()
  method + name reference" — stated from edge data, graph-grounded.
- Remaining prose (cascade claim, @InvocableMethod signature guidance) assessed
  as appropriate expert interpretation of edge types, not over-narration.
  Prompt tightening not needed — data fix was sufficient. Coupling order held.
- Cost: $0.0414 (3-turn session, disciplined tool-call pattern).

**Day 3** — Lightweight semantic eval harness ✅
- `evals/` package: `eval_case.py` (EvalCase dataclass), `eval_runner.py`
  (runner + report), `cases/` (qa/apex/soql/impact, 5 cases each).
- 20 cases total. One command: `python -m evals.eval_runner`.
  Optional `--mode` flag for single-capability runs.
- Assertions: required substrings (grounding + structure) + forbidden substrings
  (known failure modes). Full AI output printed on failure.
- Excluded from default pytest suite (live API, ~$0.035/case, ~$0.78/full run).
- 20/20 passing on first clean run against real org.
- One case fix mid-run: "method call" required string too brittle (one specific
  phrase from one tool-call path). Fixed to require "via" + forbid the Week 9
  over-narration phrases. Correct approach: assert what we're guarding, not how
  Claude phrases a specific correct answer.

**Deliverables (honest checks):**
- ✅ Refinement #10 — edge labels on find_dependencies (load-bearing, not polish)
- ✅ Self-correction confirmed — prompt untouched, over-narration gone
- ✅ Semantic eval harness — 20 cases / 4 capabilities, 20/20 passing
- ◻ 100+ test cases across 5 capabilities — deliberately not built; over-engineered
  for work already done inline during Week 9. 5 cases/capability is the right gate.
- ◻ Capability 5 (debug log) eval cases — not built; capability still parked.
- ◻ Prompt iteration — not needed; data fix was sufficient.

**Carried forward (unchanged):**
- Capability 5 (debug log) — parked, revisit Week 12.
- Flow record-operation edges — parked.
- FIELD nodes (ADR-010) — Phase 2.
- REST /graph/ route — Week 13. Graph persistence — Phase 2.
- Option-B (ADR-014) — still tool-pull. No revival trigger met.

**Tests:** 304 unit tests + 20 semantic evals (separate suite).
**Cost ledger:** ~$0.78 for full eval run. Impact queries ~$0.04/query.

---

### Phase 1C — Developer interfaces

#### Week 11 — MCP server (15 hours)

**Goal:** Expose the 5 capabilities via MCP protocol.

**Day 1-2 (5 hours)** — MCP server scaffolding
- Use Anthropic's MCP Python SDK
- `interfaces/mcp_server/server.py`
- Implement stdio transport
- Server lifecycle management

**Day 3-4 (5 hours)** — Tool exposure
- Map 5 capabilities to MCP tools
- Each tool has clear schema for inputs/outputs
- Handle errors gracefully
- Cost reporting per tool call

**Day 5 (3 hours)** — Testing with Claude Desktop
- Configure MCP server in Claude Desktop
- Test all 5 capabilities through Desktop
- Verify performance and reliability

**Day 6 (1 hour)** — Testing with Cursor and Claude Code
- Configure for both
- Verify cross-compatibility

**Day 7 (1 hour)** — Documentation
- MCP server installation guide
- Configuration examples
- Commit, push, plan Week 12

**Deliverables:**
- ✅ Working MCP server using stdio transport
- ✅ All 5 capabilities accessible via MCP
- ✅ Tested with Claude Desktop, Cursor, Claude Code
- ✅ Installation documentation
- ✅ Ready for open-source release

---

#### Week 12 — REST API + auth flow (15 hours)

**Goal:** Build REST API for VS Code extension to consume.

**Day 1-2 (5 hours)** — REST API endpoints
- `interfaces/rest_api/routes/intelligence.py`
- POST `/api/v1/metadata-qa`
- POST `/api/v1/apex-explain`
- POST `/api/v1/soql-generate`
- POST `/api/v1/deployment-impact`
- POST `/api/v1/debug-log-analyze`
- All with streaming SSE responses

**Day 3 (3 hours)** — Authentication for extension
- Local auth: API key in extension settings
- For now, single-user single-key (multi-tenant in Phase 2)

**Day 4 (3 hours)** — Rate limiting and logging
- Per-endpoint rate limits
- Structured logging for debugging
- Request/response correlation IDs

**Day 5 (3 hours)** — OpenAPI documentation
- Auto-generated from FastAPI
- Examples for each endpoint
- Schema validation

**Day 6-7 (1 hour)** — Commit, push, plan Week 13

**Deliverables:**
- ✅ REST API with all 5 capabilities
- ✅ SSE streaming support
- ✅ Auth, rate limiting, logging
- ✅ OpenAPI docs at /docs
- ✅ Ready for VS Code extension to consume

---

#### Week 13 — VS Code extension (20 hours)

**Goal:** Working VS Code extension with the 5 capabilities.

**Day 1-2 (6 hours)** — Extension scaffolding
- Yeoman generator for VS Code extension
- TypeScript setup with esbuild
- Activation events and contribution points
- Settings UI for API key

**Day 3 (4 hours)** — Command palette commands
- Command: "SF Intelligence: Ask Metadata Question"
- Command: "SF Intelligence: Explain Selected Apex"
- Command: "SF Intelligence: Generate SOQL from Description"
- Command: "SF Intelligence: Analyze Deployment Impact"
- Command: "SF Intelligence: Analyze Debug Log"

**Day 4 (4 hours)** — Sidebar UI
- Activity bar icon
- Tree view: org metadata browser
- Webview for chat-style interactions
- Streaming response display

**Day 5 (3 hours)** — REST API client
- HTTP client wrapping the FastAPI backend
- SSE handling for streaming
- Error handling with user-friendly messages

**Day 6 (2 hours)** — Polish
- Loading states
- Error messages
- Keyboard shortcuts
- Settings persistence

**Day 7 (1 hour)** — Build + commit
- esbuild bundling
- Package .vsix file for distribution
- Plan Week 14

**Deliverables:**
- ✅ Working VS Code extension
- ✅ All 5 capabilities accessible from command palette
- ✅ Sidebar UI for metadata exploration
- ✅ Packaged .vsix ready for distribution

---

### Phase 1D — Launch

#### Week 14 — Documentation and demo (15 hours)

**Goal:** Production-quality docs and demo materials.

**Day 1 (3 hours)** — Architecture deep-dive blog post
- Why metadata graph as moat
- Layered architecture explained
- Key design decisions
- Lessons learned

**Day 2 (3 hours)** — README polish
- Hero section with screenshots/GIFs
- Quick start guide
- Architecture diagram
- Feature list with examples
- Installation: MCP server + VS Code extension

**Day 3 (3 hours)** — API documentation
- Detailed API reference
- Tool documentation for MCP users
- Code examples for each capability

**Day 4-5 (5 hours)** — Demo video
- Script (5-10 minutes total)
- Screen recording of all 5 capabilities
- Voice-over explaining what's happening
- Edit with simple cuts (no need for fancy editing)
- Upload to YouTube/Loom

**Day 6 (1 hour)** — Open-source preparation
- Decide what's open vs closed
- Add LICENSE files to open-source portions
- CONTRIBUTING.md for community
- Issue templates

**Day 7** — Commit, push, plan launch

**Deliverables:**
- ✅ Polished README on GitHub
- ✅ Comprehensive docs
- ✅ Demo video (Loom or YouTube)
- ✅ Architecture blog post draft
- ✅ Open-source portions ready

---

#### Week 15 — Public launch (15 hours)

**Goal:** Get the project in front of real users.

**Day 1 (3 hours)** — Final QA pass
- Reinstall from scratch on fresh machine
- Verify installation instructions
- Test all 5 capabilities end-to-end
- Fix any rough edges

**Day 2 (3 hours)** — Open-source release
- Make MCP server repo public
- Make VS Code extension repo public
- Tag v0.1.0 releases
- Publish to MCP server registry
- Publish VS Code extension to marketplace (or have packaged .vsix)

**Day 3 (3 hours)** — LinkedIn announcement
- Write 800-1000 word post
- Architecture insights, lessons learned
- Embed demo video
- Tag relevant people in Salesforce + AI ecosystems

**Day 4 (3 hours)** — HackerNews + Reddit
- Submit to HN with strong title
- Post to r/salesforce
- Post to r/Anthropic
- Engage with comments

**Day 5 (2 hours)** — Engage with feedback
- Respond to all comments
- File issues for bugs reported
- Note feature requests for Phase 2 planning

**Day 6-7 (1 hour)** — Retrospective
- What worked, what didn't
- User feedback analysis
- Phase 2 prioritization based on real signals

**Deliverables:**
- ✅ Public release v0.1.0
- ✅ LinkedIn announcement live
- ✅ Posted to HN, Reddit
- ✅ MCP server in registry
- ✅ Initial user feedback captured
- ✅ Phase 2 priorities informed by real signals

---

## 5. What carries forward from Weeks 1-3

### Reusable assets (no changes)
- FastAPI app structure
- Pydantic models pattern
- Async architecture (httpx, asyncio)
- Dependency injection via Depends()
- pytest test suite structure
- Git workflow discipline
- Project documentation patterns (README, NOTES, TEST_URLS)
- Mock + real client pattern

### Needs minor changes
- `services/salesforce_mock.py` → moves to `salesforce/mocks/rest_mock.py`
- `services/salesforce.py` → moves to `salesforce/rest_api.py`
- `routes/accounts.py` → moves to `interfaces/rest_api/routes/`
- Imports across the codebase

### Gets replaced
- Username-password auth → OAuth 2.0 Web Server Flow
- External Client App → classic Connected App
- "Generic CRM assistant" framing → "Developer intelligence platform" framing

### Discarded
- Generic chatbot positioning
- Multi-persona ambition (for Phase 1)
- Cross-system integration plans (for Phase 1)

---

## 6. Definition of Done — Phase 1

Phase 1 is complete when ALL of these are true:

### Functional
- [ ] Five capabilities working end-to-end
- [ ] Real Salesforce OAuth working (no username-password)
- [ ] Metadata graph supporting 1000+ items
- [ ] Each capability achieving 90%+ on eval test cases
- [ ] MCP server tested with Claude Desktop, Cursor, Claude Code
- [ ] VS Code extension installable and functional

### Quality
- [ ] 100+ evaluation test cases passing
- [ ] All capabilities responding in <30 seconds
- [ ] Token cost <$0.10 per query average
- [ ] Zero crashes during 30-minute demo session
- [ ] Installation works on fresh machine following docs

### Documentation
- [ ] README with screenshots and quick start
- [ ] Architecture documentation
- [ ] API reference
- [ ] Demo video (5-10 min)
- [ ] Architecture blog post

### Launch
- [ ] MCP server published to registry
- [ ] VS Code extension packaged
- [ ] LinkedIn announcement posted
- [ ] Posted to HN, r/salesforce, r/Anthropic
- [ ] At least 3 external users have tried it

### Portfolio
- [ ] GitHub repo polished with badges, screenshots
- [ ] Clear "what problem this solves" framing
- [ ] Demonstrates: architecture, AI integration, MCP, evals, dev tooling
- [ ] References to put on resume

---

## 7. Risks and mitigations

### Risk 1 — Scope creep
**Probability:** High
**Impact:** Delays launch significantly
**Mitigation:**
- This document is the contract; refer to it weekly
- Resist adding capabilities beyond the 5
- Park "good ideas" in PHASE_2_BACKLOG.md
- Bias toward shipping over perfection

### Risk 2 — Metadata graph complexity
**Probability:** Medium
**Impact:** Could expand Weeks 5-7 to 4-5 weeks
**Mitigation:**
- Start simple; add complexity only when needed
- Use mock data heavily during development
- If a metadata pattern is too complex, document and skip
- Accept 80% coverage of patterns; defer edge cases

### Risk 3 — Evaluation accuracy
**Probability:** Medium
**Impact:** Quality bar slipping; rework needed
**Mitigation:**
- Build evals in Week 10, BEFORE building interfaces
- Iterate prompts until 90%+ achieved
- Don't proceed to MCP/VS Code if evals failing
- Document known failure modes transparently

### Risk 4 — Time underestimation
**Probability:** High
**Impact:** Push launch from Week 15 to Week 18-20
**Mitigation:**
- Build 2 weeks of slack into the plan (Weeks 14-15 are buffer-ish)
- Cut scope before extending timeline
- If a week falls behind, drop one capability rather than add weeks
- Could ship with 4 capabilities instead of 5

### Risk 5 — Burnout from intensity
**Probability:** Medium
**Impact:** Project stalls indefinitely
**Mitigation:**
- 15-20 hours/week is the ceiling, not the floor
- Take a full week off after every 5 weeks
- Skip features rather than skip rest
- Ship something every week to maintain momentum

### Risk 6 — Salesforce API changes
**Probability:** Low
**Impact:** Breaks during development
**Mitigation:**
- Stick to GA APIs only
- Avoid pilot/beta features
- Mock heavily so dev doesn't depend on live Salesforce

### Risk 7 — Job offer arrives mid-project
**Probability:** High (this is the goal)
**Impact:** Less time for project; may need to pause
**Mitigation:**
- Project should already be 50%+ done by then
- Document everything so future-you can resume
- Could become "20% time" project at new job
- Even partial completion is strong portfolio signal

---

## 8. Phase 2+ ideas (deferred)

These are intentionally NOT in Phase 1. Captured here so they're not lost.

### Phase 2 — Expand to admins (estimated 8-12 weeks after Phase 1)
- Permission analysis
- Flow debugging
- Config recommendations
- Org health insights

### Phase 3 — Cross-system context (estimated 12+ weeks after Phase 2)
- Slack message integration
- JIRA ticket integration
- Google Docs context
- Email thread mining

### Phase 4 — Multi-agent orchestration (estimated 6+ months after Phase 3)
- Sales agent
- Deployment agent
- Admin agent
- Support agent
- Orchestrator that coordinates between agents

### Phase 5 — Multi-tenant SaaS (timing depends on product-market fit)
- Web app for non-developers
- Authentication and billing
- Team collaboration features

### Phase 6 — Enterprise features (timing depends on customer demand)
- SOC 2 compliance
- Custom deployment options
- Enterprise SSO
- Audit logging at scale

---

## 9. Reference materials

### Salesforce docs (essential reading)
- Metadata API: https://developer.salesforce.com/docs/atlas.en-us.api_meta.meta/api_meta/meta_intro.htm
- Tooling API: https://developer.salesforce.com/docs/atlas.en-us.api_tooling.meta/api_tooling/intro_api_tooling.htm
- OAuth 2.0 Web Server Flow: https://help.salesforce.com/s/articleView?id=sf.remoteaccess_oauth_web_server_flow.htm

### MCP docs
- MCP specification: https://modelcontextprotocol.io/
- Python SDK: https://github.com/modelcontextprotocol/python-sdk
- Example servers: https://github.com/modelcontextprotocol/servers

### Anthropic docs
- Claude API: https://docs.anthropic.com/
- Tool use guide: https://docs.anthropic.com/claude/docs/tool-use
- Prompt engineering: https://docs.anthropic.com/claude/docs/prompt-engineering

### Inspiration / competitive landscape
- Salesforce Code Builder (their official IDE)
- Salesforce Inspector Reloaded (community Chrome extension — great UX reference)
- jpmonette/salesforce-mcp (community MCP server)
- Salesforce Data 360 MCP Server (their official one)
- Salesforce DX MCP Server (their dev tools MCP)

---

## Working agreement with Claude

Throughout Phase 1, when working with Claude on this project:

- Treat this document as the source of truth
- Reference specific weeks/days when starting sessions
- Update CHANGELOG.md after each week
- Ask for honest pushback when needed
- Refuse scope creep; defer to Phase 2 backlog
- Maintain the eval discipline starting Week 10

---

**Last updated:** Week 3 completion
**Next review:** End of Week 4 (after foundation refresh)
**Document owner:** Veda Arvind