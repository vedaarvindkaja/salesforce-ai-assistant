# Salesforce AI Assistant

> An AI-powered backend for Salesforce CRM that uses Claude (Anthropic) to answer
> questions, query records, and take actions via natural language.

🚧 **Work in progress** — actively being built. See [roadmap](#roadmap) below.

---

## Current status

**Week 3 complete** ✅ — FastAPI backend with mock Salesforce data, automated tests,
and concurrent query support. Real Salesforce auth, Claude integration, and chat
UI coming in Weeks 4-10.

## What's working today

- 6 production-grade API endpoints (4 GET, 1 POST, plus health check)
- Auto-generated OpenAPI documentation at `/docs`
- Async-first architecture (concurrent SOQL queries via `asyncio.gather`)
- Lifespan-managed shared Salesforce client (created once at startup)
- Dependency injection pattern for clean endpoint code
- CORS middleware (ready for React frontend in Week 8+)
- Pydantic v2 models with full type safety end-to-end
- 14 automated tests passing in ~5 seconds (pytest + TestClient)

## Working endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Server status check |
| GET | `/accounts/` | List accounts with `limit` validation (1-100) |
| GET | `/accounts/search/` | Filter by `industry` and/or `min_revenue` |
| GET | `/accounts/{id}` | Get specific account, returns 404 if not found |
| POST | `/accounts/batch` | Run multiple SOQL queries concurrently |
| GET | `/docs` | Auto-generated interactive API documentation |

## Tech stack

**Backend (current)**
- Python 3.11+
- FastAPI 0.136+ (async-first web framework)
- Pydantic v2 (type-safe data validation)
- httpx (async HTTP client)
- pytest + TestClient (integration testing)
- uvicorn (ASGI server)

**Coming in future weeks**
- Anthropic Claude API with tool use (Week 5-6)
- SQLite + aiosqlite (caching layer, Week 7)
- React 18 + Vite + TailwindCSS (frontend, Weeks 8-10)
- Railway + Vercel (deployment, Week 11)

## Architecture

┌──────────────────────────────────────────┐
│              HTTP CLIENT                 │
│  (Browser, curl, Week 8+ React frontend) │
└────────────────┬─────────────────────────┘
│
▼
┌──────────────────────────────────────────┐
│              FastAPI App                 │
│  ┌────────────────────────────────────┐  │
│  │  CORS Middleware                   │  │
│  ├────────────────────────────────────┤  │
│  │  app/main.py — entry point         │  │
│  │  ↓ includes routers                │  │
│  │  app/routes/accounts.py            │  │
│  │  ↓ injects via Depends()           │  │
│  │  app/dependencies.py               │  │
│  │  ↓ returns shared client           │  │
│  │  app.state.sf_client (singleton)   │  │
│  └────────────────────────────────────┘  │
└────────────────┬─────────────────────────┘
│
▼
┌──────────────────────────────────────────┐
│        Salesforce Client (async)         │
│  ┌────────────────────────────────────┐  │
│  │  Mock (current)  ──┐               │  │
│  │                    ├─ same interface│  │
│  │  Real (Week 4)  ──┘                │  │
│  └────────────────────────────────────┘  │
└────────────────┬─────────────────────────┘
│
▼
┌──────────────────────────────────────────┐
│            Pydantic Models               │
│  Account, SalesforceQueryResponse,       │
│  BatchQueryRequest, BatchQueryResult,    │
│  SalesforceAuthResponse                  │
└──────────────────────────────────────────┘

## Project structure

salesforce-ai-assistant/
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI entry point + lifespan
│   │   ├── dependencies.py          # Dependency injection helpers
│   │   ├── models/
│   │   │   └── salesforce.py        # Pydantic models for SF data
│   │   ├── services/
│   │   │   ├── salesforce.py        # Real async SF client (Week 4)
│   │   │   └── salesforce_mock.py   # Mock client for development
│   │   └── routes/
│   │       └── accounts.py          # /accounts/* endpoints
│   ├── tests/
│   │   └── test_endpoints.py        # 14 pytest integration tests
│   ├── requirements.txt
│   └── .env.example
├── README.md
├── NOTES.md                          # Development journal
├── TEST_URLS.md                      # Manual testing reference
├── LICENSE                           # MIT
└── .gitignore                        # Protects secrets


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

A few choices I made and why:

**FastAPI over Flask/Django** — Async-native (matches Salesforce I/O patterns),
auto-generated OpenAPI docs, Pydantic integration is unmatched.

**Mock client + real client (same interface)** — Develop the API without
dependency on Salesforce being available. When real auth is fixed (Week 4),
swap one line in `main.py` and everything keeps working.

**Lifespan-managed shared client** — Create the client once at startup, share
across all requests. Avoids re-authenticating per request. Standard production
pattern.

**Dependency injection via `Depends()`** — Endpoints declare what they need
(`client: MockSalesforceClient = Depends(get_sf_client)`), FastAPI provides it.
Decouples endpoints from how dependencies are constructed.

**CORS configured early** — Even though there's no React frontend yet, configuring
CORS now means Week 8 React integration won't hit cross-origin errors.

**Tests written alongside features** — Each endpoint has corresponding tests.
14 tests run in 5 seconds, catching regressions during the upcoming Salesforce
auth and Claude integration work.

## Roadmap

- [x] Foundation: Python OOP, Pydantic, async (Weeks 1-2)
- [x] **FastAPI backend with mock data + tests (Week 3)** ← we are here
- [ ] Real Salesforce auth via classic Connected App (Week 4)
- [ ] Anthropic Claude integration with system prompts (Week 5)
- [ ] Claude tool use — natural language → SOQL queries (Week 6)
- [ ] SQLite caching layer to respect API limits (Week 7)
- [ ] React + Vite + TailwindCSS chat UI (Weeks 8-10)
- [ ] Public deployment to Railway + Vercel (Week 11)
- [ ] Polish, demo video, and blog post (Weeks 12-13)

## About this project

Built by a senior Salesforce developer (10 years of enterprise CRM experience)
learning modern AI engineering. The goal is to demonstrate production-grade
patterns for integrating LLMs with enterprise SaaS systems — specifically,
combining deep Salesforce knowledge with the latest AI capabilities.

Building in public — follow commits to see the journey.

## License

MIT — see [LICENSE](./LICENSE)