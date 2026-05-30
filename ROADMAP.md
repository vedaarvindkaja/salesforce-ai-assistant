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

#### Week 7 — Apex parser, code intelligence, and field-level graph (20 hours)

**Goal:** Add Apex source understanding to the graph, and — with field
references now extractable from code — add Object/Field nodes plus the
field/relationship edges deferred from Week 6.

Reconcile against reality at week start (as every week). Two notes carried in
from Week 6:
- The cache holds only ApexClass + ApexTrigger. Object/Field nodes don't exist
  yet; they must be created before field-reference edges can.
- "Apex parser" here means PATTERN-BASED extraction (regex over structured
  constructs: SOQL FROM/SELECT, DML, Object.Field refs, Class.method calls),
  NOT a full ANTLR AST. Full AST is heavy and a Phase 2 candidate; pattern
  extraction gets the high-value 80% (continues ADR-006's stance).

**Day 1 (3 hours)** — Test-class classifier (elevated from parked → first-class)
- Classify each node test-vs-production at build time: name ends in
  Test/Tests OR body contains `@isTest`. Store as a Node attribute (`is_test`)
- Wire one filter/de-rank flag through QueryEngine queries
- Justification: test-class noise hit 3 independent queries (Week 5 ranking,
  Week 6 out-degree, Week 6 never-referenced was 80% tests). Structural, not
  cosmetic. Do it first — it improves the quality of every edge/query below

**Day 1-2 (5 hours)** — Apex pattern parser
- `intelligence/code/apex_parser.py`
- Extract from each Apex body: SOQL queries (→ referenced objects/fields),
  DML ops (→ objects modified), explicit field refs (`Object.Field`), static
  method calls (`Class.method` → class deps)
- Identify trigger handlers and event types; mark `@InvocableMethod` as
  flow-callable
- Test coverage on parser logic (hermetic, synthetic Apex bodies)

**Day 3-4 (6 hours)** — Object/Field nodes + code edges into the graph
- Create Object and Field nodes from references the parser discovers
  (NodeType.OBJECT / NodeType.FIELD enum stubs from Week 6 become live)
- Add edges: Apex → Object (SOQL/DML), Apex → Field (field refs),
  Apex → Apex (static calls)
- Builder is already type-agnostic (Week 6, ADR-008/009) — extend the
  type→NodeType map; traversal/query/CLI code unchanged
- **DECISION at week start (ADR-worthy): derive vs extract.**
  Lean = DERIVE Object/Field nodes from Apex references only (no separate
  EntityDefinition/FieldDefinition extraction). Unblocks the field-impact demo
  cheaply; downside is non-referenced fields/objects don't appear. Extracting
  authoritative metadata is the alternative — more complete, more work. Decide
  before building Day 3

**Day 5 (4 hours)** — Flow analysis [SCOPE-RISK — first trim candidate]
- `intelligence/code/flow_analyzer.py`
- Parse Flow XML: triggering object, field refs, subflows, Apex actions invoked
- PREREQUISITE not yet met: Flow metadata isn't extracted (recall Week 5
  FlowDefinition.MasterLabel unreliability). Needs a Flow extraction step first
- If Week 7 is running hot, push this whole day to Week 8 — the field-impact
  headline does not depend on it

**Day 6 (3 hours)** — Dependency tracker [SCOPE-RISK — evaluate before building]
- `intelligence/code/dependency_tracker.py`
- "If I change X, what's affected?" — ranked impact list, tests de-ranked via
  the Day 1 classifier
- NOTE: once the graph has Object/Field edges, this may be a thin wrapper over
  `what_depends_on(transitive=True)` + ranking. Decide whether it earns a new
  module or folds into query.py. Don't build a module for the sake of the plan

**Day 7 (1 hour)** — Commit, push, ROADMAP update, refresh Project knowledge,
plan Week 8

**Deliverables (honest checks):**
- ✅ Test-vs-production node classification, with query filtering
- ✅ Apex pattern parser extracting SOQL/DML/field/class references
- ✅ Object/Field nodes + Apex→Object/Field/Apex edges in the graph
- ✅ Headline demo: `depends-on Account.Industry` (or similar real field) traces
  the Apex classes that reference it — "what breaks if I remove this field"
- ◻ Flow analyzer — TARGET, but first to slip to Week 8 if time-constrained
- ◻ Dependency tracker — build only if it's more than a query.py wrapper
- ⬜ Master-detail/lookup edges + validation-rule edges — still deferred; they
  need CustomField/ValidationRule metadata extraction (Week 8 unless the
  derive/extract decision pulls extraction forward)
- ⬜ Full ANTLR AST parser — Phase 2 candidate; pattern extraction covers Phase 1

**ADRs likely this week:** derive-vs-extract Object/Field nodes; possibly a
pattern-parser scope ADR. Flag genuine trade-offs only.

---

### Phase 1B — Claude integration

#### Week 8 — Orchestration layer (15 hours)

**Goal:** Make the graph queryable through Claude.

**Day 1-2 (5 hours)** — Claude client setup
- `intelligence/orchestration/claude_client.py`
- Anthropic SDK integration
- Streaming support
- Token counting and cost tracking
- Error handling and retries

**Day 3-4 (5 hours)** — Tool definitions
- `intelligence/orchestration/tool_definitions.py`
- Define tools Claude can call:
  - `query_metadata_graph(query: str)`
  - `get_object_definition(object_name: str)`
  - `get_apex_source(class_name: str)`
  - `find_dependencies(metadata_id: str)`
  - `find_references_to(metadata_id: str)`
  - `get_flow_definition(flow_name: str)`

**Day 5 (3 hours)** — Context window builder
- `intelligence/context/retrieval.py`
- Given a user query, retrieve relevant metadata
- Token-efficient packing (don't send the entire org)
- `intelligence/context/compression.py`
- Strategies: summarize large objects, link related items

**Day 6-7 (2 hours)** — First end-to-end test
- CLI command: ask a question, get an answer
- Use real org metadata + Claude
- Verify tool use works correctly
- Commit, push, plan Week 9

**Deliverables:**
- ✅ Claude calling tools to query the metadata graph
- ✅ Context builder packing relevant metadata efficiently
- ✅ First working end-to-end example
- ✅ Cost tracking infrastructure in place

---

#### Week 9 — The 5 MVP capabilities (20 hours)

**Goal:** Build all 5 capabilities, each as a coherent flow.

**Day 1 (4 hours)** — Capability 1: Metadata Q&A
- Prompt template
- Tool orchestration flow
- Format response with citations

**Day 2 (4 hours)** — Capability 2: Apex explanation/refactoring
- Two sub-flows: explain vs refactor
- Pull relevant metadata for context
- Format output with code blocks + explanation

**Day 3 (4 hours)** — Capability 3: SOQL generation
- Take natural language + org context
- Generate SOQL that uses actual field names
- Validate SOQL syntax before returning
- Optional: dry-run against describe metadata

**Day 4 (4 hours)** — Capability 4: Deployment impact analysis
- Input: list of metadata components or change set XML
- Trace dependencies through graph
- Format risk assessment with severity levels

**Day 5 (3 hours)** — Capability 5: Debug log analysis
- Parse debug log structure
- Identify error stack traces
- Cross-reference against Apex source
- Format root cause analysis

**Day 6-7 (1 hour)** — Commit, push, plan Week 10

**Deliverables:**
- ✅ All 5 capabilities working end-to-end via CLI
- ✅ Each capability has at least 5 manual test cases passing
- ✅ Performance: each query completes in <30s
- ✅ Cost per query tracked

---

#### Week 10 — Evaluation harness (20 hours)

**Goal:** Build rigorous evaluation, hit 90%+ accuracy on test cases.

**Day 1-2 (6 hours)** — Eval framework
- `evals/runners/eval_runner.py`
- pytest-based evaluation framework
- Test case format: input + expected output schema
- Scoring: exact match, semantic similarity, structural correctness

**Day 3 (4 hours)** — Test cases for Capabilities 1-2
- 20+ test cases for metadata Q&A
- 20+ test cases for Apex explanation
- Run evals, identify failures

**Day 4 (4 hours)** — Test cases for Capabilities 3-5
- 20+ for SOQL generation
- 20+ for deployment impact
- 20+ for debug log analysis

**Day 5-6 (5 hours)** — Iterate on prompts
- Analyze failure patterns
- Adjust prompt templates
- Re-run evals
- Target: 90%+ pass rate across all capabilities

**Day 7 (1 hour)** — Document eval methodology and results
- Commit, push, plan Week 11

**Deliverables:**
- ✅ 100+ evaluation test cases across 5 capabilities
- ✅ Automated eval runner
- ✅ 90%+ pass rate documented
- ✅ Failure analysis with documented fix strategies
- ✅ Evaluation report in `evals/reports/`

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