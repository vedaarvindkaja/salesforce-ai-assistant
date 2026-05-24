# Project Notes — Salesforce AI Assistant

A running journal of decisions, problems, and lessons learned while building this 
project. Written for my future self.

---

## Project goal

Build a portfolio-quality AI assistant for Salesforce CRM that demonstrates 
production-grade patterns for integrating Claude (Anthropic) with enterprise 
SaaS systems. Target: deployed, demoable web app by ~Week 13.

## Background

- 10 years as a Senior Salesforce developer
- Learning Python and AI engineering on evenings/weekends
- Goal: position myself for senior AI engineering roles

## Tech stack

| Layer | Choice | Why |
|---|---|---|
| Backend language | Python 3.11+ | Best ecosystem for AI/LLM work |
| Web framework | FastAPI | Async-native, Pydantic-friendly, auto-docs |
| Type safety | Pydantic v2 | Runtime validation + serialization |
| HTTP client | httpx | Async, modern, drop-in for urllib/requests |
| LLM provider | Anthropic Claude | Better tool use semantics than alternatives |
| Local cache | SQLite (aiosqlite) | Simple, file-based, plenty for portfolio scale |
| Frontend | React (Vite) + Tailwind | Modern stack, lots of jobs use it |
| Backend deploy | Railway | Free tier, GitHub-based auto-deploy |
| Frontend deploy | Vercel | Best-in-class for React hosting |
| Version control | Git + GitHub | Standard |

## Timeline (planning)

- **Weeks 1-2** ✅ Python OOP, Pydantic, async (foundations)
- **Week 3** ⏳ FastAPI backend
- **Week 4** ⏳ Fix Salesforce auth (External Client App → Connected App)
- **Week 5** ⏳ Anthropic API + basic /chat endpoint
- **Week 6** ⏳ Tool use (Claude queries Salesforce)
- **Week 7** ⏳ SQLite caching layer
- **Weeks 8-10** ⏳ React chat UI
- **Week 11** ⏳ Public deployment
- **Weeks 12-13** ⏳ Polish, demo video, blog post

---

## Foundational work (Weeks 1-2 — completed)

### What I built before starting the real project

- Async, typed Salesforce client using httpx and Pydantic
- Pydantic models: SalesforceAuthResponse, Account, SalesforceQueryResponse
- MockSalesforceClient for development without live Salesforce
- Real SalesforceClient with async context manager pattern
- Concurrent query execution with asyncio.gather (~3x speedup demonstrated)

### Key learnings

- Async makes a huge difference for I/O-bound work (3+ concurrent queries 
  finish in ~1/N the time)
- time.sleep() vs asyncio.sleep() — never mix blocking calls into async code
- Pydantic v2 .model_validate_json() is way cleaner than json.loads + dict access

---

## Open issues / parking lot

These are things I noticed but deliberately deferred to focus on the build.

### Salesforce OAuth issue (to fix Week 4)

- Currently getting `invalid_grant: authentication failure` (HTTP 400)
- Using External Client App with grant_type=password
- Suspected fix: create classic Connected App instead (External Client Apps 
  appear to have deprecated username-password flow)
- Workaround for now: using mock JSON data
- Files affected: sf_secrets.py, sf_client.py

### Salesforce credentials rotation (do before going public)

- Some credentials were exposed in screenshots during early learning
- Before pushing this repo public or deploying, rotate:
  - Consumer Secret on Connected App
  - User password
  - Security token

---

## Decisions log

I'll log major decisions here as I make them.

### 2026-05-23 — Going portfolio-first instead of company tool

Considered building this as an internal tool at my current company. Decided 
against because:
- Faster execution without stakeholder management
- Stays mine forever (no NDA, can showcase)
- More flexibility to make technically excellent choices
- Better signal for AI engineering job applications

Can revisit "deploy at current company" path after portfolio version is shipped.

### 2026-05-23 — Skip JHU Agentic AI course for now

Was considering the Johns Hopkins certificate but deferring. The 4-month build 
gives me practical experience + a real shipped artifact that's more credible 
than a certificate alone. Can revisit JHU after CRM Assistant is done if I 
want structured deepening on multi-agent patterns and observability.

### 2026-05-23 — Disabling Augment AI for this project

Disabled Augment AI in this workspace to maximize learning. Will re-enable in 
Week 8 (React frontend) where boilerplate is more repetitive and AI assistance 
doesn't hurt learning the same way.

---

## Daily log

### 2026-05-23

- ✅ Created GitHub repo: salesforce-ai-assistant (public)
- ✅ Cloned repo locally with VS Code
- ✅ Set up basic folder structure
- ✅ Confirmed .gitignore protects sf_secrets.py and .env files
- ✅ Wrote initial NOTES.md
- Next: Move existing Pydantic + async code into backend/ folder, then start Week 3

### Week 3 Day 1 — FastAPI setup

- Installed FastAPI, uvicorn, httpx
- Created backend/app/main.py with /health endpoint
- Server runs on http://localhost:8000
- /docs page auto-generates Swagger UI
- Tested endpoint via browser and curl
- Practiced git from terminal (add/commit/push)

Took: ~1.5 hours

Notes for future self:
- Always have 2 terminals: one for server, one for everything else
- Run uvicorn from inside backend/ folder, not project root
- favicon.ico 404 is normal — every browser asks for it