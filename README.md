# Salesforce AI Metadata Graph

> An AI-powered intelligence layer for Salesforce developers. Ask questions
> about your org's metadata, dependencies, Apex, and Flows in natural language.
> Open-core: MCP server and metadata extractor are open source; advanced
> features are proprietary.

🚧 **Work in progress** — actively being built. See [ROADMAP.md](./ROADMAP.md) for
the Phase 1 plan (15 weeks to portfolio launch).

---

## Current status

**Week 4 complete** ✅ — Salesforce OAuth 2.0 Web Server Flow with PKCE is
working end-to-end. The backend can now authenticate against a real
Salesforce org and run SOQL queries with transparent token refresh.

Next: metadata graph construction (Weeks 5-7).

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

- **Real Salesforce authentication** via OAuth 2.0 Web Server Flow with PKCE
- **Transparent token refresh** — access tokens auto-refresh on 401, refresh tokens rotate
- **Mock + real client architecture** — swap between mock and real via `USE_MOCK_DATA` env var
- **9 REST endpoints** — 4 account endpoints + 3 auth endpoints + /health + /docs
- **19 automated tests** — including 5 dedicated tests for OAuth refresh-on-401 lifecycle
- Async-first FastAPI backend with concurrent query support
- Lifespan-managed shared client (mock or real, decided at startup)
- Pydantic v2 models with full type safety
- Tests are hermetic — produce the same result regardless of `.env` state

## Tech stack

**Currently in the codebase**
- Python 3.11+ with FastAPI
- Pydantic v2 (type-safe data validation)
- httpx (async HTTP client)
- python-dotenv (env var loading)
- pytest + TestClient + httpx.MockTransport (integration + unit testing)

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
│  Metadata API + Tooling API (Week 5)                            │
│  REST API (✅ working — Week 4)                                 │
│  OAuth 2.0 Web Server Flow + PKCE (✅ working — Week 4)         │
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
│   │   │   ├── auth.py                            # OAuth 2.0 + PKCE logic
│   │   │   ├── oauth_models.py                    # OAuth response models
│   │   │   ├── token_storage.py                   # Token persistence (gitignored file)
│   │   │   ├── rest_api.py                        # Real OAuth-backed async REST client
│   │   │   └── mocks/
│   │   │       └── rest_mock.py                   # Mock client for development
│   │   └── interfaces/                            # All consumer-facing entry points
│   │       └── rest_api/
│   │           └── routes/
│   │               ├── accounts.py                # /accounts/* endpoints
│   │               └── auth.py                    # /auth/* endpoints
│   ├── tests/
│   │   ├── test_endpoints.py                      # 14 pytest tests (mock client)
│   │   └── test_salesforce_client.py              # 5 pytest tests (real client + refresh)
│   ├── requirements.txt
│   ├── .env.example                               # Template (.env is gitignored)
│   └── tokens.json                                # OAuth tokens (gitignored)
├── README.md
├── ROADMAP.md                                     # Phase 1 15-week plan
├── NOTES.md                                       # Development journal
├── TEST_URLS.md                                   # Manual testing reference
├── LICENSE                                        # MIT
└── .gitignore                                     # Protects secrets

Future directories (will appear as Phase 1 progresses):
- `backend/app/intelligence/` — metadata graph, code intel, orchestration (Weeks 5-9)
- `backend/app/interfaces/mcp_server/` — MCP protocol server (Week 11)
- `vscode-extension/` — TypeScript VS Code extension (Week 13)
- `evals/` — evaluation test cases and runners (Week 10)

## Running locally

### Prerequisites
- Python 3.11+
- Git
- A Salesforce Developer Edition org (free at developer.salesforce.com)

### Setup

```bash
git clone https://github.com/yourusername/salesforce-ai-assistant.git
cd salesforce-ai-assistant/backend
pip install -r requirements.txt
```

### Salesforce side — one-time setup

1. In your dev org: Setup → App Manager → New External Client App
2. Enable OAuth Settings; Callback URL: `http://localhost:8000/auth/callback`
3. Selected Scopes: `api`, `refresh_token`, `id`
4. Enable: Authorization Code and Credentials Flow, PKCE required, Refresh Token Rotation
5. Save, wait 10 minutes for propagation
6. Copy the Consumer Key + Consumer Secret

### Environment

Copy the template and fill in the OAuth values:

```bash
cp .env.example .env
# Edit .env with your Consumer Key and Consumer Secret
```

The `USE_MOCK_DATA` toggle in `.env`:
- `true` (default) — uses the in-memory mock client; no Salesforce required
- `false` — uses the real OAuth-backed client; requires valid tokens

### Start the server

```bash
uvicorn app.main:app --reload
```

Server runs at `http://localhost:8000`. Startup log will say `MOCK` or `REAL`
depending on `USE_MOCK_DATA`.

### Authenticate (real mode only)

If `USE_MOCK_DATA=false`, visit `http://localhost:8000/auth/login` in a browser
to run through the OAuth flow. Tokens persist to `tokens.json` (gitignored)
and survive server restarts.

### Try it

- `http://localhost:8000/docs` — interactive API documentation
- `http://localhost:8000/accounts/` — list accounts (mock or real org)
- `http://localhost:8000/auth/status` — check authentication state
- See [`TEST_URLS.md`](./TEST_URLS.md) for the full list of testable URLs

### Run tests

```bash
cd backend
pytest tests/ -v
```

All 19 tests should pass in ~12 seconds. Tests are hermetic — they force
`USE_MOCK_DATA=true` via `monkeypatch.setenv`, so they don't care what's
in your `.env`.

## Key technical decisions

A few choices and why:

**FastAPI over Flask/Django** — Async-native (matches Salesforce I/O patterns),
auto-generated OpenAPI docs, Pydantic integration is unmatched.

**Layered architecture (`salesforce/`, `intelligence/`, `interfaces/`)** —
Separates concerns by *what they do*, not by file type. Lets Week 11 add an
MCP server without disturbing anything else.

**External Client App over classic Connected App** — Salesforce is phasing
out Connected Apps in newer org versions. External Client Apps now have full
Web Server Flow + PKCE + RTR support. Using the forward path on a portfolio
project signals current Salesforce knowledge.

**OAuth Web Server Flow with PKCE** — The username-password flow is deprecated
and was broken in our Week 2 attempt. PKCE is mandatory for External Client
Apps as of May 2026. Web Server Flow is what real dev tools use.

**Mock client + real client via duck typing** — Same async interface
(`__aenter__`, `authenticate`, `query`, `query_all`), no shared inheritance.
Phase 1 keeps it simple; if we grow more methods/clients, a `Protocol` will
formalize the contract.

**Transparent refresh-on-401** — Access tokens expire (~2 hours);
SalesforceClient handles refresh internally so endpoint code never sees auth
complexity. Caller writes `await client.query(soql)` — nothing else.

**Tests must be hermetic** — `monkeypatch.setenv` in test fixtures so tests
behave identically regardless of `.env` state. Apex enforces this via `@isTest`
semantics; Python doesn't, so we design it in deliberately.

**Dependency injection for HTTP client** — `auth.py`'s functions accept an
optional `httpx.AsyncClient` parameter. Lets tests inject `MockTransport`,
lets production code share connection pools. The Apex parallel is
`HttpCalloutMock` injection via `Test.setMock()`.

## Roadmap (high level)

Detailed week-by-week plan in [ROADMAP.md](./ROADMAP.md).

- [x] Foundation: Python OOP, Pydantic, async (Weeks 1-2)
- [x] FastAPI backend with mock data + tests (Week 3)
- [x] **Architecture refactor + Salesforce OAuth 2.0 + real REST client (Week 4)**
- [ ] Metadata API extraction + graph construction (Weeks 5-7) ← next
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