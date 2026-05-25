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

### Week 3 Day 3 — Path params, query validation, error handling (with debugging story)

What I built:
- GET /accounts/{id} — single account lookup with 404 handling
- GET /accounts/search/ — optional industry + revenue filters
- Upgraded /accounts/ with Query(ge=1, le=100) validation

DEBUGGING STORY (took ~45 min to resolve):

Symptom: All /accounts/* URLs returning 404, but /health worked.

Things I tried (didn't fix):
- Reordered routes so /{account_id} comes last (still correct to do, but not the issue)
- Cleared __pycache__ folders
- Restarted uvicorn cleanly

Actual root cause: main.py never imported or included the accounts router!
I had created routes/accounts.py but forgot to add to main.py:
   from app.routes import accounts
   app.include_router(accounts.router)

Without those two lines, FastAPI has no idea those routes exist.

Misleading clue: 422 validation errors look scary but are a SUCCESS signal — 
they prove your validation rules are working. `{"detail": [{"type": "...", "loc": ..."}]}` 
is FastAPI's standard error format. Status code 422 = "input failed validation."

Lessons:
1. Adding a new router requires TWO files: the routes file + main.py update
2. 404 vs 422 are different things — 404 = URL not registered, 422 = bad input
3. When debugging routes, check /openapi.json or /docs to see what FastAPI 
   actually knows about
4. The Problems tab in VS Code is your friend — silent import errors hide there

Next: Day 4 — lifespan management, dependency injection

### Week 3 Day 4 — Lifespan + dependency injection

What I changed:
- Added @asynccontextmanager lifespan function in main.py
- Salesforce client now created ONCE at startup, stored in app.state
- Created backend/app/dependencies.py with get_sf_client() function
- Endpoints now receive client via Depends(get_sf_client) instead of creating their own

Took: ~2 hours

Key concepts:
- @asynccontextmanager: code before `yield` runs at startup, after runs at shutdown
- app.state: container for app-wide shared resources
- Depends(): FastAPI auto-calls the function and injects the result into endpoints

Why this matters:
- Authentication happens ONCE, not per-request
- Endpoints are cleaner (no async with, no authenticate calls)
- Easy to swap MockSalesforceClient for real SalesforceClient later
- Standard production pattern — used in every real FastAPI app

Visible difference:
- Startup terminal shows "Starting Salesforce client..." / "Salesforce client ready."
- Shutdown terminal shows "Closing Salesforce client..."
- Each request is ~0.3s faster (no re-auth)


### Week 3 Day 5 — CORS + batch endpoint

What I added:
- CORSMiddleware in main.py (allows browser frontends to call this API)
- POST /accounts/batch endpoint that runs multiple queries concurrently
- New Pydantic models: BatchQueryRequest, BatchQueryResult

Took: ~2 hours

Key concepts:
- CORS = browser security feature that blocks cross-origin requests by default
- Middleware = code that runs before/after every request
- POST with JSON body for sending complex inputs (vs GET with query params)
- *request.queries = Python unpacking operator (list -> individual args)
- asyncio.gather (inside query_all) runs N queries concurrently

Visible results:
- 3 queries take ~0.8s total instead of ~2.4s sequential
- Access-Control-Allow-Origin: * header now present in all responses

Why this matters:
- Week 8 React frontend will be able to call this API without CORS errors
- Week 6 Claude tool use will use this pattern for multi-step queries

Next: Day 6 — pytest tests for all endpoints


### Week 3 Day 6 — Automated tests with pytest

What I added:
- pip install pytest pytest-asyncio
- Updated requirements.txt with testing dependencies
- Created backend/tests/test_endpoints.py with 14 tests
- Tests cover all endpoints: health, list, get by id, search, batch
- Tests cover both success (200) and error (404, 422) cases

Took: ~2 hours

Key concepts:
- pytest fixtures = reusable setup; @pytest.fixture decorator
- TestClient = simulates HTTP requests without running a real server
- `with TestClient(app) as client` triggers FastAPI lifespan correctly
- Tests are just functions starting with `test_`
- `assert` is the only "special" syntax

Verification:
- pytest tests/ -v runs all 14 tests in ~5 seconds
- All pass — confirms entire API works as expected
- Tested intentionally breaking /health → test caught it instantly

Why this matters:
- Catches regressions when I change code in Weeks 4-6
- Documents what each endpoint should do
- Recruiter signal — most portfolio projects lack tests
- Confidence to refactor knowing tests will catch breakage

Next: Day 7 — README polish + Week 3 retrospective


---

## Week 3 Retrospective

### What I built
- Full-featured FastAPI backend (6 endpoints + /docs)
- Pydantic models for type-safe Salesforce data
- Async architecture with concurrent query support
- Mock + real client pattern (same interface, swappable)
- Lifespan-managed singleton client
- Dependency injection pattern
- CORS middleware for future React frontend
- 14 pytest integration tests
- Professional documentation (README, TEST_URLS, NOTES)

### Total time invested
About 13 hours across 7 days. Roughly:
- Day 1 (setup + /health): 1.5h
- Day 2 (first real endpoint): 1.5h
- Day 3 (path params, validation, debugging): 2.5h
- Day 4 (lifespan + DI): 2h
- Day 5 (CORS + batch endpoint): 2h
- Day 6 (pytest tests): 2h
- Day 7 (README polish): 1.5h

### Biggest learning moments

**Day 3 — route ordering and the missing router registration**
Spent 45 minutes debugging a 404 on /accounts/. Two issues stacked:
1. The accounts router wasn't imported into main.py
2. /{account_id} wildcard route was matching before specific routes

Lesson: when adding a new router, BOTH files need changes (route file + main.py).
And specific routes go BEFORE wildcard routes always.

**Day 4 — lifespan + dependency injection clicked**
The shift from "create client per request" to "create client once, inject it"
felt magical. The endpoints became dramatically cleaner. This is the pattern
every production FastAPI app uses.

**Day 5 — async concurrency pays off visibly**
The batch endpoint demonstrated the value of asyncio.gather. 3 queries in 0.8s
instead of 2.4s. Will matter a lot when Claude makes multi-step queries.

**Day 6 — pytest is delightful**
Was expecting tests to be tedious. Actually fun — write a test, run it, see
it pass. Then deliberately break code to watch tests catch it. Now I trust
my codebase.

### What I'd do differently

- Set up the file structure (Day 0) more thoroughly. Some folders existed
  but weren't used until later — should have planned them upfront.
- Commit more frequently. Combined Day 4+5 into one commit because I forgot
  to commit Day 4 on its own. Not bad, but cleaner history would have been
  better.
- Run `git status` after every `git add` to verify what's staged. Avoided
  one weird "NOTES.md wasn't added" issue this way.

### What surprised me

- FastAPI's `/docs` page is genuinely magical. I spent more time there than
  I expected, and it became my primary testing tool.
- Pydantic does so much heavy lifting — validation, serialization, OpenAPI
  schema generation, all from type hints. I appreciate it more now.
- Async is much less scary than I thought. The mental model from Week 2
  carried over cleanly.

### What's next (Week 4)

Fix the Salesforce auth issue (External Client App → classic Connected App).
Once real data is flowing, all 14 tests should still pass (they test against
the mock, but the structure is identical).

Then Week 5: wire up Claude API for /chat endpoint.