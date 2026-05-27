# Salesforce AI Metadata Graph

> An AI-powered intelligence layer for Salesforce developers. Ask questions
> about your org's metadata, dependencies, Apex, and Flows in natural language.
> Open-core: MCP server and metadata extractor are open source; advanced
> features are proprietary.

🚧 **Work in progress** — actively being built. See [ROADMAP.md](./ROADMAP.md) for
the Phase 1 plan (15 weeks to portfolio launch).

---

## Current status

**Week 4 in progress** — Architecture refactor and Salesforce OAuth 2.0 setup.
See [ROADMAP.md](./ROADMAP.md) for week-by-week plan.

## Project vision

A developer-focused Salesforce intelligence platform with five core capabilities:

1. **Metadata Q&A** — Natural language questions about org structure and dependencies
2. **Apex explanation and refactoring** — Intelligent code analysis with full metadata context
3. **SOQL generation** — Natural language to SOQL using your org's actual schema
4. **Deployment impact analysis** — Trace what could break when you deploy a change
5. **Debug log analysis** — Root-cause analysis with code and metadata context

Accessible via MCP server (open source, works with Claude Desktop, Cursor, Claude Code)
and a VS Code extension. Built for the developer persona first; admin, sales,
and support features may come in Phase 2.

## What's working today

- 6 working REST endpoints (mock data) — foundation for the upcoming intelligence layer
- Async-first FastAPI backend with concurrent query support
- Lifespan-managed shared Salesforce client
- Dependency injection pattern for clean endpoint code
- Pydantic v2 models with full type safety
- 14 automated tests passing in ~5 seconds
- Layered architecture ready for the metadata graph (Weeks 5-7), Claude integration (Weeks 8-10), and developer interfaces (Weeks 11-13)

## Tech stack

**Currently in the codebase**
- Python 3.11+ with FastAPI
- Pydantic v2 (type-safe data validation)
- httpx (async HTTP client)
- pytest + TestClient (integration testing)

**Coming in upcoming weeks**
- Salesforce Metadata API + Tooling API clients (Week 5)
- networkx-based metadata graph with SQLite persistence (Weeks 6-7)
- Apex parser and Flow analyzer (Week 7)
- Anthropic Claude API with tool use (Weeks 8-9)
- pytest-based evaluation harness (Week 10)
- MCP server using the Anthropic Python SDK (Week 11)
- TypeScript + VS Code Extension API (Week 13)

## Architecture (target — being built through Phase 1)


┌────────────────────────────────────────────────────────────────┐
│                    USER-FACING INTERFACES                       │
├────────────────────────────────────────────────────────────────┤
│  VS Code Ext  │  MCP Server (stdio)  │  REST API  │  CLI       │
│  (Week 13)    │  (Week 11)           │  (current) │  (testing) │
└──────┬─────────────┬────────────────────┬───────────┬──────────┘
│             │                    │           │
└─────────────┴────────────────────┴───────────┘
│
▼
┌────────────────────────────────────────────────────────────────┐
│              ORCHESTRATION LAYER (Weeks 8-9)                    │
│  Receives requests, builds context, calls Claude with tools     │
└──────────────────────────┬─────────────────────────────────────┘
│
┌──────────────┼──────────────┐
▼              ▼              ▼
┌────────────────┐ ┌──────────────┐ ┌──────────────────────┐
│ METADATA GRAPH │ │ CODE INTEL   │ │ CONTEXT RETRIEVAL    │
│ (Weeks 5-6)    │ │ (Week 7)     │ │ (Week 8)             │
│ Objects/Fields │ │ Apex parser  │ │ Token-efficient      │
│ Relationships  │ │ Flow XML     │ │ context for Claude   │
│ Dependencies   │ │ Triggers     │ │                      │
└───────┬────────┘ └──────┬───────┘ └─────────┬────────────┘
│                 │                   │
└─────────────────┼───────────────────┘
│
▼
┌────────────────────────────────────────────────────────────────┐
│              SALESFORCE DATA LAYER                              │
│  Metadata API + Tooling API + REST API (current)                │
│  OAuth 2.0 Web Server Flow (Week 4)                             │
│  SQLite local cache (Week 7)                                    │
└─────────────────────────────────────────────────────────────────┘

## Project structure
salesforce-ai-assistant/
├── backend/
│   ├── app/
│   │   ├── main.py                                # FastAPI entry point + lifespan
│   │   ├── dependencies.py                        # Dependency injection helpers
│   │   ├── models/
│   │   │   └── salesforce.py                      # Pydantic models for SF data
│   │   ├── salesforce/                            # Salesforce data layer
│   │   │   ├── rest_api.py                        # Real async REST client
│   │   │   └── mocks/
│   │   │       └── rest_mock.py                   # Mock client for development
│   │   └── interfaces/                            # All consumer-facing entry points
│   │       └── rest_api/
│   │           └── routes/
│   │               └── accounts.py                # /accounts/* endpoints
│   ├── tests/
│   │   └── test_endpoints.py                      # 14 pytest integration tests
│   ├── requirements.txt
│   └── .env.example
├── README.md
├── ROADMAP.md                                     # Phase 1 15-week plan
├── NOTES.md                                       # Development journal
├── TEST_URLS.md                                   # Manual testing reference
├── LICENSE                                        # MIT
└── .gitignore                                     # Protects secrets


Future directories (will appear as Phase 1 progresses):
- `backend/app/intelligence/` — metadata graph, code intel, orchestration (Weeks 5-9)
- `backend/app/interfaces/mcp_server/` — MCP protocol server (Week 11)
- `backend/app/interfaces/cli/` — CLI for testing (as needed)
- `vscode-extension/` — TypeScript VS Code extension (Week 13)
- `evals/` — evaluation test cases and runners (Week 10)

## Running locally

### Prerequisites
- Python 3.11+
- Git

### Setup

```bash
git clone https://github.com/yourusername/salesforce-ai-assistant.git
cd salesforce-ai-assistant/backend
pip install -r requirements.txt
```

### Start the server

```bash
uvicorn app.main:app --reload
```

Server runs at `http://localhost:8000`.

### Try it

- Visit `http://localhost:8000/docs` for interactive API documentation
- Visit `http://localhost:8000/accounts/` to see mock account data
- See [`TEST_URLS.md`](./TEST_URLS.md) for the full list of testable URLs

### Run tests

```bash
cd backend
pytest tests/ -v
```

All 14 tests should pass in ~5 seconds.

## Key technical decisions

A few choices and why:

**FastAPI over Flask/Django** — Async-native (matches Salesforce I/O patterns),
auto-generated OpenAPI docs, Pydantic integration is unmatched.

**Layered architecture (`salesforce/`, `intelligence/`, `interfaces/`)** —
Separates concerns by *what they do*, not by file type. The Salesforce layer
only knows how to talk to Salesforce. The intelligence layer doesn't care
where the data came from. The interfaces layer (REST, MCP, CLI, VS Code)
doesn't care what the intelligence is. This is what lets Week 11 add an MCP
server without disturbing anything else.

**Mock client + real client (same interface)** — Develop without dependency
on Salesforce being available. The mock has the same async method signatures
as the real client; the lifespan in `main.py` picks which to use.

**Lifespan-managed shared client** — Create the client once at startup, share
across all requests. Avoids re-authenticating per request.

**Dependency injection via `Depends()`** — Endpoints declare what they need,
FastAPI provides it. Decouples endpoints from how dependencies are constructed.

**Tests written alongside features** — 14 tests run in 5 seconds, catching
regressions during the upcoming Salesforce auth, Claude integration, and
metadata graph work.

## Roadmap (high level)

Detailed week-by-week plan in [ROADMAP.md](./ROADMAP.md).

- [x] Foundation: Python OOP, Pydantic, async (Weeks 1-2)
- [x] FastAPI backend with mock data + tests (Week 3)
- [ ] **Architecture refactor + Salesforce OAuth 2.0 (Week 4)** ← in progress
- [ ] Metadata API extraction + graph construction (Weeks 5-7)
- [ ] Claude integration with tool use (Weeks 8-9)
- [ ] Evaluation harness with 100+ test cases (Week 10)
- [ ] MCP server for Claude Desktop / Cursor / Claude Code (Week 11)
- [ ] REST API + VS Code extension (Weeks 12-13)
- [ ] Documentation, demo video, public launch (Weeks 14-15)

## About this project

Built by a senior Salesforce developer (10 years of enterprise CRM experience)
learning modern AI engineering. Goal: demonstrate production-grade patterns
for integrating LLMs with enterprise SaaS systems — specifically, building
a metadata-aware intelligence layer that understands what's in your Salesforce
org and helps developers reason about it.

Building in public — follow commits to see the journey.

## License

MIT for open-source components — see [LICENSE](./LICENSE).
Some advanced features may be released under different terms in future phases.

