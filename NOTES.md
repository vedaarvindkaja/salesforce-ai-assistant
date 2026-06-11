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

### 2026-05-28 — Strategic pivot: developer intelligence platform

Reframed the project from "generic Salesforce AI assistant" to "AI metadata
graph for Salesforce developers." Reasoning:

- The original framing ("AI-powered CRM assistant") competes directly with
  Salesforce's own AI tools, which target business users. I have no edge there.
- Where I do have edge: 10 years of Salesforce developer experience. The pain
  of changing a field and not knowing what'll break, of debugging Apex without
  full org context, of writing SOQL against an org I can't fully remember —
  these are problems I know intimately.
- Developer tools are easier to evaluate (you can immediately tell when output
  is wrong) which makes the build-measure-learn loop tighter.
- Open-core strategy: MCP server and metadata extractor open source, advanced
  features proprietary. Builds community credibility and leaves business optionality.

Five MVP capabilities (all developer-facing):
1. Metadata Q&A
2. Apex explanation/refactoring
3. SOQL generation with metadata awareness
4. Deployment impact analysis
5. Debug log analysis

Phase 2+ (admin, sales, support, cross-system) deferred. Captured in ROADMAP.md
section 8.

The full 15-week Phase 1 plan lives in ROADMAP.md. NOTES.md remains the journal;
ROADMAP.md is the plan; README.md is the public face.

---

## Daily log (continued)

### Week 4 Day 1 — Folder structure refactor

Reorganized the codebase into the layered structure from ROADMAP section 3:
- `app/services/` → `app/salesforce/` (data layer)
- `app/routes/` → `app/interfaces/rest_api/routes/` (consumer-facing)
- `services/salesforce_mock.py` → `salesforce/mocks/rest_mock.py`
- `services/salesforce.py` → `salesforce/rest_api.py`

Relaxed `dependencies.get_sf_client()` return type from `MockSalesforceClient`
to `Any`. Reasoning: Day 3-5 swaps in the real client; the dependency function
shouldn't need to know which. Eventually this becomes a Protocol once both
clients exist and the contract is clear.

All 14 tests still passing after the move.

Took: ~2.5 hours (budget was 1.5-2h).

**Debugging story — silent file clobbering:**

After `git mv` correctly moved `salesforce_mock.py` and `salesforce.py` to
their new locations, both files got silently emptied. Tests started failing
with `ImportError: cannot import name 'MockSalesforceClient' from
'app.salesforce.mocks.rest_mock'` — Python found the module but the file was
empty.

Recovery: `git checkout -- <path>` restored the content from the staged
rename. Git knew where the file went and what was in it; the on-disk version
was the thing that got corrupted.

Root cause (best guess): VS Code had the old paths open in tabs. After
`git mv`, the editor's in-memory buffers and the on-disk files were out of
sync. Some interaction — a save prompt, an extension auto-formatting, a
tab close — overwrote the new location with an empty buffer.

Lessons:
1. **Close all VS Code tabs before doing `git mv` on those files.** The shell
   is the source of truth during refactors. The editor only confuses things.
2. **Trust `git status`.** When it shows `renamed:` + `deleted:` on the same
   file, that's Git telling you "I moved this, then someone deleted it." The
   message reads as confusing but it's precise.
3. **`git checkout -- <path>` restores a staged-but-deleted file** without
   undoing the rename. Useful muscle memory.
4. **`git mv` preserves history**; drag-and-drop in File Explorer shows up
   as delete-plus-add. Always use `git mv` for structural refactors.

Verifying file sizes after refactors is a 10-second sanity check that catches
silent corruption that tests might miss (a clobbered docstring doesn't fail
tests).

### Week 4 Day 2 — Sweep, docs, merge

What I did:
- Searched the codebase for stragglers referencing old paths (`app.services`,
  `app.routes`). Zero real hits. Three false positives — `NOTES.md` historical
  entry (correct to leave alone), README's `models/salesforce.py` reference
  (different file, false match), ROADMAP's target structure diagram (also
  references the Pydantic models file).
- Rewrote README.md to reflect the strategic pivot and the new architecture.
  Kept the "What's working today" section honest — still 6 REST endpoints with
  mock data, but reframed as foundation for the intelligence layer rather than
  as the product.
- Updated this NOTES.md (Day 1 entry + this Day 2 entry + the strategic pivot
  decision).
- Merged `week-4-refactor` branch into `main` and pushed.

Took: ~1.5 hours.

Key concept reinforced — **separation of "history" docs vs "current state"
docs**. NOTES.md is a journal: past entries describe what was true at the
time and never get edited. README.md is current state: rewritten freely as
the project changes. ROADMAP.md is the plan: updated when priorities shift,
not when individual days complete.

Confused these once during the sweep — almost edited a Week 3 Day 3 NOTES
entry referencing `app.routes` (the old import path). Caught myself in time.
That entry is a record of what I knew when I knew it; falsifying it would
erase the learning trail.

Next: Day 3 — Salesforce Connected App + OAuth 2.0 Web Server Flow.

### Week 4 Day 3 — Salesforce OAuth 2.0 Web Server Flow with PKCE

What I built:
- `app/salesforce/oauth_models.py` — Pydantic models for OAuth responses
- `app/salesforce/auth.py` — OAuth protocol logic: PKCE generation,
  authorize URL building, code-for-token exchange, refresh token support
- `app/salesforce/token_storage.py` — JSON file persistence for tokens
- `app/interfaces/rest_api/routes/auth.py` — /auth/login, /auth/callback,
  /auth/status endpoints
- New Salesforce-side: External Client App with Web Server Flow + PKCE
  + Refresh Token Rotation enabled

End-to-end verified: clicked /auth/login → redirected to Salesforce login →
logged in → clicked Allow → redirected back to /auth/callback → tokens
exchanged and saved to tokens.json → used access_token to call /sobjects/
endpoint → got back 1241 SObjects from real org schema.

Took: ~5 hours (across Day 3 Part 1 + Part 2, including the External
Client App setup and 10-minute propagation wait).

### Strategic pivot: External Client App over Connected App

Started Day 3 planning to use a classic Connected App. Salesforce's UI
no longer shows the "New Connected App" button in newer org versions —
only "New External Client App." Researched the current state of External
Client Apps (mid-2026): they now fully support Web Server Flow with PKCE,
the previous limitations were only on the deprecated username-password
flow which we weren't using anyway.

Decision: switched to External Client App. It's the forward path Salesforce
is steering everyone toward, and using a deprecated path on a portfolio
project sends the wrong signal. PKCE adds ~15 lines of Python; Refresh
Token Rotation means we must replace the stored refresh_token after each
refresh (Phase 1 doesn't refresh yet, but Day 5+ will).

Captured as ADR in the Day 3 commit message; should formalize into
docs/decisions/ in Week 14.

### Key technical concepts (Apex-developer perspective)

- **PKCE (Proof Key for Code Exchange)** — generate a random verifier
  server-side; send sha256(verifier) base64url-encoded as the "challenge"
  in the authorize URL; send the original verifier when exchanging the
  code for tokens. Salesforce verifies they match. Prevents an attacker
  who intercepts the redirect from completing the flow.

- **Server-side flow state** — the PKCE verifier must persist between
  /auth/login (when we generate it) 


  ### Week 4 Day 4 — Real SalesforceClient + refresh-on-401

What I built:
- `app/salesforce/rest_api.py` — real OAuth-backed client replacing the
  Week 2 broken username-password code
- `app/main.py` lifespan branches on USE_MOCK_DATA env var
- `tests/test_salesforce_client.py` — 5 tests using httpx.MockTransport
- Fix in `tests/test_endpoints.py` — forced USE_MOCK_DATA=true via
  monkeypatch so tests are hermetic regardless of .env state

End-to-end verified: yesterday's access_token had expired (24+ hours old);
hitting /accounts/ today triggered refresh-on-401 automatically. New
tokens saved to disk, retry succeeded, 10 real accounts returned.

Took: ~3 hours (within 2-3 hour budget).

### Architecture decision: dependency injection for HTTP client

Discovered a bug while writing tests: `auth.refresh_access_token()` was
creating its own `httpx.AsyncClient` internally. This made it impossible
to inject a MockTransport for testing — every test that triggered refresh
was secretly hitting real Salesforce, which (correctly) rejected our
fake `OLD_REFRESH_TOKEN` string.

Two options:
- A: Pass httpx.AsyncClient as an optional parameter (dependency injection)
- B: Use a module-level shared client (hidden global state)

Picked A. Honest about the function's dependencies, testable, reuses
the SalesforceClient's connection pool in production. The Apex parallel
is `HttpCalloutMock` injected via `Test.setMock()` — same idea, different
plumbing.

This is the kind of bug you only catch by writing tests. Without tests,
it would have lurked until Week 8-9 when Claude tool use makes rapid
refresh calls and I'd have spent hours debugging "why are my tokens
randomly invalid."

ADR-worthy. Captured in commit message; formalize in docs/decisions/
during Week 14 polish.

### Lesson — tests must be hermetic

Initial test run failed 7/19 tests after Day 4 changes. Cause: my .env
had USE_MOCK_DATA=false from the real-mode live test, and TestClient(app)
inherited that env var. Tests were running against my real org, returning
"Pyramid Construction" instead of "Edge Communications," failing on
assertion mismatches.

Fix: `monkeypatch.setenv("USE_MOCK_DATA", "true")` in the test fixture.
Tests now set up their own environment regardless of .env.

The principle: **tests should produce the same result on every machine,
in every environment.** Apex enforces this via @isTest semantics (Custom
Settings hidden, callouts blocked unless mocked). Python doesn't enforce
it — you have to design hermeticity in deliberately.

### Key technical concepts

- **Duck typing for swappable clients**: Mock and Real clients share no
  inheritance, just identical method signatures. Python's "if it quacks
  like a duck, treat it like one." For Phase 1 with 2 clients and ~5
  methods this is fine. Phase 2+ will probably need a Protocol or ABC
  to formalize the contract.

- **`Optional[httpx.AsyncClient] = None` pattern**: When a function might
  manage its own resource or be given one, `Optional[T] = None` with an
  `if param is not None` branch is the Pythonic idiom. Cleaner than
  overloading or two separate functions.

- **`monkeypatch` fixture**: pytest's built-in fixture for temporarily
  setting env vars, swapping module attributes, etc. Auto-reverts after
  the test. Use this; don't manually save/restore in tearDown.

- **`httpx.MockTransport`**: lets you fake every HTTP call at the
  transport layer without changing your code. The function `handler`
  receives every `httpx.Request` and returns whatever `httpx.Response`
  you want. Much cleaner than mocking individual `.get`/`.post` calls.

- **Refresh Token Rotation in code**: every `_refresh_tokens()` call
  saves the new refresh_token from Salesforce's response. If you forget
  this step, the second refresh fails because Salesforce invalidated the
  old refresh_token the moment you used it.

### Race condition I'm aware of but parking

If two concurrent `query()` calls both get 401, both call
`_refresh_tokens()`. The second one might use an already-rotated
refresh_token (now invalid), causing a refresh failure that propagates
to the user as an error.

For Phase 1 single-user this won't happen often — UI sessions don't
fire dozens of concurrent queries. Documented in the rest_api.py
docstring. Phase 2 multi-tenant needs an `asyncio.Lock` around refresh.

Apex avoids this entirely because Named Credentials serialize refreshes
at the platform level. Trade-off: we get control + responsibility.

### What's next (Day 5)

Day 4 was the heavy lift; Day 5 is cleanup:
- Update README.md to reflect Day 4 reality (real Salesforce client
  working, tokens.json file, USE_MOCK_DATA env var)
- Update TEST_URLS.md with the /auth/* endpoints
- Verify the full Week 4 retrospective bullets
- Decide on Week 5 starting point (Metadata API client)

---

## Week 4 Day 5 — Documentation polish

What I did:
- Updated README.md to reflect Week 4 complete state (OAuth working,
  real client, 19 tests, USE_MOCK_DATA toggle, hermetic test discipline)
- Updated TEST_URLS.md to reflect mock vs real mode behavior, added
  /auth/* endpoint tests, refresh-on-401 manual test instructions
- Wrote this Week 4 retrospective
- Decided to skip CHANGELOG.md (deferred to Week 14 launch prep —
  NOTES.md is already doing that doc's job for now)

Took: ~1.5 hours.

---

## Week 4 Retrospective

### What I built

A complete authentication and data-access layer for Salesforce:

**Architecture (Days 1-2):**
- Refactored Week 3's flat structure into layered architecture
  (salesforce/ → data layer, intelligence/ → reserved, interfaces/ →
  consumer-facing)
- Established the pattern that lets Week 11 add an MCP server without
  disrupting anything else

**OAuth 2.0 Web Server Flow with PKCE (Day 3):**
- External Client App created in Salesforce (after discovering Connected
  Apps are being phased out)
- PKCE generator using `secrets` + `hashlib` + `base64.urlsafe_b64encode`
- /auth/login → redirect to Salesforce
- /auth/callback → code exchange, token persistence
- /auth/status → diagnostic endpoint
- Token storage as JSON file (gitignored), keyed for future SQLite migration

**Real SalesforceClient with refresh-on-401 (Day 4):**
- Replaced Week 2's broken username-password client
- Bearer token authentication on every request
- Transparent refresh-on-401 with single retry
- Refresh Token Rotation persistence (new refresh_token saved each refresh)
- Mock + Real clients swappable via USE_MOCK_DATA env var
- 5 new tests using httpx.MockTransport for the auth lifecycle

**Documentation (Days 2 and 5):**
- README reframed around developer intelligence platform vision
- TEST_URLS.md updated with mock/real mode distinction, auth endpoints,
  manual refresh testing
- NOTES.md captures every day's learnings + this retrospective

### Total time invested

About 13 hours across 5 working days. Roughly:
- Day 1 (refactor): 2.5h
- Day 2 (sweep + docs + merge): 2h
- Day 3 (OAuth Connected App + Python flow): 5h
- Day 4 (real client + tests): 3h
- Day 5 (final docs polish): 1.5h

Original budget was 15 hours; came in slightly under.

### Biggest learning moments

**Day 3 — External Client App pivot**

Started planning to use a classic Connected App per Salesforce's older
documentation. Discovered the UI no longer surfaces "New Connected App"
in newer org versions. Researched current state, realized External
Client Apps now fully support Web Server Flow + PKCE, and pivoted.

The lesson: documentation ages. Always verify Salesforce platform
guidance against the current org UI before committing to a path. The
correct answer 18 months ago is sometimes the wrong answer today.

**Day 3 — PKCE in code, conceptually**

Worth internalizing: PKCE is a clever solution to a specific problem
(intercepted auth codes), and the math is simpler than the name suggests:
1. Random 32-byte verifier → kept server-side
2. SHA-256 of verifier → base64url-encoded → sent in /authorize URL
3. Verifier sent again in /token exchange → Salesforce verifies they match

The Apex parallel is `Crypto.generateDigest('SHA-256', ...)` +
`EncodingUtil.base64Encode()` + manual replace of `+`/`/`/`=` for the
base64url alphabet. Python's `base64.urlsafe_b64encode` does the
character substitution for us; only the trailing `=` padding needs to
be stripped.

**Day 4 — Tests caught a real bug**

The biggest single architectural lesson of Week 4. While writing the
refresh-on-401 tests, two of them failed with the literal Salesforce
error "unknown_error — retry your request." Investigated: `auth.refresh_access_token()`
was creating its own `httpx.AsyncClient` internally, so my MockTransport
never intercepted refresh calls — they went to real Salesforce, which
correctly rejected my fake "OLD_REFRESH_TOKEN" string.

Fix: refactored both `exchange_code_for_tokens` and `refresh_access_token`
to accept an optional `httpx.AsyncClient` parameter. Caller passes their
own (real production or mocked test). Now tests can inject a MockTransport
and refresh stays fully fake.

This is exactly the kind of bug you only catch by writing tests.
**Hidden dependencies are testability killers.** The Apex parallel is
`HttpCalloutMock` — Test.setMock() injects a fake HTTP responder, and
your production code doesn't need to know it happened. Python doesn't
give you Apex's free injection; you have to design it in deliberately
via function parameters.

**Day 4 — Tests must be hermetic**

After Day 4's code worked end-to-end against my real org (USE_MOCK_DATA=false),
running `pytest tests/` failed 7/19 tests. They were checking for
"Edge Communications" (mock data) but getting "Pyramid Construction"
(real org data) because the test process inherited my `.env`.

Fix: `monkeypatch.setenv("USE_MOCK_DATA", "true")` in the TestClient
fixture. Tests now produce the same result regardless of `.env` state.

The principle: **tests should produce the same result on every machine,
in every environment.** Apex enforces this via `@isTest` semantics; Python
doesn't, so you have to design hermeticity in deliberately.

### Architectural decisions made this week

These are the principal-architect-worthy decisions worth flagging for
future reference (formalize as ADRs in docs/decisions/ during Week 14
polish):

1. **Layered architecture** (`salesforce/`, `intelligence/`, `interfaces/`)
   over feature-flat folders. Day 1.

2. **External Client App** over classic Connected App. Day 3. Reasons:
   Salesforce phasing out Connected Apps in newer orgs; ECAs now have
   full Web Server Flow support; PKCE/RTR mandates apply to both anyway.

3. **In-memory dict for OAuth flow state** (PKCE verifier between
   /auth/login and /auth/callback) over signed cookies. Day 3. Phase 1
   is single-user local; Phase 2 multi-tenant will need a real session
   store.

4. **Duck typing for Mock vs Real client** over a formal Protocol/ABC.
   Day 4. Pragmatic for 2 clients with ~5 methods; Phase 2's metadata
   API client will likely justify a Protocol.

5. **Design B (refresh on 401, retry once)** over Design A (fail loudly,
   require caller to handle) or Design C (background refresh task). Day 4.
   Right balance of self-healing and simplicity.

6. **Dependency injection for httpx.AsyncClient** over hidden internal
   creation. Day 4. Forced by needing testability; also a production
   win (connection pool reuse during refresh).

### What I'd do differently

- **More frequent commits.** Day 3 was a single huge commit (737 lines).
  Should have committed after oauth_models.py, then auth.py, then routes,
  etc. Cleaner history; if something broke I could revert one piece.

- **Verify the startup log line every time.** When uvicorn `--reload`
  didn't pick up my Step 2 main.py change in Day 4, I should have caught
  it from the startup line saying "mock for now" (old code) instead of
  "MOCK" or "REAL" (new code). Wasted ~10 minutes assuming everything
  was up-to-date when it wasn't.

- **Treat the editor as untrustworthy during refactors.** Day 1's silent
  file clobbering should have taught me to close VS Code tabs of files
  I'm about to `git mv`. The shell is the source of truth during
  structural changes; the editor is just a viewer.

- **Smaller principal-architect moments earlier.** Several decisions I
  made this week (in-memory flow dict, duck typing, etc.) deserved
  explicit ADR-format flagging when I made them, not after.

### What surprised me

- **httpx.MockTransport is delightful.** I expected mocking HTTP in
  async Python to be painful. It's not — you write a function that
  takes an `httpx.Request` and returns an `httpx.Response`, pass it as
  `transport=MockTransport(handler)` on the AsyncClient, done. No
  monkey-patching individual methods, no fragile string matching.

- **PKCE math takes 4 lines of Python.** The acronyms make it sound
  intimidating. It's actually trivial: random string → sha256 → base64url
  → strip padding.

- **My old expired access_token was the perfect test case for refresh.**
  Day 4's live test exercised refresh-on-401 naturally because the
  token from Day 3 was 23 hours old. If I'd built this with fresh
  tokens, I wouldn't have seen the refresh path execute until Day 5+.

- **Pydantic v2 deserialization continues to be magic.** No JSON.parse,
  no manual field assignment, no validation logic. Just call
  `Model.model_validate_json(text)` and either get a typed object or a
  clear error. Compared to Apex's `JSON.deserialize` + manual null checks,
  this is a productivity multiplier.

### What's next (Week 5)

Per ROADMAP.md Section 4, Week 5 is **metadata extraction**:

- Build `app/salesforce/metadata_api.py` — Metadata API client
  (list_metadata, read_metadata, describe_metadata)
- Build `app/salesforce/tooling_api.py` — Tooling API client (Apex
  classes, Flow definitions, validation rules)
- Pull comprehensive org metadata to local JSON files
- Generate realistic mock org structure for testing
- Tests for both APIs

20 hours allocated in ROADMAP. Realistically might be 15-18 given Week 4
came in under budget. The architecture from Week 4 (mock+real pattern,
hermetic tests, dependency injection for HTTP client) carries forward
directly — Week 5's metadata API client is structurally identical to
Week 4's REST client, just hitting different endpoints.

The Salesforce Metadata API is SOAP-based (XML, not JSON), which will
be the main new wrinkle. Either parse XML manually, use a library, or
use the simpler subset of the Tooling API which IS REST/JSON. Decision
for Day 1 of Week 5.

---

## Daily log (continued — Week 5)

### Week 5 Day 1 — Layered HTTP client refactor (ADR-003)

What I did:
- Wrote three ADRs into `docs/decisions/`:
  - ADR-001 (backfill): layered architecture
  - ADR-002 (backfill): External Client App over classic Connected App
  - ADR-003 (today): split SalesforceClient into HTTP layer + API layer
- Refactored Week 4's monolithic `SalesforceClient` into two classes:
  - `SalesforceHTTPClient` (new file `app/salesforce/http_client.py`) —
    owns httpx instance, token state, refresh-on-401, RTR persistence
  - `RestAPIClient` (renamed from `SalesforceClient` in
    `app/salesforce/rest_api.py`) — holds an HTTPClient, exposes
    domain methods `query()` / `query_all()`
- Updated `app/main.py` lifespan to construct `RestAPIClient` for real mode
- Migrated `tests/test_salesforce_client.py` to test the HTTP layer
  directly (refresh-on-401 is HTTP-layer behavior; testing it through the
  REST wrapper would be testing the wrong thing)
- Kept `SalesforceClient = RestAPIClient` alias for backwards compatibility;
  plan to remove in Week 6 when callsites have settled
- All 19 tests still pass; manual verification in both mock and real modes
  confirmed end-to-end behavior unchanged

Took: ~[FILL IN ACTUAL TIME] hours.

### Why the refactor today rather than later

The trigger was Week 5 Day 2's planned Tooling API client. Without the
refactor, ToolingAPIClient would either duplicate the auth+refresh logic
or reach into RestAPIClient's privates — both bad. With the refactor,
ToolingAPIClient simply holds the same SalesforceHTTPClient instance
and gets refresh-on-401 for free.

Captured in ADR-003. The key insight: Week 4's SalesforceClient was
secretly doing two jobs (HTTP lifecycle + REST API operations) that
only looked like one because there was one consumer. The moment a
second consumer appeared on the horizon (Tooling, then Metadata,
then MCP), the seam became obvious.

### The "quality over timebox" moment

I originally proposed the refactor with a 90-minute hard cutoff: if it
takes longer, fall back to composition-without-refactor. Pushed back
on that explicitly — Phase 1 is the foundation for Phase 2+, and a
shortcut here compounds across every future consumer of Salesforce APIs.

Updated ADR-003 to reject timeboxing as a forcing function. The right
discipline is "if it's getting messy, slow down and address it cleanly,"
not "if the clock runs out, ship a worse design."

This is the kind of self-correction I want to keep doing. Engineer
fatigue + AI tendency to optimize for the conversational close = real
risk of accepting shortcuts that look reasonable in the moment. The
defense is to articulate the standard up front and refer back to it.

### Key technical concepts (Python ↔ Apex)

- **Composition over inheritance.** Python idiom: when class A "uses"
  class B's functionality, hold a B instance rather than subclassing.
  RestAPIClient holds a SalesforceHTTPClient — it doesn't extend it.
  Apex would lean toward inheritance because dependency injection is
  awkward without a framework; Python's first-class objects and
  constructor flexibility make composition the default.

- **Class aliasing as rename safety net.** The line
  `SalesforceClient = RestAPIClient` at module bottom creates a second
  name pointing to the same class. Lets old imports keep working during
  a transition. Apex has no equivalent — class renames are atomic across
  all callsites or they don't compile.

- **Keyword-only arguments via `*`.** The `request()` signature is
  `request(self, method, path, *, params=None, json=None)`. The bare `*`
  forces `params` and `json` to be passed by name, never positionally.
  Apex doesn't have this; you'd use method overloading or a request
  struct.

- **Sharp layer responsibilities.** The new HTTP client's job is to
  return raw httpx.Response objects — it does NOT call raise_for_status.
  The REST client decides what counts as an error and parses bodies.
  This separation matters: a Tooling client might handle 400s differently
  than a REST client (e.g., parse a Tooling-specific error envelope), and
  it shouldn't have to undo the HTTP layer's opinion to do so.

### Scope discovery I noticed but parked

The mock client (`MockSalesforceClient`) stays monolithic — I deliberately
did NOT split it into a mock HTTP layer + mock REST layer. Reasoning is
in ADR-003's "Mock client asymmetry (explicit)" subsection. Briefly: the
mock doesn't do HTTP, so a mock HTTP layer is ceremony without function.
Duck typing means the asymmetry is invisible to consumers.

If Phase 2 multi-tenant needs to test token-refresh races or per-user
session state, that's when I'd split the mock. Not before.

### What I'd do differently

- **Could have written the ADRs in commit messages first**, then promoted
  to docs/decisions/ when the structure settled. Writing all three as
  fresh markdown files up front meant some back-and-forth as I refined
  ADR-003 mid-session. Eith

  ### Week 5 Day 2 — ToolingAPIClient + first real-org verification

What I did:
- Built Pydantic models for the 6 core Tooling API record types in
  `app/models/tooling.py`:
  - ApexClass, ApexTrigger, EntityDefinition, CustomField,
    ValidationRule, FlowDefinition
  - Plus a generic `ToolingQueryResponse[T]` envelope using
    Pydantic v2 + Python generics — one wrapper, six uses
- Built `ToolingAPIClient` in `app/salesforce/tooling_api.py`:
  - 6 typed query methods (one per record type)
  - `query_raw()` escape hatch for ad-hoc SOQL
  - `extract_all_for_graph()` — fires all 6 queries concurrently
    via `asyncio.gather`
  - REQUIRES a SalesforceHTTPClient in constructor (no fallback
    to internal creation — composition is mandatory)
- 10 new unit tests in `tests/test_tooling_api.py` using
  `httpx.MockTransport`
- Real-org verification script at `scripts/verify_tooling_api.py`
  with the `python -m scripts.verify_tooling_api` invocation pattern
- All 29 tests passing (14 endpoints + 5 HTTP client + 10 tooling)

Took: ~4.5 hours.

### The headline number — concurrent extraction proved out

Real-org verification ran `extract_all_for_graph()` against my dev
org. Six Tooling API queries fired concurrently via `asyncio.gather`:

| Query | Sequential (sum) | Concurrent (gather) |
|---|---|---|
| apex_classes (42) | 0.29s | |
| apex_triggers (1) | 0.20s | |
| entity_definitions (211) | 0.26s | |
| custom_fields (57) | 0.19s | |
| validation_rules (5) | 0.13s | |
| flow_definitions (6) | 0.12s | |
| **TOTAL** | **1.19s sum** | **0.27s wall time** |

That's a 4.4× speedup — concurrent wall time is roughly the time of
the slowest single query, which is exactly what `asyncio.gather` is
supposed to deliver. This matters enormously for Week 8 when Claude
tool use chains 3-4 metadata queries per user question. The Apex
parallel (Continuation API) only works from Visualforce/Lightning
contexts and is significantly more complex.

### The FlowDefinition.MasterLabel saga — why we verify against real orgs

The lesson of the day. First real-org run blew up:

    pydantic_core.ValidationError: 5 validation errors for
    ToolingQueryResponse[FlowDefinition]
    records.0.MasterLabel
      Input should be a valid string [type=string_type,
      input_value=None, input_type=NoneType]

Five of five FlowDefinitions in my dev org returned `MasterLabel=null`,
breaking the non-Optional `MasterLabel: str` declaration.

My initial hypothesis: "system-generated or managed-package flows
bypass the 'label required' UI." Fixed by making MasterLabel
Optional[str] = None, re-ran the script.

Second run revealed my hypothesis was wrong. The flows weren't
system-generated — they had clearly meaningful names:
- Update_Contact_Phone_When_Account_Phone_Updates
- Opportunity_Approval_Orchestrator
- Evaluate_Pricing_Need
- URSIP_Opportunity_After_Save
- PlatFormEventFlow_MuleSoft

All ACTIVE flows. All with null MasterLabel. The actual finding was
different: **MasterLabel via the Tooling API's FlowDefinition SOQL
path is unreliable across the board, not just for edge cases.** The
real label likely lives on the `Flow` record (the version), not on
`FlowDefinition` (the wrapper). The schema exposes it but the data
path doesn't populate it.

This is a real Salesforce platform quirk that anyone building Tooling
API tools needs to know. Documented in the model docstring and the
test fixture. Future engineers reading the code will learn the lesson
without having to hit the failure themselves.

Implications for Week 6's graph (parked for Day 1 of Week 6):
- Use `DeveloperName` as the graph node's display label (reliable —
  every flow had a meaningful one)
- OR fetch the Flow record at `ActiveVersionId` for the real label
- Decision deferred until the graph builder needs labels

The Apex-developer takeaway: even 10 years of Salesforce experience
doesn't immunize you against platform quirks in less-common APIs.
The Tooling API is "REST/JSON like the data API" until it isn't.
**Real-org verification is non-negotiable for every new API surface.**

### Key technical concepts (Python ↔ Apex)

- **Pydantic v2 generics.** `ToolingQueryResponse[ApexClass]` is one
  class doing six jobs via `Generic[T]` and `TypeVar`. The runtime
  type system tracks which T is bound; `.records` is typed
  `list[ApexClass]` for one and `list[FlowDefinition]` for another.
  Apex generics are restricted to platform types (List, Map, Set);
  you can't declare your own generic class, so you'd duplicate the
  response wrapper 6 times.

- **`asyncio.gather` vs Apex Continuation.** Python's `gather`
  accepts N coroutines and waits for all in parallel. Apex's
  Continuation API does the same thing but only in VF/LWC contexts,
  requires explicit callback wiring, and limits you to 3 callouts.
  Python's version is 1 line of code, no context restrictions, no
  callout count limit.

- **Keyword-only arguments via `*` in def.** The `query_apex_classes`
  signature is
  `def query_apex_classes(self, *, include_body=False, where=None,
  limit=None)`. The bare `*` forces all subsequent parameters to be
  passed by name. `query_apex_classes(True, "x", 10)` won't compile;
  `query_apex_classes(include_body=True, where="x", limit=10)` is
  required. Self-documenting API design. Apex has no equivalent;
  you'd use method overloading or a request struct.

- **Required composition (no default constructor fallback).**
  ToolingAPIClient takes `http: SalesforceHTTPClient` as required,
  not optional. There's no "create my own HTTP client if you didn't
  give me one" path. This forces correct usage (the lifespan owns
  the HTTP client; consumers borrow it) and prevents the hidden-state
  bug pattern from Week 4 Day 4. RestAPIClient still has the optional
  fallback for backwards compatibility — to be cleaned up in Week 6.

- **The `python -m module.path` convention.** Project scripts live
  in `backend/scripts/` and are invoked as
  `python -m scripts.verify_tooling_api`, not
  `python scripts/verify_tooling_api.py`. The latter doesn't find
  `app/` in the import path. The former treats `backend/` as the
  package root and resolves imports correctly. This is the standard
  Python pattern — adopt it for every script we add. Apex has no
  equivalent because the platform owns invocation; you never write
  the entry point.

### What I'd do differently

- **Earlier reality-check on the mock data shapes.** I wrote mock
  responses that assumed Salesforce's documented shape was the
  actual shape. The FlowDefinition.MasterLabel failure could have
  been caught by a 10-minute spike into a real org BEFORE writing
  the Pydantic model. Lesson for Day 3+: when adding new metadata
  types, query one record from the real org with the relevant
  SObject fields BEFORE designing the model. The 5 minutes saves
  iteration cycles later.

- **Sharing verification output more reliably.** Partway through
  Day 2 I told Claude "29 tests passed" without sharing the
  verification script's output. Claude correctly pushed back — tests
  prove the unit-level code works against mock data; the script
  proves it works against real Salesforce. They're different
  proofs. Adopting the discipline: every real-world verification
  step produces output that gets shared, not just a thumbs-up.

- **Initial hypothesis was wrong; second look corrected it.** When
  the MasterLabel failure first surfaced, I (well, Claude) jumped
  to "system-generated flows" as the cause. The second run showed
  that was wrong — the real finding was "MasterLabel is broadly
  unreliable on this query path." First findings deserve a second
  pass before they become committed conclusions. The commit
  history captures both: the first commit makes MasterLabel
  Optional with the wrong reason, the second commit corrects the
  reasoning. That's the right shape for engineering history.

### What surprised me

- **211 EntityDefinitions in a dev org.** I expected ~50-80. Real
  orgs (even fresh dev orgs) have a lot of standard objects
  including ones I've never used. Week 6's graph will need to be
  thoughtful about whether to include all of them or filter to
  "objects with user-relevant metadata."

- **Concurrent extraction at 0.27s wall time.** I expected 0.5-1.0s;
  it came in under. Asyncio's overhead is genuinely small, and
  Salesforce's API can serve 6 concurrent Tooling queries from one
  authenticated session without rate limiting.

- **Only 1 ApexTrigger in this org.** This dev org is metadata-heavy
  (211 objects, 57 custom fields) but Apex-light. For Week 6's graph,
  the demo questions might lean more on "what depends on this field"
  than "what does this trigger touch" depending on the org. Good to
  know now.

- **Pydantic's error messages are excellent.** The ValidationError
  output told me the field path (`records.0.MasterLabel`), the
  expected type (str), the actual value (None), and gave a docs
  link. In Apex this would be a vague `JSONException`. Python's
  ecosystem is genuinely better here for the dev-tool category we're
  building.

### Scope I noticed but parked

- **`EntityDefinitionId` / `TableEnumOrId` inconsistency.** Some
  records reference parent objects by API name ("Account"), others
  by Id ("01IdM00000EO9Zy"). Same conceptual relationship, two
  different shapes. Week 6's graph builder needs to normalize. Not
  a Day 2 problem.

- **ValidationRule metadata expansion.** ErrorConditionFormula
  isn't a top-level field; it lives under `Metadata` and requires
  a different SOQL query shape. Day 3 or Week 6 will decide.

- **Whether to use DeveloperName vs ActiveVersion's label as the
  Flow display name in the graph.** Parked for Week 6.

- **Pagination.** `nextRecordsUrl` would fire if we hit >2000
  records in one query. Day 2 doesn't follow pagination; the
  `ToolingQueryResponse` model captures `nextRecordsUrl` for later.
  Phase 2 problem.

### What's next (Day 3)

Day 3 of ROADMAP Week 5 is more Tooling API + Metadata API integration.
With Day 2's foundation solid, Day 3 options are:

1. **Add ValidationRule metadata expansion** so the parser (Week 7)
   can extract field references from ErrorConditionFormula
2. **Add FieldDefinition** for standard-field coverage (Phase 1
   currently only does CustomField)
3. **Start Day 5-6's storage layer** — write extracted JSON to
   `app/intelligence/graph/extracted/` per-type files

Recommended Day 3 plan (will confirm at start of next session):
spike on ValidationRule metadata expansion (smallest scope), then
move into storage. The graph (Week 6) needs both formula contents
and persisted JSON to work.

Day 2 done. Foundation for Week 5 is solid: real-org-verified Tooling
API client, 29 tests green, clean commits, documented platform quirks.


### ADR-004 — SQLite connection strategy for MetadataCache

**Decision:** Per-operation connections (`with sqlite3.connect(...)` inside
each method) rather than a lifespan-owned persistent connection.

**Alternatives considered:**
- Lifespan-owned connection (same pattern as ADR-003's SalesforceHTTPClient)
- Connection pool (overkill for single-user local SQLite)

**Why this is the OPPOSITE call from ADR-003:**
ADR-003 chose a persistent HTTP connection because Salesforce auth state
(tokens, refresh lifecycle) must live somewhere across requests — you
can't recreate it per-operation without re-authenticating.

SQLite has no equivalent state problem. A file-based database carries
its own persistence; the connection is just a door into it. Opening and
closing that door per-operation costs microseconds and buys:
- No connection leak risk (context manager guarantees close)
- No threading concerns (each operation is isolated)
- Simpler code (no lifespan wiring needed)

The contrast is the lesson: persistent resources are justified when
they own state that must survive across operations. When the resource
is stateless (SQLite file, simple HTTP GET with no auth), per-operation
is cleaner.

**Trade-off accepted:** If Phase 2 adds concurrent writes from multiple
users, WAL mode + connection pooling (via `aiosqlite`) becomes the right
answer. Not a Phase 1 problem.

## ADR-005 — Cache partition key = org instance_url, read via load_tokens()

**Decision:** Key the cache on `instance_url`, obtained by calling
`load_tokens()` in the extraction script — the same loader the HTTP client
uses.

**Alternatives considered:** (a) hardcode `"default"` — silent cross-org
collision risk; (b) `getattr` fallback chain on the client — untraceable,
and doesn't work (instance_url isn't a public client attr); (c) reach into
`http._tokens.instance_url` — couples to client internals; (d) explicit
`--org-key` CLI arg — correct but redundant when load_tokens() has it.

**Trade-offs:** Reading tokens a second time is a negligible duplicate file
read for a once-per-extraction script. In exchange: no private-attr
coupling, no manual arg, key is provably the real org.

**Why:** A partition key must be known and explicit, never best-effort.
Best-effort is fine for a display label (can be null, who cares) and wrong
for a key (a wrong key corrupts silently across orgs).

---

## ADR-006 — String-scan before AST parse (reference analyzer v1)

**Decision:** v1 reference analysis is word-boundary regex over cached Apex
source, not AST parsing.

**Alternatives considered:** (a) AST parse via Apex grammar (ANTLR) now;
(b) Salesforce's `MetadataComponentDependency` API.

**Trade-offs:** Regex ships today, gives the useful 80%, but has known
false positives (comments, string literals) and false negatives (dynamic
refs, `obj.get('Field')`, dynamic SOQL). AST is exact but a multi-day
grammar integration (Week 7's job). The dependency API is exact and free
but covers only certain component types — evaluate Week 6.

**Why:** Day 4's goal was a working answer, not a perfect one. A
documented-limitation scanner that runs beats a perfect parser that's
half-built at Week 15. Limitations are named in output + docstring, so the
demo narrates them as deliberate scope.

---

## Week 6 parked items

- Rank production classes above test classes in reference results. Real-org
  finding: searching `Account` ranked 5 `*Test` classes above the actual
  production `MetadataTriggerHandler`. Raw match-count over-weights test
  fixtures. Product improvement, not scope creep.
- Evaluate `MetadataComponentDependency` API as a possible exact-data
  shortcut that might cheapen/replace the Week 7 AST parser.

## Real-org observations (Week 5 Day 4)

- Dev org: 42 Apex classes, all with non-empty Body.
- Trigger-framework-heavy (trigger-actions / FFLib-style class names:
  MetadataTriggerHandler, TriggerActionFlow*, *Domain, *Selector).
- `Contact` referenced in 0 of 42 classes — genuine, not a scanner miss.
  Org's Apex doesn't touch Contact directly.

  ## ADR-007 — Case-insensitive matching for reference analysis

**Decision:** The reference analyzer matches identifiers case-insensitively
(`re.IGNORECASE`).

**Alternatives considered:** Case-sensitive matching (fewer false positives —
ignores `account` the variable when you mean `Account` the object).

**Trade-offs:** Case-insensitive over-reports slightly (a local variable named
`account` matches a search for the `Account` object). But ADR-006 already
accepts false positives (comments, string literals) as the v1 stance, so
adding case-sensitivity to fight false positives would be internally
inconsistent. False negatives are far more dangerous than false positives in
impact analysis: telling a developer "nothing references this field" when
something does means they ship a breaking change.

**Why:** Apex is a case-insensitive language — `Account`, `account`, `ACCOUNT`
all refer to the same thing to the compiler. An analyzer claiming to find
"references to Account" should match what Apex itself considers a reference.
Case-insensitive matching is therefore *correct*, not just convenient.

**Real-org evidence (this is the interview story):** Found by accident —
searching lowercase `account` returned 1 class; capital `Account` returned 9.
Same org, same cache, different answers. Traced to case-sensitivity. After the
fix, some classes revealed 2–3x more references than the case-sensitive scan
had reported (MetadataTriggerHandlerTest: 7 → 22; TriggerBaseTest: 9 → 22;
TriggerActionFlowAddErrorTest: 4 → 12). The case-sensitive scan had been
silently hiding 60%+ of references in some classes.

---

## Week 5 Day 5 retrospective

### What shipped
- Extended the reference analyzer to scan Apex triggers alongside classes
  (multi-type scan via a `metadata_types` tuple parameter, default
  `("ApexClass", "ApexTrigger")`).
- `extract_to_cache.py` now pulls both classes and triggers.
- Fixed case-sensitivity bug (ADR-007).
- 44 tests passing (was 40; replaced 5 single-type analyzer tests with 9
  multi-type + case-insensitive tests).
- Added `scripts/list_cached.py` — a cache inspector. Kept as a dev tool;
  useful for Week 6 when the graph builder reads from the cache.

### Judgment call: what is and isn't ADR-worthy
Extending the analyzer to a second body-bearing type (triggers) is NOT
ADR-worthy — a routine extension with no real alternatives or trade-offs to
weigh. The case-sensitivity fix (ADR-007) IS ADR-worthy — a real decision with
a genuine trade-off and a non-obvious "correct" answer. Knowing which is which
keeps the ADR log sharp; padding it with trivial entries would signal an
inability to tell signal from noise.

### Python learning notes
- **Mutable default argument trap.** `metadata_types: tuple[str, ...] =
  ("ApexClass", "ApexTrigger")` uses a TUPLE, not a list, as the default. A
  list default is one shared object across all calls — mutate it once and every
  future call sees the change. Tuples are immutable, so they're safe in a
  signature. Rule: never put a list/dict/set as a default argument; use a tuple
  or `None` + build inside. Same family as `field(default_factory=list)` in the
  dataclasses.

### Real-org finding
- Dev org has exactly 1 trigger across 42 classes. This is the signature of a
  trigger-actions / metadata-driven framework org (class names:
  MetadataTriggerHandler, TriggerActionFlow*, *Domain, *Selector). In this
  architecture logic lives in handler classes, not triggers — which makes the
  tool's class-scanning the higher-value path. The single trigger is not on
  Account/Opportunity (both real-org searches showed only [class] hits).

### Week 6 first tasks
- Add .gitattributes at repo root to normalize line endings (LF in repo,
  platform default in working copy). Stops the "LF will be replaced by CRLF"
  warnings. Quick setup at start of Week 6.

---

## Week 6 Day 1 — Graph data model

### What shipped
- `app/intelligence/graph/models.py` — the typed vocabulary for the whole
  graph system. Three things: `NodeType`/`EdgeType` enums, `Node`/`Edge`
  Pydantic models, and `MetadataGraph` (a wrapper around networkx.DiGraph).
- `GraphStats` model for snapshot statistics (node/edge counts by type).
- 16 unit tests (`tests/unit/test_graph_models.py`), all green. Full suite
  now 60 (44 prior + 16).
- Added `networkx>=3.0` to requirements.txt. Installed networkx 3.6.1.

### The scoping decision (the interview story for this day)
ROADMAP Week 6 Day 1-2 called for defining 7 node types (Object, Field,
ApexClass, Trigger, Flow, ValidationRule, PermissionSet) and 6 edge types.
Reconciled that against reality before building: the cache holds exactly 2
metadata types — ApexClass and ApexTrigger. You cannot populate Object,
Field, Flow, or ValidationRule nodes because that data was never extracted.

Decision: model what you can populate. The enums list all 7 node types and
all 6 edge types as *stub values* (an enum value costs nothing and documents
intent), but only ApexClass/ApexTrigger nodes and REFERENCES edges get real
builder/query/test code this week. The other types arrive when their data
does — Object/Field in Week 7 (Apex parser extracts field refs), Flow/
ValidationRule in Week 8.

The principle: **building models for node types you can't populate is
speculative engineering.** The builder would have untestable branches, the
query layer would have unreachable paths, and the graph would *look*
complete while being structurally hollow. A graph with 2 well-populated node
types is more useful — and more honest — than one with 7 half-populated ones.
This is the same "ship the useful 80% with named limitations" stance as
ADR-006, applied to data modelling instead of matching.

### Judgment call: what was and wasn't ADR-worthy
ADR-008 (MetadataGraph wraps networkx) IS ADR-worthy — a real interface
decision with a genuine trade-off (type safety vs indirection) and a
non-obvious correct answer. The scoping-to-2-types decision is borderline:
documented it here in the journal rather than as a standalone ADR, because
it's an application of an existing principle (ADR-006's stance) to a new
situation, not a fresh architectural choice. If it comes up in an interview
it's a "scope discipline" story, not an "architecture" story.

### Python learning notes
- **`str, Enum` mixin.** `class NodeType(str, Enum)` makes each member behave
  as a real string — `NodeType.APEX_CLASS == "ApexClass"` is True, and it
  serializes straight to JSON without a custom encoder. A plain `Enum` member
  is NOT equal to its value and needs `.value` everywhere. The str-mixin is
  the Pythonic default when an enum's values are strings that cross a
  serialization boundary (JSON, networkx node attrs, REST responses).
- **Wrapper over inheritance.** First instinct (Apex habit) was to subclass
  `nx.DiGraph`. The Pythonic choice here is composition — `MetadataGraph`
  *has* a DiGraph (`self._g`), it isn't one. Subclassing would expose
  networkx's entire untyped API surface as public, which is the opposite of
  what ADR-008 wants. "Prefer composition over inheritance" lands concretely
  here: I want to expose 6 typed methods, not 80 untyped ones.
- **`_` prefix as a contract, not enforcement.** `MetadataGraph._graph` is a
  property prefixed with `_` to signal "internal — query layer only." Python
  has no real `private`; the underscore is a convention other developers
  honor. Coming from Apex's `private` keyword this felt flimsy at first, but
  it's the actual Python norm.

### What surprised me
- **networkx stores node/edge data as plain dicts.** `g.add_node(id, **attrs)`
  just splats keyword args into a dict hanging off the node. No schema, no
  validation — which is exactly why ADR-008 wraps it. The typing has to live
  in my layer because networkx provides none.
- **Python 3.14.** Local interpreter is 3.14.4, but the ROADMAP/README claim
  "3.11+". Nothing in models.py uses 3.14-only syntax (the `X | None` unions
  and `list[int]` generics are all 3.10+), so I'm safe across the stated
  range. Flagged a parked item below.

### Scope I noticed but parked
- **OSS support matrix.** Running on 3.14 locally, but claiming 3.11+ support.
  Before the open-source MCP server launch, CI needs to test against 3.11,
  3.12, 3.13 — a library can pass on 3.14 and break on 3.11 if newer-only
  syntax slips in. Pre-launch / Phase 2 concern, not now. Noting it so it
  isn't lost.

### What's next (Day 2)
Graph builder — `app/intelligence/graph/builder.py`. Read the cache, run the
reference analyzer internally against the real org's 42 classes + 1 trigger,
and turn the string-scan hits into actual REFERENCES edges between nodes.
First time the graph holds real data instead of test fixtures.

---

## ADR-008 — MetadataGraph wraps networkx.DiGraph

**Status:** Accepted
**Date:** Week 6, Day 1

**Decision:** `MetadataGraph` is a typed wrapper class. Callers interact with
`Node`/`Edge` Pydantic models; the underlying `nx.DiGraph` is an
implementation detail, exposed only via a `_graph` escape hatch for the query
layer's algorithm needs (shortest_path, etc.).

**Alternatives considered:**
- **Expose `nx.DiGraph` directly** — callers call `G.successors()` and read
  node data as raw dicts. Simplest, zero indirection.
- **Subclass `nx.DiGraph`** — `MetadataGraph(nx.DiGraph)`. Inherits the full
  API, can add typed methods on top.
- **Pure-Pydantic adjacency structure** — no networkx; a `dict[str, list[str]]`
  adjacency map plus a node lookup dict.

**Trade-offs:**
- ✅ Type safety — no `node["node_type"]` string lookups leaking into the
  query or REST layers; IDE autocomplete works end to end.
- ✅ Swap-safe — if networkx is ever replaced (DB-backed graph in Phase 2),
  callers don't change; only the wrapper internals do.
- ✅ Testable in isolation — MetadataGraph unit tests need no running server.
- ❌ Indirection cost — `g.add_node(node)` instead of `G.add_node(id, **data)`.
- ❌ The `_graph` escape hatch is a mild design smell: the query layer gets
  privileged access to internals. Accepted because reimplementing networkx's
  graph algorithms in my own layer would be far worse.

**Why this over raw networkx:** The untyped dict API is fine for exploratory
graph scripting. It's a liability when building a typed REST API on top —
every layer has to know the internal dict shape and there's no compiler help.
The wrapper pays for itself at the first `/graph/` endpoint.

**Why composition over subclassing:** Subclassing `nx.DiGraph` would expose
its entire ~80-method untyped surface as public API. The whole point is to
expose ~6 typed methods. Composition (`MetadataGraph` *has* a DiGraph) hides
what shouldn't be public; inheritance can't.

**Why not pure-Pydantic:** networkx gives shortest-path, connected-components,
and cycle detection for free. Reimplementing those in adjacency-dict logic is
Phase 2 pain with no Phase 1 payoff.

---

## Week 6 Day 2 — Graph builder + real-org verification

### What shipped
- `app/intelligence/graph/builder.py` — `GraphBuilder`. Two passes over the
  cache: one Node per record (ApexClass, ApexTrigger), then REFERENCES edges
  built by running the reference analyzer with each node's name as the target
  identifier. Self-edges excluded; edges only to known nodes. ADR-009.
- `scripts/verify_graph.py` — builds the graph from the real local cache
  (zero API calls) and reports hubs, dependency counts, orphans, build time.
- 11 hermetic builder tests. Full suite 71 (60 + 11).

### Real-org result (arvindcom-dev-ed)
43 nodes (42 classes + 1 trigger), 87 edges, built in 268 ms.

- **Hubs (in-degree) = framework core, as expected.** TriggerActionFlow (12),
  TriggerBase (11), MetadataTriggerHandler (9), TriggerAction (8),
  TriggerActionConstants (8). The graph correctly flags the high-blast-radius
  classes. A change to TriggerActionFlow touches 12 dependents.
- **Out-degree dominated by test classes.** MetadataTriggerHandlerTest (6),
  four *Test classes at 5. Tests instantiate what they cover, inflating
  out-degree. Independently validates parked item 1 (rank production above
  test) — tests pollute BOTH directions of ranking, not just ref counts.
- **1 orphan: EdmcDealLineItemController.** Zero Apex refs in or out. A
  controller with no Apex links is almost certainly UI-bound (Aura/LWC/VF —
  invisible to an Apex string scan) or dead code. Concrete actionable insight;
  worth manual triage.

### Prediction vs reality (the honest retro)
I predicted metadata-wired action classes would surface as ORPHANS. Wrong.
Only 1 orphan appeared, and it's a UI controller, not an action class.

Why the prediction failed: I conflated "orphan" (in-degree 0 AND out-degree 0)
with "nothing in Apex references it" (in-degree 0 only). Trigger-actions
action classes ARE invisible by name (wired via Trigger_Action__mdt strings,
not Apex) — so in-degree 0 — but their bodies still `implements
TriggerAction.BeforeInsert`, giving them out-edges. The out-edge disqualifies
them as orphans. The orphan filter is too strict to catch the metadata-wired
classes I was looking for.

Correction: the right lens for "metadata/UI-wired, never called from Apex" is
IN-DEGREE 0, not orphan. Folding this into the Day 5 query API as a distinct
query alongside find_orphaned.

### Perf finding — refines ADR-009
ADR-009 framed the cost as "O(N^2) body scans." More precisely: the 268 ms is
dominated by repeated SQLite I/O, not regex. ~43 analyzer calls x 2
connections each (per-op connection, ADR-004) = ~88 connect/close cycles,
each re-reading all 42 bodies. Regex is ~18 ms of the 268 ms; the rest is
connection churn. The scaling fix is therefore "load the cache once, scan in
memory" — independent of matching strategy. Still 18x under the 5 s ROADMAP
target at this scale, so parked, but now the cause is precise. (Confirms the
quadratic: 7 synthetic nodes built in 11 ms; 43 nodes in 268 ms ~= (43/7)^2.)

### Day 5 query API refinement (driven by today's data)
- `find_orphaned()` — in==0 AND out==0. Catches dead/UI-bound classes
  (EdmcDealLineItemController).
- `find_never_referenced()` (in==0, out>0) — NEW. Catches metadata-wired
  action classes the orphan filter misses. This is the query that actually
  exposes the trigger-actions wiring gap.

### What's next (Day 3-4 -> compressed)
Day 1-2 delivered the model AND the builder AND real-org verification ahead of
the ROADMAP's Day 1-4 plan. Day 3-4 reduces to: optional perf hardening
(load-once) if wanted, else straight into Day 5 query API
(what_depends_on / what_does_it_depend_on / find_path / find_orphaned /
find_never_referenced) and the CLI command. Likely pulls the week forward.

---

## Week 6 Day 3 — Graph query API (Day 5 work pulled forward)

### What shipped
- `app/intelligence/graph/query.py` — `QueryEngine`, six domain queries over
  the in-memory graph: what_depends_on, what_does_it_depend_on (both
  direct/transitive), find_path (returns edges w/ line numbers), find_by_name
  (case-insensitive), find_orphaned, find_never_referenced.
- 18 hermetic tests. Full suite 89 (71 + 18).

### Design decisions
- **Synchronous, not async.** The graph is in-memory; the builder already
  paid the async SQLite cost. Queries need no await and return instantly.
  A genuinely Python-shaped distinction with no Apex parallel.
- **Direct vs transitive behind one flag** (`transitive: bool = False`,
  default direct). Direct = interpretable, composable, least-surprising.
  Transitive = blast radius (nx.ancestors/descendants), one keyword away.
  A default-value choice, not an architecture fork — not ADR-worthy.
- **Honored ADR-008's escape hatch** rather than re-opening it. query.py is
  the single sanctioned consumer of MetadataGraph._graph for raw networkx
  traversal. Consistency with my own 2-day-old ADR over churning models.py.
- **find_never_referenced added** (in==0, out>0) per Day 2's data — the
  query that actually exposes metadata-wired trigger-action classes the
  orphan filter misses.

### Python learning — comprehensions are for simple filters
Tried to inline a ternary as a comprehension filter:
    [n for n in xs if (cond1) if exact else (cond2)]   # SyntaxError
Python parses the first `if` as the filter, then can't handle the trailing
`if/else`. The Apex instinct is to add parens until it compiles. The Pythonic
fix is to pull the branching condition into a named predicate:
    def matches(name): return name == q if exact else q in name
    [n for n in xs if matches(n.name)]
Reads as English, testable in isolation, no parse ambiguity. Rule: when a
comprehension's condition needs a branch, name it — don't cram it.

### What's next
Day 6 — wire QueryEngine to a /graph/ REST route + the CLI command
(`python -m ... query "what depends on X"`), then benchmark. The query
engine and builder are both done and real-org-verified ahead of schedule.

---

## Week 6 Day 6 — CLI + real-org demo

### What shipped
- `app/interfaces/cli.py` — argparse CLI (ADR-001: interfaces/ layer, NOT
  scripts/, because the CLI is a product surface not dev plumbing). Seven
  commands: depends-on, dependencies (both --transitive), path, find,
  orphans, never-referenced, stats. Handlers are pure functions returning
  strings; only main() prints (testable without stdout capture).
- Name->id resolution: exact match wins, single substring auto-resolves,
  ambiguity prompts. The glue that makes it demoable (humans type names,
  QueryEngine takes Ids).
- 23 tests (handlers + name resolution + argparse wiring). Full suite 112.

### Real-org demo results (arvindcom-dev-ed)
- `depends-on TriggerActionFlow`: 12 direct, 13 transitive (extra hop reaches
  TriggerActionFlowChangeEventTest). Blast-radius story works end to end.
- `dependencies MetadataTriggerHandler`: 5 (FinalizerHandler, FormulaFilter,
  TriggerAction, TriggerActionFlow, TriggerBase).
- `orphans`: 1 (EdmcDealLineItemController) — consistent with Day 2.
- `never-referenced`: 15.

### never-referenced — prediction half-wrong AGAIN, and the real lesson
I framed never-referenced (in==0, out>0) around metadata-wired trigger-action
classes. Real output: 12 of 15 are *Test classes. Test classes are
never-referenced for a mundane reason — the @isTest runner invokes them by
annotation, not by code reference. So in==0/out>0 is the EXPECTED, boring
state for every test class. Only 3 of the 15 are the interesting signal:
AsyncParksServices, PricingFlowAction, TriggerDispatcher (likely flow/invocable
entry points or framework dispatch). The query is correct but noise-dominated.
Fixed the CLI header, which had claimed "often metadata-wired" — the data says
otherwise, and a demo shouldn't make a claim the screen contradicts.

### Test-class noise is now structural, not a parked nicety
Third independent hit: (1) Week 5 Account search ranked 5 Tests above the prod
handler; (2) Day 2 out-degree ranking dominated by Tests; (3) today
never-referenced is 80% Tests. A node-level test-vs-production classifier
(name ends in Test/Tests OR body has @isTest, stored as a node attribute at
build time) would let every query de-rank/filter tests with one flag. Elevating
from "parked product improvement" to a Week 7 first-class task at week-end.

### REST /graph/ route — parked
ROADMAP Day 6 listed a /graph/ REST route. Deferred: the CLI already satisfies
the "queryable graph" deliverable and the demo, and a REST route forces a
graph-lifecycle decision (build at startup? per request? cached?) for a
consumer (VS Code ext, Week 13) that doesn't exist yet. Add it when the
consumer does.

## Week 7 Day 1 — Test-class classifier + --no-tests filter

### What shipped
- `app/intelligence/graph/classifier.py` (new) — `is_test_class(record)`.
  Two signals OR'd: (1) name ends in `Test` or `Tests` (case-insensitive,
  word-boundary guarded so `ContestHelper` doesn't match); (2) body contains
  `@isTest` annotation (case-insensitive, covers `@IsTest(SeeAllData=true)`).
  Kept as a module-level function, not a class — classifiers are stateless
  transforms (input → bool), a class would add indirection with no benefit.
- `app/intelligence/graph/builder.py` — classifier wired into `_add_nodes()`.
  `is_test_class(rec)` runs once per record at build time; result stored as
  `node.attributes["is_test"]`. Queries and CLI never re-read bodies.
- `app/intelligence/graph/query.py` — `find_never_referenced()` gains
  `exclude_tests: bool = False`. When True, filters nodes where
  `attributes["is_test"]` is True. Inner `_keep()` predicate used instead of
  stacking conditions in the generator — same lesson as Week 6's comprehension
  filter moment: when a generator condition needs branching, name it.
- `app/interfaces/cli.py` — `never-referenced` command gains `--no-tests`
  flag. Unfiltered output now annotates test nodes with `[test]` suffix so
  both views (all 15 / production-only 3) are readable without running two
  commands.
- 17 classifier tests, 4 new query tests. Full unit suite: 106 passing.

### Real-org verification
- `never-referenced` (no flag): 15 results, 12 annotated `[test]` ✓
- `never-referenced --no-tests`: 3 production entries only:
  AsyncParksServices, PricingFlowAction, TriggerDispatcher ✓
- Classifier correctly identifies all 12 test classes by name suffix alone
  (all end in `Test` or `Tests`). The `@isTest` body signal is the safety net
  for classes named outside the convention.

### The signal this unlocks
Week 6's `never-referenced` query was 80% noise (12/15 test classes). With
`--no-tests`, the 3 production entries are clean signal for the first time:
- `TriggerDispatcher` — likely framework dispatch entry point
- `PricingFlowAction` — likely flow/invocable entry point
- `AsyncParksServices` — likely @future or async entry point
These are the dead-code / metadata-wired candidates worth eyeballing (carried
from Week 6 parked list).

### Python learning
- **Inner predicate functions over stacked generator conditions.** The
  `_keep(n)` function inside `find_never_referenced` handles three conditions
  (in-degree, out-degree, is_test). Stacking them as `if a and b and (not
  exclude_tests or not n.attributes.get(...))` inside a generator expression
  is legal Python but hard to read and hard to test. Pulling it into a named
  inner function reads as English and is independently debuggable. Rule: when
  a generator's filter condition needs branching, name it — don't cram it.
- **Module-level functions vs classes for stateless logic.** `classifier.py`
  has no class. In Apex everything lives in a class — there's no choice.
  Python has no such requirement. A stateless transform (record → bool) is
  cleanly expressed as a plain function. A class wrapper would force a
  pointless instantiation call and add `self` to a method that doesn't need
  any instance state. Pythonic default: class only when you need state or
  multiple related behaviours.

### What's next — Day 2
Apex pattern parser (`intelligence/apex/parser.py`). Pattern-based extraction
from Apex class bodies: SOQL queries, DML statements, field references
(SObject.Field__c dot-notation), class-level method calls. Output feeds the
derive-vs-extract decision on Day 3. No ANTLR — regex patterns only.

## Week 7 Day 2 — Apex pattern parser

### What shipped
- `app/intelligence/code/apex_parser.py` (new package `intelligence/code/`).
  `parse_apex_body(body)` returns a `ParseResult` dataclass with four lists:
  `soql_references`, `dml_references`, `field_references`, `class_references`.
  Pure function — no I/O, no cache, no graph dependency.
- Three fixes discovered and applied after first real-org run:
  - Fix 1: `_strip_comments()` pre-processor removes `//` and `/* */` before
    any pattern runs. Eliminated `www.apache`, `PMD.*` (from Javadoc),
    `the`/`a` (from prose comments after FROM) as false positives.
  - Fix 2: PascalCase filter on class refs — qualifiers starting lowercase
    are variable names (`result`, `handler`, `this`), not class names. Dropped
    them. Real Apex class names are PascalCase by convention.
  - Fix 3: DML regex updated with optional `(?:new\s+)?` group to skip the
    `new` keyword. `insert new Account()` now captures `Account`, not `new`.
- `scripts/verify_parser.py` — real-org validation script (zero API calls).
- 42 hermetic tests. Full unit suite: 148 passing.

### Real-org verification results (34ms, 43 records)
- 6 clean sObject nodes derivable from SOQL: Opportunity, Trigger_Action__mdt,
  OpportunityLineItem, ProcessInstance, ProcessInstanceStep,
  ProcessInstanceWorkitem
- Residual SOQL noise: `the` (1), `elements` (1) — string literal false
  positives, not fixable without string stripping, acceptable for Phase 1
- Top class-call targets: Assert(44-test noise), TriggerBase(20),
  TriggerActionFlow(18), MetadataTriggerHandler(15) — these become CALLS edges
- `PMD.*` still in field refs — these are `@SuppressWarnings('PMD.X')` in live
  code (not comments), so comment stripping can't remove them. Accepted noise.
- Zero extractions: CaseObjectTrigger (minimal trigger), IDomain (interface) —
  both expected

### derive-vs-extract decision — now concrete (Day 3 ADR)
Parser output confirms derive (Option B) is correct for Phase 1:
- 6 real sObject nodes from SOQL alone is enough for the portfolio demo
- Class-call edges (Apex→Apex via method calls) are a genuine graph enrichment
  on top of the existing string-scan REFERENCES edges
- Full extraction (Option A) would add metadata richness but cost a week;
  the intelligence value is in the edges, not the node attributes

### Python learning
- **`re.DOTALL` flag.** Block comment stripping requires `re.DOTALL` so `.`
  matches newlines. Without it, `/* multi\nline */` doesn't match because `.`
  stops at `\n` by default. In Apex, `Pattern.DOTALL` is the equivalent flag.
- **Non-capturing groups `(?:...)`** in the DML fix. `(?:new\s+)?` skips
  `new` without creating a capture group that would shift `m.group(2)`.
  In Apex: same syntax — `Pattern.compile("(?:new\\s+)?")`.
- **`frozenset` for lookup tables.** `_SYSTEM_NAMESPACES` and `_DML_SKIP_TOKENS`
  are `frozenset` not `set`. Frozenset is immutable and hashable — signals
  "this is a constant, not state". In Apex: `static final Set<String>` in a
  static initializer block is the closest equivalent, but it's mutable by
  default (no true immutability in Apex collections).

### What's next — Day 3
Object/Field nodes + CALLS edges wired into the graph builder. Derive approach
confirmed. Builder already type-agnostic (ADR-008/009) — extend
`_METADATA_TYPE_TO_NODE_TYPE` map and add a second edge-building pass using
the parser output.

## Week 7 Day 3 — Object nodes + CALLS/USES_OBJECT edges; MultiDiGraph migration

### What shipped
- `models.py`: NodeType.OBJECT now live; EdgeType gains CALLS (Apex→Apex
  method calls) and USES_OBJECT (Apex→Object via SOQL/DML). Underlying graph
  migrated DiGraph → MultiDiGraph (ADR-011).
- `builder.py`: third build pass (`_add_parser_edges`) runs the Apex parser
  over each body. Derives Object nodes (id=`obj:<name>`, source="derived",
  ADR-010), adds CALLS edges to known class nodes, USES_OBJECT edges to derived
  Object nodes. Noise filter (`_is_valid_object_name`) drops short tokens and
  known SOQL noise (the, elements, etc.).
- `query.py`: find_path made MultiDiGraph-safe (picks first edge key per hop);
  `_nodes_for`, successors/predecessors dedupe neighbors reached by parallel edges.
- 156 unit tests passing (148 → 156). Zero regressions on the MultiDiGraph switch.

### The bug that forced ADR-011 (the interview story)
Wrote the CALLS-edge tests, they passed. But a Week 6 REFERENCES test —
`test_edge_attributes_carry_lines_and_count` — started failing: it found ZERO
REFERENCES edges where it expected one. Root cause: networkx DiGraph allows
only ONE edge per ordered node pair. When Caller both REFERENCES Helper (pass 2)
and CALLS Helper (pass 3), the second add_edge silently OVERWROTE the first.
We were losing edges with no error.

The test caught real data loss. If I'd only run the new tests, the regression
would have shipped. Switched to MultiDiGraph (parallel edges allowed). Verified
on real org: REFERENCES count held at exactly 87 (would have dropped under
DiGraph as CALLS overwrote same-pair REFERENCES edges).

### Real-org graph (298ms)
- 50 nodes: 42 ApexClass + 1 ApexTrigger + 7 derived Object
- 166 edges: 87 REFERENCES + 71 CALLS + 8 USES_OBJECT
- 0 orphans (Object nodes connected everything that was previously isolated)
- 7 Object nodes: the clean sObjects from the parser (Opportunity,
  Trigger_Action__mdt, OpportunityLineItem, ProcessInstance, etc.)

### Python learning
- **DiGraph vs MultiDiGraph edge semantics.** DiGraph: one edge per (u,v) pair;
  re-adding overwrites. MultiDiGraph: parallel edges, each with an integer key.
  `get_edge_data(u, v)` returns `{key: data}` on a MultiDiGraph vs a flat data
  dict on DiGraph — that's why find_path needed `get_edge_data(a,b)[first_key]`
  not `edges[a, b]`. The migration's hidden cost is every consumer of raw edge
  access, not the type swap itself.
- **MultiDiGraph successors can repeat.** `g.successors(n)` yields a neighbor
  once per parallel edge. Deduping with a `seen` set is required wherever we
  return "distinct neighbors" — otherwise a class called twice shows up twice.

### What's next — Day 4
field-impact demo: `depends-on Opportunity` should now trace the Apex classes
that query/DML it (via USES_OBJECT edges). Wire Object-node lookup into the CLI
name resolver so `obj:opportunity` resolves from a typed "Opportunity".

## Week 7 Day 4 — impact command + incoming_edges (field-impact demo)

### What shipped
- `query.py`: new `incoming_edges(node_id, edge_type=None)` — returns the
  actual Edge objects pointing at a node, not deduped Nodes. This is the
  missing primitive: every prior query returned Node lists and discarded edge
  metadata. impact needs the edge detail (edge_type + attributes like
  via="soql", method="run") to show HOW a dependency exists. Returns all
  parallel MultiDiGraph in-edges; optional edge_type filter.
- `cli.py`: new `impact <name>` command. Shows what touches a node and how:
  "via SOQL/DML (SOQL)" for objects, "via method call (isBypassed())" for
  class calls, "via name reference" for string-scan refs. Dedicated command
  (not overloaded depends-on) per design decision — keeps depends-on as the
  clean Apex→Apex dependency story.
- 6 incoming_edges tests + 4 impact handler tests + parser wiring. 169 total.

### Real-org demo — the Week 7 headline working
- `impact Opportunity`: EdmcDealLineItemController + OpportunitySelector,
  both via SOQL. "What breaks if I change Opportunity" answered.
- `impact TriggerBase`: 30 references. Shows the SAME class with BOTH a
  method-call edge (isBypassed()) AND a name-reference edge — the parallel
  edges MultiDiGraph preserves. method-level detail (which method couples the
  caller) is the parser precision the string-scan alone couldn't give.

### Why a dedicated command (the design decision)
Chose a separate `impact` command over enriching `depends-on`. Reasoning:
depends-on answers "what is the blast radius" (Node list, deduped). impact
answers "how exactly does each thing touch this" (Edge list, typed, with
method/via detail). Different questions, different return shapes. Overloading
one command to do both would muddy the clean Node-list semantics of
depends-on. The edge-detail need is also why incoming_edges had to return
Edges, not Nodes — the first query in the engine to do so.

### Python learning
- **MultiDiGraph in_edges signature.** `g.in_edges(node, keys=True, data=True)`
  yields 4-tuples `(src, tgt, key, data)`. Forgetting keys=True on a
  MultiDiGraph silently merges parallel edges in some networkx calls — keys=True
  makes each parallel edge distinct. The key is the integer networkx assigns to
  disambiguate parallel edges.
- **Returning edges vs nodes — an API shape decision.** Every existing query
  returned `list[Node]`. incoming_edges breaks that pattern by returning
  `list[Edge]` because the caller needs the relationship metadata, not just the
  endpoints. The lesson: let the consumer's actual need drive the return type,
  don't force a new query into an existing shape that drops the data it needs.

### What's next — Day 5
Per ROADMAP, Day 5 is the Flow analyzer — flagged as FIRST TRIM CANDIDATE if
the week is running hot. Decision point: we're on Day 4 and the field-impact
headline is DONE and demoable. Evaluate at start of Day 5 whether Flow analysis
earns the time or slips to Week 8 (its prerequisite — Flow metadata extraction
— isn't even built yet).

## Week 7 Day 5 — Flow vertical slice (SOAP extraction + XML parser + graph edges)

### What shipped
Full Flow analysis, all three layers, against the real org:
- **metadata_api.py** — Metadata API SOAP client. readMetadata('Flow', names),
  synchronous, OAuth access_token reused as the SOAP <sessionId> (probed and
  confirmed Day 5 step 0 — no separate SOAP login). Chosen over retrieve()
  (async poll + zip) because we need structure for analysis, not deployable
  artifacts — collapses a 4-layer stack to 2. Batches at 10 names (the
  readMetadata cap). Caches RAW XML, consistent with caching ApexClass.Body raw.
- **flow_parser.py** — Flow XML -> FlowParseResult (triggering object, apex
  actions, subflows). ElementTree, not regex (nested well-formed XML).
- **builder.py pass 4** — Flow nodes (id=flow:<name>), then Flow->Object
  (USES_OBJECT via=flow_trigger), Flow->Apex (CALLS via=flow_action),
  Flow->Flow (CALLS via=subflow). Reuses existing edge types so impact works
  for free. Two sub-passes: all Flow nodes first, then edges, so subflow
  targets resolve regardless of order.
- **cli.py** — impact labels now driven by the edge `via` attribute, not just
  edge type. Fixes Flow edges that were mislabeled "method call".
- 201 tests (169 -> 201).

### Real-org result
57 nodes (43 Apex + 8 Object + 6 Flow), 172 edges
(87 REFERENCES + 74 CALLS + 11 USES_OBJECT). REFERENCES held at 87 across all
four passes — MultiDiGraph still preventing edge loss (ADR-011).

**The payoff:** `impact PricingFlowAction` -> Opportunity_Sales_Orchestration_Flow
via Flow action. PricingFlowAction was a Week-6 "never-referenced" production
class; the Flow->Apex edge explains why — a Flow invokes it, invisible to an
Apex-only string scan. The metadata-graph thesis demonstrated in one command.
It correctly dropped off the never-referenced list once the edge existed.

### Bugs caught (both before shipping)
1. **xsi-namespace unbound-prefix.** The bare <records> block from readMetadata
   carries xsi:type="Flow", but the xsi prefix is declared on the SOAP envelope
   (stripped during block extraction). ElementTree rejected it ("unbound
   prefix"). Fix: wrap the fragment in a synthetic root declaring xsi, then
   descend to the records element. Caught by sandbox verification against real
   XML structure, not the hermetic tests.
2. **actionType filter.** Not every <actionCalls> is a Flow->Apex edge. The
   Approval Orchestrator's actionCall was actionType=submit (an approval
   action), not apex. Filtering on actionType=apex prevents a phantom edge to a
   class named "submit". Verified against the real dump.

### Real-org finding — a correct orphan
`Opportunity_Approval_Orchestrator` is the sole orphan, and that's the RIGHT
answer. Its <start> has no <object> (autolaunched, not record-triggered —
<start> just connects to a Get_Opportunity lookup). Its one actionCall is
submit (filtered). The Opportunity it references is a runtime recordLookups,
not a trigger. So: no incoming edges, no outgoing graph edges -> orphan. In a
trigger-actions org, an orphan flow means invoked outside scanned metadata
(button/quick-action/approval process) or dead. Exactly the human-eyeball
signal the tool exists to surface.

CAVEAT banked: verify_metadata_api.py's "start object" line uses a loose regex
(<object> anywhere in XML) and gave a FALSE POSITIVE here — reported "start
object: Opportunity" when the object was only in a recordLookups. The parser's
stricter rule (object must be a direct child of <start>) was correct. Trust the
parser over that recon line.

### Python learning
- **ElementTree namespace handling.** fromstring on a fragment with an
  undeclared prefix raises ParseError "unbound prefix". A namespace prefix is
  only valid where declared; extracting a sub-element loses ancestor xmlns
  declarations. Wrapping in a synthetic root that re-declares the prefix is the
  fix. _localname() strips the {namespace} ET adds to every tag.
- **Let the data's own discriminator drive logic, not the container type.**
  Both the parser (actionType=apex) and the CLI (via attribute) decide on a
  specific field rather than the broad type. CALLS-the-edge-type isn't enough to
  label an edge; via tells you whether it's a method call, flow action, or
  subflow. Same lesson in two places this week.

### Parked to Week 8 (deliberate, not dropped)
- **Flow record-operation edges.** Flows reference objects/fields in
  recordLookups/recordCreates/recordUpdates (not just the trigger). A real
  dependency the graph currently misses (the Approval Orchestrator DOES depend
  on Opportunity via a lookup). It's the Flow equivalent of Apex SOQL/DML
  extraction — a whole sub-feature with field-level reach — so it belongs as a
  deliberate Week 8 task, not a last-day add.



  ## ADR-010 — Derive Object nodes from the Apex parser, not Tooling API extraction

**Status:** Accepted
**Date:** Week 7, Day 3

**Decision:** Object nodes are DERIVED from references the Apex/Flow parsers
discover (SOQL FROM targets, DML targets, Flow triggering objects), not
EXTRACTED as authoritative records from the Tooling API (EntityDefinition).
A derived Object node has id `obj:<name casefold>`, carries `source="derived"`,
and exists only because some code or flow references it.

**Alternatives considered:**
- **Extract authoritative objects** via Tooling EntityDefinition (and
  FieldDefinition for fields). Every object in the org becomes a node whether
  or not anything references it; nodes carry real metadata (label, key prefix,
  custom-vs-standard).
- **Hybrid** — derive now, backfill authoritative metadata onto derived nodes
  in a later pass.

**Trade-offs:**
- ✅ Cheap and immediate — Object nodes fall out of parsing we already do for
  edges. No new extraction, no new API calls, no new cache type. ~1 day vs ~1
  week for full EntityDefinition/FieldDefinition extraction.
- ✅ The graph only contains objects that actually participate in dependencies,
  which is exactly what the impact/depends-on queries care about. No noise from
  hundreds of unreferenced standard objects.
- ❌ Objects nothing references don't appear. "What uses Lead?" returns nothing
  if no Apex/Flow touches Lead — but that's arguably the correct answer for a
  dependency graph (if nothing uses it, it's not in the dependency story).
- ❌ Derived nodes have no metadata richness (no label, no field list, no
  custom/standard flag). source="derived" marks them so Phase 2 can enrich.
- ❌ Name-based ids (`obj:account`) not Salesforce ids — a derived Account and
  an extracted Account would need reconciling if we add extraction later. The
  casefold id scheme is the reconciliation key.

**Why this over extraction:** The value of Phase 1 is the EDGES — "what depends
on what" — not node metadata completeness. A dependency graph answers "if I
change X, what breaks"; that needs the objects that participate in dependencies,
which derivation gives for free. Authoritative extraction is a real feature with
real cost (two new Tooling queries, two new cache types, field-node explosion)
whose payoff — objects/fields nothing references — doesn't serve the Phase 1
demo. Deferred to Phase 2, with source="derived" as the seam to enrich along.

---

## ADR-011 — MetadataGraph uses MultiDiGraph, not DiGraph

**Status:** Accepted
**Date:** Week 7, Day 3

**Decision:** The underlying networkx graph is a `MultiDiGraph` (parallel edges
allowed between the same ordered node pair), not a `DiGraph` (at most one edge
per ordered pair). This supersedes the DiGraph choice implied in ADR-008.

**Context — how it surfaced:** A Week-6 test, `test_edge_attributes_carry_lines
_and_count`, started failing when Day-3 added CALLS edges. The cause was silent
data loss: a DiGraph allows only ONE edge from A to B, so when class A both
REFERENCES class B (string-scan, pass 2) AND CALLS a method on B (parser, pass
3), the second edge silently OVERWROTE the first. The graph quietly dropped a
real dependency and nobody would have known without that test.

**Alternatives considered:**
- **Keep DiGraph, merge edge types onto one edge** — store a set of types in a
  single edge's attributes (e.g. `types={REFERENCES, CALLS}`). One edge per
  pair, no parallel edges.
- **Keep DiGraph, drop the "lesser" edge** — when CALLS and REFERENCES exist
  between a pair, keep only one by some priority rule.
- **MultiDiGraph** — allow both edges to coexist as distinct parallel edges,
  each with its own type and attributes.

**Trade-offs:**
- ✅ No data loss — every typed relationship between two nodes is preserved.
  The impact command can show "TriggerBase is touched by class X via method
  call isBypassed() AND via name reference" — both true, both shown.
- ✅ Honest model — a class really can depend on another in multiple distinct
  ways; collapsing them loses information a developer needs.
- ❌ Traversal complexity — successors()/predecessors() can return the same
  neighbor multiple times (once per parallel edge), so they must dedupe by node
  id. get_edge_data() returns `{key: data}` not `data`. find_path picks one
  edge per hop (lowest key) as representative.
- ❌ Slightly more memory (multiple edge records per pair) — negligible at scale.

**Why this over merging:** Merging types onto one edge sounds tidy but loses
per-relationship attributes — a CALLS edge carries `method="isBypassed"`, a
REFERENCES edge carries `line_numbers=[...]`; they can't share one attribute
bag without ambiguity ("which line number belongs to which relationship?").
Dropping the lesser edge is strictly worse — deliberate data loss. MultiDiGraph
models reality: distinct relationships are distinct edges. The dedup cost in
traversal is a few lines; the alternative is a graph that lies about
dependencies.

**Strongest lesson:** A test written for an unrelated reason (Week 6 edge
attributes) caught a silent correctness bug introduced two weeks later (Day 3
CALLS edges). The test didn't fail loudly because of a crash — it failed
because the data was wrong. This is the case for testing data correctness, not
just "does it run."

---

## ADR-012 — Flow extraction via Metadata API readMetadata, not Tooling or retrieve()

**Status:** Accepted
**Date:** Week 7, Day 5

**Decision:** Flow structure is extracted via the Metadata API SOAP operation
`readMetadata('Flow', names)`, authenticated with the existing OAuth
access_token as the SOAP `<sessionId>`. Not the Tooling API's Flow.Metadata
field, and not the Metadata API's `retrieve()` operation.

**Alternatives considered:**
- **Tooling API Flow.Metadata** — query the Flow record, read its `Metadata`
  field as a JSON structure. Stays in the existing REST/JSON stack.
- **Metadata API retrieve()** — the canonical metadata-deployment path: POST a
  package manifest, get an async result id, poll checkRetrieveStatus until done,
  download a base64 zip, unzip, parse the .flow XML files.
- **Metadata API readMetadata()** — synchronous: POST a SOAP envelope naming the
  flows, get the Flow structure back directly in the SOAP response body.

**Trade-offs:**
- ✅ readMetadata is SYNCHRONOUS — one call in, structure back. No async result
  id, no polling loop, no checkRetrieveStatus, no backoff. retrieve() is async.
- ✅ Returns structure directly as SOAP XML — no base64 zip to decode, no
  archive to unzip. retrieve() returns a zip; that's a whole extra layer.
- ✅ Authoritative source — it IS the Metadata API, the canonical metadata,
  unlike the Tooling API's secondary Flow.Metadata exposure.
- ✅ OAuth token works as the SOAP sessionId (probed Day 5 step 0) — no separate
  SOAP login() flow needed; one auth path shared with the REST/Tooling clients.
- ❌ SOAP, not REST — a foreign protocol in an otherwise REST/JSON stack. Needs
  hand-built XML envelopes and XML response parsing (vs JSON everywhere else).
- ❌ 10-records-per-call cap — must batch. (Non-issue at 6 flows; batching added
  anyway for correctness.)
- ❌ Tooling's Flow.Metadata would have stayed in JSON/REST — but its reliability
  was unproven (cf. the FlowDefinition.MasterLabel unreliability from Week 5),
  and it's a secondary exposure, not the authoritative metadata.

**Why readMetadata over retrieve():** retrieve() is correct for its problem —
pulling deployable file artifacts as a package. Our problem is different: read
Flow STRUCTURE for analysis. readMetadata fits that exactly and collapses the
4-layer retrieve() stack (envelope → async poll → zip decode → XML parse) to 2
(envelope → XML parse). Choosing the operation that matches the actual need,
not the most powerful one.

**Why Metadata SOAP over Tooling JSON:** The portfolio thesis is "metadata
graph." Reading the authoritative Metadata API is more credible than a Tooling
side-channel, and avoids betting on Tooling's unproven Flow.Metadata
reliability. The cost (a SOAP client in a REST stack) was scoped and accepted
deliberately — see the Day-5 SOAP probe that de-risked it before building.


---

## Week 8 Day 1 — Claude client (orchestration foundation)

### What shipped
- `app/intelligence/orchestration/claude_client.py` (+ package `__init__.py`)
  — async Claude client wrapping `AsyncAnthropic`, with:
  - the agentic tool loop (stream text → detect tool_use → dispatch handlers
    concurrently → feed results back → repeat until end_turn or max_iterations)
  - streaming via `client.messages.stream()` (gives streamed text AND the
    final message with usage in one pass)
  - `SessionUsage`/`TurnUsage` cost tracking (in-memory, session-scoped;
    pricing constants for claude-sonnet-4-6)
  - `max_iterations` guard (default 10) against runaway tool loops
  - externally-registered tool handlers (`register_tool`) — client stays
    generic, knows nothing about Salesforce
- Model targeted: `claude-sonnet-4-6` (verified current via platform docs).
- Smoke-tested (cost math $18.00 for 1M+1M tokens, instantiation, tool
  registration — all green), then removed the throwaway smoke script; the
  client's real verification is the Day 6 end-to-end live call plus the unit
  tests landing with tool_definitions.

### Not yet exercised (honest status)
- The agentic loop has NOT made a real API call yet. Streaming, tool dispatch,
  and usage capture are structurally complete but verified only by smoke test
  (no network). First live call is the Day 6 end-to-end test. Until then,
  "working" means "compiles + instantiates + cost math correct," not "proven
  against the live API."

### Design decisions worth remembering
- `messages.stream()` context manager over `stream=True`: the manager yields
  streamed text and exposes the final accumulated message (with `.usage`) at
  close — no manual event accumulation for token counting.
- Agentic loop lives in the client, not the tool layer: the client owns
  conversation-turn mechanics; tools just return data strings.
- Concurrent tool dispatch via `asyncio.gather`: right pattern for multi-tool
  turns. No measurable benefit yet (handlers are in-memory graph queries), but
  free to do correctly now.
- None of these rose to ADR level — idiomatic SDK usage, not decisions with
  genuine architectural alternatives. The one real Week-8 architecture call so
  far (tool-pull vs pre-loaded context, Option A) gets its ADR when the
  retrieval layer lands, not here.

### Shell learning
- `python -c "..."` with f-strings + `$` breaks under PowerShell quoting; a
  real `.py` file run with `python -m scripts.<name>` sidesteps it.
- Scripts importing `app` must run as `python -m scripts.<name>` from backend/,
  never `python scripts\<name>.py` — the latter puts scripts/ on sys.path
  instead of the package root, so `app` won't resolve.

---

## Week 8 Day 2 — Shared naming module + graph-query tools

### What shipped
- `app/intelligence/graph/naming.py` — extracted name resolution
  (`resolve_one`), node formatting (`fmt_node`), and edge-label logic
  (`edge_relation_label`, `edge_method_detail`, `VIA_LABEL`/`EDGE_LABEL`) out
  of cli.py so the CLI and the orchestration tool layer describe metadata
  identically. ADR-013.
- `cli.py` refactored to import from naming; kept `_resolve_one`/`_fmt_node`
  as thin aliases so existing test import paths still resolve. `_cmd_impact`
  now calls the shared label helpers. Behavior-preserving — full suite stayed
  green across the refactor.
- `app/intelligence/orchestration/tool_definitions.py` — 5 graph-query tools
  Claude can call (find_dependencies, find_references_to, analyze_impact,
  find_by_name, graph_health), as thin async wrappers over QueryEngine,
  reusing naming.py for resolution + labels. Static TOOL_SCHEMAS + a
  build_tools() factory returning (schemas, handler_map) for
  ClaudeClient.register_tool. Returns are lightly-structured text, not JSON
  (tool-pull model — Claude reads these to reason; prose costs fewer tokens
  while preserving name/type/via-label).
- `tests/unit/test_tool_definitions.py` — 21 hermetic tests, incl. a direction
  guard (test_dependencies_and_references_are_opposite_directions) so the
  dependencies/references pair can't be silently inverted, and a Flow-action
  label test asserting "method call" is NOT used for a Flow edge (the Week-7
  mislabel bug, now guarded at the tool layer).
- Verified once against the real cached org (throwaway verify_tools.py, since
  removed): analyze_impact PricingFlowAction reproduced the CLI's "via Flow
  action" → Opportunity_Sales_Orchestration_Flow; graph_health surfaced the
  known correct orphan.
- Suite: 230 → 251.

### Why naming.py came first
Day 2's deliverable is the tools, but they need the same name resolution and
edge labels the CLI uses. Two choices: duplicate the logic (drift risk on the
demo-critical labels) or extract a shared module. Extracted — ADR-013. The
label maps are product vocabulary, not plumbing; they must be single-sourced
so Claude and the CLI never describe the same edge differently.

### Why no ADR for tool_definitions
Building tool wrappers over an existing, tested query engine is a routine
extension, not an architectural decision — no real alternatives or trade-offs
to weigh. The one genuine call (lightly-structured text over JSON returns) is
an application of the tool-pull decision, and folds into the ADR that lands
with retrieval.py. Padding the ADR log with a routine wrapper would blunt it.

### Test discipline note (caught my own fixture mistake)
A test asserted "1 direct dependent" for Helper, but the fixture I wrote gives
Helper TWO dependents (Caller via CALLS + OppSelectorTest via REFERENCES). The
handler counted correctly ("2 direct dependent(s)"); my assertion had the wrong
number. The tight substring assertion caught the mismatch — a looser
"direct dependent" check would have passed and hidden it. Same lesson as the
Week-7 MultiDiGraph story: assert on data correctness, not just "did it run."

### Note to self — test count
Suite is at 251. Was recorded at 201 end of Week 7; reached 230 before today
(the +29 predate this refactor — confirm with git log) and +21 from
test_tool_definitions today. Reconcile the running count in ROADMAP at week's
end.

---

## ADR-013 — Shared name resolution + edge labels in graph/naming.py

**Status:** Accepted
**Date:** Week 8, Day 2

**Decision:** Name resolution (`resolve_one`), node formatting (`fmt_node`), and
edge-label logic (`edge_relation_label`, `edge_method_detail`, plus the
`VIA_LABEL`/`EDGE_LABEL` maps) live in `intelligence/graph/naming.py`. Both
`interfaces/cli.py` and the orchestration tool layer import from it. The CLI
keeps `_resolve_one`/`_fmt_node` as thin aliases so existing tests' import
paths still resolve.

**Alternatives considered:**
- **Leave it in cli.py; have orchestration import from interfaces/cli.py.**
  Zero CLI change, but inverts the dependency direction — orchestration (a core
  layer) would depend on a UI layer. Brittle as the CLI grows UI-specific
  imports (argparse, stdout concerns).
- **Duplicate the ~20 lines into the orchestration layer.** Fastest, but the
  demo-critical label maps would then exist in two places and drift. The CLI
  and Claude would eventually describe the same edge differently — a visible
  product inconsistency.

**Trade-off:** A new shared module + a one-time CLI refactor (and two alias
lines) vs. correct dependency direction and a single source of truth for the
labels that both the CLI demo and Claude's tool output depend on.

**Why this:** The label maps are product-facing vocabulary, not plumbing. They
must be single-sourced. Placing them in the graph layer (where the graph
vocabulary already lives) gives both consumers a downward dependency and kills
the drift risk before it starts. Verified behavior-preserving: full suite green
after the move, and `impact PricingFlowAction` still reports `via Flow action`
identically through naming.edge_relation_label.

**Is this ADR-worthy?** Borderline-yes. Small, but a genuine "where does shared
logic live + which way do dependencies point" decision with a real trade-off
and a wrong answer that would have bitten later. Banked as a "layering
discipline" story, not a marquee architecture call.

---

## Week 8 Day 3 — get_source content-retrieval tool

### What shipped
- `tool_definitions.py` — added `get_source`, a 6th tool that returns raw
  component source: Apex Body (class/trigger) or Flow XML. Resolves a name to
  a node, then branches on node_type:
  - APEX_CLASS/APEX_TRIGGER: node.id IS the cache record_id → cache.get_one →
    Body.
  - FLOW: node.id is synthetic (flow:<name>), so fetch Flow records and match
    on DeveloperName → xml.
  - OBJECT: derived node (ADR-010), no source — returns a clear explanation,
    not an error.
- `build_tools(engine, graph, cache=None, org_key=None)` — cache/org_key now
  optional; get_source is included only when both are supplied. The 5
  graph-query tools never needed a cache, so the signature reflects that.
- Soft 12k-char truncation guard on returned source — a guardrail against one
  pathological large flow/class blowing the context window. NOT token-budget
  management (that's retrieval/compression, Day 5); just a bound with a clear
  [truncated] marker.
- `test_tool_definitions.py` — 21 → 30 tests: get_source across Apex/trigger/
  Flow/Object/unknown/no-body/truncation, plus conditional-inclusion tests
  (no cache → 5 tools, cache → 6). Suite 251 → 260.
- Verified live (throwaway verify_get_source.py, removed): pulled real
  PricingFlowAction Apex and the full Opportunity_Sales_Orchestration_Flow XML
  from the cache through the tool.

### One tool, not two (design note, not ADR)
ROADMAP planned get_apex_source + get_flow_definition. Built as a single
get_source instead: the Apex-id-vs-Flow-synthetic-id asymmetry is incidental
complexity better hidden behind one tool than exposed as two, and in the
tool-pull model Claude shouldn't have to pre-know a component's type to ask
for its source. Application of "let the data drive, hide incidental
complexity" — a tool-shape choice, not an architectural fork. Not ADR-worthy.

### Real-org finding — the graph is missing a real dependency (confirms parked item)
The live Flow XML for Opportunity_Sales_Orchestration_Flow makes the Week-7
parked item concrete. The flow contains:
  - a recordLookups on Opportunity (get_opportunity) — a real Object dependency
    the graph does NOT capture (we only edge the TRIGGER object, not record
    operations)
  - a subflow call to Evaluate_Pricing_Need — captured (Flow→Flow subflow edge)
  - an apex actionCall to PricingFlowAction — captured (Flow→Apex flow_action)
So get_source just gave us eyes on exactly the gap the parked "Flow
record-operation edges" item describes: this flow depends on Opportunity via a
recordLookups, invisible to the current builder. Still parked (not a Day-3
blocker), but now evidenced by real data, not theory.

### Test count
Suite 260. Running reconciliation deferred to ROADMAP at week's end.

---

## Week 8 Day 5 — Tool-pull system-prompt builder

### What shipped
- `app/intelligence/orchestration/system_prompt.py` — `build_system_prompt(graph)`
  assembles Claude's standing context for the tool-pull model: role, live
  orientation (component counts by type, relationship counts by type), edge
  semantics, how-to-reason guidance, and a KNOWN LIMITATIONS block. Orientation,
  not data — every specific name/dependency/source comes through a tool call.
- `tests/unit/test_system_prompt.py` — 8 tests: counts, type/edge breakdowns,
  edge semantics, the find_dependencies/find_references_to direction guidance,
  the limitations block (incl. the recordLookups gap), tool-use-over-guessing,
  and empty-graph handling. Suite 260 → 268.
- Verified live against the real org (throwaway script, removed): prints the
  actual 57-component / 172-relationship snapshot with the 43 ApexClass /
  8 Object / 6 Flow / 1 ApexTrigger breakdown and the limitations block.

### Why this is thin (A1, not A2)
Chose minimal-seed (A1) over seed-plus-names-index (A2). The whole tool-pull
bet is that Claude pulls what it needs; pre-loading even a names list is the
first step down the Option-B slope and should be a deliberate, data-driven
decision, not smuggled into the system prompt. At this org's scale a discovery
round-trip is cheap. Day 6's live run will show Claude's actual tool-call
patterns — that data decides whether a names-index ever earns its tokens.

### Honest-by-design: the limitations block
The prompt tells Claude what the graph does NOT capture — no fields, objects
tracked at object (not field) grain, and Flow record operations
(recordLookups/Creates/Updates) not edged. This is the Day-3 real-org finding
turned into a guardrail: Claude is instructed not to claim completeness the
graph doesn't have. Cheaper to prevent overclaiming in the prompt than to
detect it after.

### Structural decision (see ADR-014)
ROADMAP located this at intelligence/context/retrieval.py alongside planned
compression.py/templates.py — but that package encodes the pre-loaded (Option
B) framing. Under tool-pull there is no retrieval and nothing to compress, so
the file is a system-prompt builder in orchestration/, and the context/ package
is deferred to if/when Option B lands. Folder structure reflects the model we
actually chose, not the one we deferred.

### Test count
Suite 268. Running reconciliation deferred to ROADMAP at week's end.

## ADR-014 — Tool-pull orchestration over pre-loaded context (Option A)

**Status:** Accepted
**Date:** Week 8 (decided Day 2, became load-bearing Day 5)

**Decision:** Claude reasons over the metadata graph by PULLING specifics
through tools. It receives only a thin standing system prompt — role, a
high-level orientation (counts by node/edge type), edge semantics, reasoning
guidance, and the graph's known limitations. Every specific component name,
dependency, and source line comes through a tool call, never the system prompt.

**Alternatives considered:**
- **Option B — pre-loaded context.** Given a user query, a retrieval step
  selects the likely-relevant nodes (e.g. find_by_name + 1-hop neighbours),
  a compression step trims large source, and the result is packed into the
  system prompt up front. Claude uses tools only for follow-up. This is the
  intelligence/context/ package the ROADMAP planned (retrieval.py +
  compression.py + templates.py).
- **A2 — tool-pull plus a thin names index.** Option A, but seed the prompt
  with a names-only list of all components so Claude knows what exists without
  a discovery round-trip.

**Trade-offs:**
- ✅ Tool-pull is simpler — no retrieval heuristic to tune, no compression
  strategy, no relevance scoring. None of those modules need to exist yet.
- ✅ Lowest system-prompt token cost — orientation only, no contents.
- ✅ Lets us OBSERVE Claude's real tool-call patterns (Day 6) before building a
  retrieval heuristic. You cannot tune pre-loading well without first seeing
  what Claude actually reaches for; tool-pull generates exactly that data.
- ✅ No premature structure — the context/ package isn't created for a model
  we deferred (same discipline as Week 6 Day 1's "model what you can populate").
- ❌ Extra round-trips — Claude may call a tool to discover something that
  pre-loading could have handed it. At current org scale this is cheap; at
  large-org scale it may not be (revisit trigger below).
- ❌ A2 would save a discovery round-trip, but a names index is the first step
  toward pre-loading and should be a deliberate Option-B decision, not a
  default. Rejected for now.

**Why this over Option B:** We have no latency SLA, no token-pressure data, and
no observed tool-call patterns yet. Pre-loading requires a good retrieval
heuristic, which can't be tuned without that data. Build the simple, honest
thing first; let real usage tell us whether pre-loading earns its complexity.

**Structural consequence:** No intelligence/context/ package. The orientation
builder lives in orchestration/system_prompt.py. retrieval.py / compression.py /
templates.py are deferred to Option B.

**Option B revival trigger (breadcrumb):** Revisit when EITHER (a) measured
per-query latency from discovery round-trips becomes a real cost, OR (b) the
org scale makes find_by_name discovery expensive, OR (c) Day-6+ tool-call logs
show Claude repeatedly making the same discovery calls that a names-index or
1-hop pre-load would eliminate. At that point Option B is decided with data,
and context/retrieval.py + compression.py earn their package.

---

## Week 8 Day 6 — First end-to-end live call (ask CLI)

### What shipped
- `app/interfaces/ask_cli.py` — the first AI surface. Wires build_system_prompt
  + build_tools + ClaudeClient into one command:
  `python -m app.interfaces.ask_cli "question"`. Streams the answer; announces
  each tool call on stderr (observability for ADR-014); reports token cost via
  SessionUsage. Separate entry point from cli.py on purpose — deterministic
  graph CLI vs probabilistic AI CLI (different cost/output/failure models).
- `tests/unit/test_ask_cli.py` — 7 hermetic tests (parser + _announce wrapper;
  the live call is verified manually, not unit-tested). Suite 268 → 275.
- Explicit load_dotenv() at module top — don't rely on auth.py's incidental load.

### Setup gotcha (worth a line for future-me / cloners)
First live call failed with "Could not resolve authentication method." Cause:
.env.example ships ANTHROPIC_API_KEY commented out, so it was never set.
Fix: real key from console.anthropic.com, uncommented in .env, + $5 prepaid
usage credits (API billing is separate from any Claude.ai subscription).
Diagnostic one-liner to confirm the key loads:
  python -c "from dotenv import load_dotenv; import os; load_dotenv(); print('FOUND' if os.environ.get('ANTHROPIC_API_KEY') else 'MISSING')"

### The payoff — Claude narrated the metadata-graph thesis live
Asked "PricingFlowAction looks never-referenced by Apex — how does it ever get
invoked?" Claude called find_references_to + find_dependencies + analyze_impact
(parallel), found the Flow-action edge, and explained: PricingFlowAction is a
Flow-invocable @InvocableMethod wired by Opportunity_Sales_Orchestration_Flow —
a metadata wire, not a code call — so it looks dead to an Apex scan but isn't.
It even added the developer-pain insight: deleting/renaming it would break the
Flow action step silently at runtime. The Week-7 payoff, now narrated by Claude
through the tools, from natural language. Cost ~$0.024/query (Sonnet 4.6).

### Tool-selection observations (ADR-014 data — A1 vs Option B)
- Direction distinction HELD: for "how is it invoked", Claude correctly chose
  find_references_to (inward), not find_dependencies. Day-2 descriptions work.
- OVER-FETCH signal (log it): on the simple "what does X depend on" query,
  Claude did find_by_name (discovery) THEN find_dependencies, though the name
  was exact. One instance, not yet a pattern. If Claude routinely warms up with
  find_by_name, that's the evidence ADR-014 trigger (c) names for revisiting
  Option B (a names-index would remove the round-trip). Watching.
- find_dependencies returns node names only (no edge label), so Claude hedged
  dependencies as "likely SOQL" rather than stating the mechanism. analyze_impact
  has the label; find_dependencies doesn't. Refinement candidate (add edge label
  to find_dependencies output) — PARKED, not a Week-8 deliverable; the hedge is
  honest, not wrong.

### Cost tracking is realq
SessionUsage printed $0.0247 / $0.0235 per query. Cross-check against the
console Usage page (settings → Usage) — app-layer estimate should match
provider billing within rounding. $5 credits ≈ ~200 queries at this shape.

### Test count
Suite 275. Reconcile running count in ROADMAP at week's end.


## Week 9 Day 1

### Test count reconciliation
Confirmed 275 passing at Week 9 start (matches Week 8 close).
Gap explanation: Week 7 close was recorded as 201 but suite measured 230 at
Week 8 start (+29). Git log confirms the delta came from Week 7 Day commits
(classifier, MultiDiGraph migration, Flow slice, impact command) whose tests
were not reflected in the recorded close number. No missing or phantom tests —
the count is clean. Baseline for Week 9: 275.

### Capability scope locked (Week 9)
1. Metadata Q&A — structurally complete (ask_cli.py). Prompt sharpening only.
   One-shot Q&A for Phase 1. Multi-turn/session state explicitly parked to Week 13.
2. Apex explanation/refactoring — new system prompt + mode + entry-point wrapper.
3. SOQL generation — new system prompt + mode + entry-point wrapper.
   Honest scope: object/class awareness only; no field validation (FIELD nodes parked ADR-010).
4. Deployment impact analysis — new system prompt + mode + entry-point wrapper.
5. Debug log analysis — PARKED. Revisit Week 12.
   Rationale: descoped version doesn't exercise the graph; real version is 2-3 days.
   Four solid graph-exercising capabilities is the stronger portfolio story.

### Architecture decision: mode-dispatch
One shared orchestration surface. ask_cli.py gains a --mode flag (or mode
parameter). Thin entry-point wrappers (ask_apex.py, ask_soql.py, ask_impact.py)
added inline as each capability is built — not deferred to Week 14.

## Week 9 Day 2 — Capability 2: Apex explanation/refactoring

### What shipped
- apex mode live-verified against real org. `--mode apex "Explain TriggerDispatcher..."`
  produced a graph-grounded explanation: pulled get_source + find_references_to +
  find_dependencies (+ transitive), anchored refactoring advice to the dependency graph.
- Headline result: Claude flagged TriggerDispatcher as DEAD CODE (zero inbound refs) —
  an insight only possible WITH the graph; a plain LLM reading source alone can't know
  nothing references it. Apex-mode equivalent of the Week-8 PricingFlowAction payoff.
- Self-discovered the org's SECOND trigger framework (MetadataTriggerHandler /
  CaseObjectTrigger) by exploring outward; flagged the architectural inconsistency.
  Unprompted — followed the graph.
- `app/interfaces/ask_apex.py` — thin wrapper, main(default_mode="apex"). Clean
  portfolio entry point. Verified via --help (default: apex) + import; no extra
  live call (apex path already proven this session — don't burn credit re-proving).

### Cost observation (real Option-B / budget data)
- apex query cost $0.088 vs qa baseline ~$0.024 — 3.7x. Cause: get_source pulled
  4 full source bodies (19,190 input tokens). apex is the MOST EXPENSIVE capability
  because it reads source aggressively. impact (no get_source) will be cheapest.
- Note: this cost is SOURCE-READING, not discovery round-trips — pre-loading (Option B)
  would NOT reduce it. Different cost axis than the names-index question.

### ADR-014 watch — over-fetch is now 2 instances (not yet "repeated")
- find_by_name('TriggerDispatcher') THEN get_source('TriggerDispatcher') — warm-up
  on an EXACT name, same as Week-8 Day-6. Second data point, same pattern.
- Distinct from the legitimate find_by_name('Trigger') mid-stream (broad discovery,
  tool working as intended). Only the warm-up-on-exact-name is wasteful.
- If Day 3 (soql) shows a third warm-up, the names-index conversation becomes real.
  Trigger (c) approaching, not yet met.

### Tests
- No new tests (apex prompt + wrapper covered by Day-1 tests: build_apex_prompt
  assertions + registry contract + default_mode override). Suite 296.

## Week 9 Day 3 — Capability 3: SOQL generation

### What shipped
- soql mode live-verified. "Write SOQL for Opportunities closed this quarter
  with amount and stage" → Claude ran find_references_to(Opportunity) →
  get_source(OpportunitySelector), read REAL SOQL, and grounded fields in it.
- THE HONESTY HELD: per-field provenance table distinguished grounded fields
  (Id/Name/StageName/Amount — "confirmed in OpportunitySelector") from
  platform-knowledge fields (CloseDate — "standard Salesforce field") from
  uncertain ones (Account.Name — "verify if needed"). The verify caveat fired.
- Grounding confirmed genuine: `cli find Opportunity` shows OpportunitySelector
  is a real ApexClass. Claude did not hallucinate the grounding source.
- `app/interfaces/ask_soql.py` — wrapper, main(default_mode="soql"). Verified
  via --help + import; no extra live call.

### The precise scope boundary (interview-ready honesty, ADR-010)
soql mode grounds CUSTOM/QUERIED fields in real source (the differentiator).
But STANDARD fields (CloseDate, IsWon, IsClosed) rest on Claude's platform
priors, NOT org verification — the graph has no field nodes, so there's no way
to verify a standard field against THIS org. Safe for genuinely-universal fields;
the gap would show on a field Claude believes is standard but that's custom/
renamed in a given org. Honest answer to "how do you know CloseDate exists in
their org?" → "we don't verify standard fields; that's the FIELD-node gap."
Documentation item, not a prompt fix — the output was correct.

### Cost & Option-B watch
- $0.037 — between qa ($0.024) and apex ($0.088), as predicted. One source read.
- NO warm-up over-fetch. soql's find_by_name calls are PROMPT-DIRECTED (step 1
  "confirm the Object exists"), not wasteful warm-ups. Over-fetch count stays 2.
- Note: soql's find_by_name can't be read as Option-B evidence either way —
  the prompt induces it. apex/qa warm-ups remain the clean signal.

### Tests
- No new tests (soql prompt + wrapper covered by Day-1 tests). Suite 296.

## Week 9 Day 4 — Capability 4: Deployment impact analysis

### What shipped
- impact mode live-verified. "Deployment impact if I change PricingFlowAction?"
  → all 5 structured sections (DIRECT/TRANSITIVE/RELIES ON/RISK/CHECKS), rated
  HIGH correctly (Flow dependency = High per rubric), and reproduced the Week-8
  Flow-vs-Apex insight GENERATIVELY: Flow Action binding isn't compile-time
  validated, so a signature change fails silently at runtime.
- get_source-free exclusion HELD PERFECTLY. Claude worked from topology alone
  (analyze_impact + find_references_to --transitive + find_dependencies), never
  flailed for source. Day-1 exclusion call validated.
- Cheapest non-qa capability: $0.0298 (5,182 in tokens vs apex's 19,190). As predicted.
- `app/interfaces/ask_impact.py` — wrapper, main(default_mode="impact").

### CRITICAL FINDING — deterministic CLI audited the AI, skeleton grounded but commentary over-narrates
Ran the deterministic cli.py as ground truth against Claude's claims:
  - `cli impact PricingFlowAction` → 1 inbound: Opportunity_Sales_Orchestration_Flow
    via Flow action. ✅ matches Claude's DIRECT exactly.
  - `cli dependencies PricingFlowAction` → OpportunitySelector, PricingService.
    ✅ both real — Claude did NOT invent the RELIES ON table.
  - `cli depends-on PricingFlowAction --transitive` → +URSIP_Opportunity_After_Save.
    ✅ transitive edge real.
VERDICT: every node/edge Claude named is REAL. The skeleton is exact. What's NOT
graph-established is the interpretive PROSE layered on top — "PricingService =
core pricing logic" (never read it, no get_source), "if its query interface
changes" (inferred mechanism), "could corrupt the entire orchestration." Confident
risk commentary that outruns what the edges license. For a DEPLOYMENT tool —
output developers act on — that's the riskiest place to over-narrate.

### Two coupled findings → Week 10 (deferred, do NOT band-aid now)
1. Refinement #10 (edge labels on find_dependencies) is now LOAD-BEARING, not
   optional. Claude over-narrates partly BECAUSE find_dependencies/depends-on
   strip the via-label — it has the node but not the relationship kind, so it
   guesses mechanism ("likely calls it as a subflow" hedge = same root cause).
2. impact prompt over-narration.
COUPLING + ORDER: do #10 FIRST in Week 10, then re-run this exact PricingFlowAction
query and check if over-narration self-corrects before touching the prompt. The
narration may largely fix itself once Claude has the mechanism. Only tighten the
prompt for embellishment that REMAINS after the data gap closes. Fixing prompt
before data = band-aid you'd delete. Decided to defer (Veda's call): superseded
work isn't worth doing twice.

### Option-B watch — warm-up signal now hard to isolate
impact's find_by_name is PROMPT-DIRECTED (step 1), like soql. 3 of 4 capabilities
now induce find_by_name in step 1 by design — so find_by_name-then-act is mostly
DESIGNED, not waste, across the MVP. Over-fetch count stays 2 (apex + qa warm-ups
on exact names remain the only clean signal). Noting: the prompts are making the
warm-up pattern harder to detect, which itself is Option-B-relevant.

### Tests
- No new tests (impact prompt + wrapper covered by Day-1 tests). Suite 296.

## Week 10 Day 1 — Refinement #10: edge labels on find_dependencies

### What shipped
- `QueryEngine.outgoing_edges()` — outward mirror of `incoming_edges()`.
  Uses `self._nx.out_edges(node_id, keys=True, data=True)`, returns full
  Edge objects with via/method attributes, sorted by target name. Inserted
  immediately after `incoming_edges` in the Edge-level queries block.
- `find_dependencies` handler updated — direct mode now calls
  `outgoing_edges()` instead of `what_does_it_depend_on()`, emits
  `- {target} via {relation}{detail}` per dependency. Transitive mode
  intentionally stays node-list-only: per-hop labels across a multi-hop
  chain are noise, not signal. Mechanism belongs on the direct hop.
- 8 new tests: 6 in test_graph_query.py (outgoing_edges — mirrors the
  incoming_edges test structure with source/target swapped), 2 in
  test_tool_definitions.py (label present in direct output, no via-label
  in transitive output).
- 1 test correction: test_find_dependencies_direct_includes_relation_label
  initially asserted "name reference" (REFERENCES edge) — fixture edge is
  actually CALLS, label is "method call". Fixed before final run.
- Suite: 296 → 304 passing.

### Why this is load-bearing (not optional polish)
find_dependencies was returning node names only — Claude had the target
but not the relationship kind, so it guessed mechanism. "Core pricing
logic", "if its query interface changes" — confident prose that outran
what the edges license. With outgoing_edges feeding the handler, Claude
now sees "via method call (publishPricingEvent())" and has no reason to
invent an explanation. Data fix before prompt fix — the coupling order held.

### Smoke test confirmed
Synthetic graph smoke test output:
  PricingFlowAction (ApexClass) has 2 direct dependenc(ies):
  - OpportunitySelector (ApexClass) via SOQL/DML query
  - PricingService (ApexClass) via method call (calculate())
Mechanism present, format matches analyze_impact vocabulary. Ready for
live re-run on Day 2.

### ADR note
No new ADR. outgoing_edges is a routine symmetric extension of an
existing pattern — no genuine architectural alternatives to weigh.
The design decision (direct=labels, transitive=nodes) is documented
in the handler comment and the test assertion.

## Week 10 Day 2 — Refinement #10 live verification

### Re-run: PricingFlowAction impact query post-fix

Ran the exact Week-9-Day-4 query that exhibited over-narration:
`python -m app.interfaces.ask_impact "What is the deployment impact of PricingFlowAction?"`

### Self-correction verdict: COMPLETE

The over-narration self-corrected without prompt changes.

RELIES ON table (the failure site in Week 9):
- Week 9: "core pricing logic", "if its query interface changes" — inferred
  from node name, no graph basis
- Week 10: "CALLS byIds() method + name reference", "CALLS publishPricingEvent()
  method + name reference" — stated from edge data, graph-grounded

Root cause confirmed: find_dependencies was stripping the via-label, forcing
Claude to guess mechanism. With outgoing_edges feeding the handler, Claude
has the method name and edge type — it states the coupling and stops.

### What remains (acceptable, not over-narration)
- Cascade claim ("if signatures change, cascades to both flows") — correct
  inference from a CALLS edge; method calls couple on signatures. Graph-licensed.
- RECOMMENDED CHECKS #3/#4 (subflow variable mappings, @InvocableMethod
  signature) — Salesforce platform knowledge about what Flow-action edges mean
  operationally, not claims about unread code. This is the tool's value-add.

### Coupled fix complete — prompt tightening not needed
Order held: data fix first, self-correction checked, prompt untouched.
No band-aid applied. Cost: $0.0414 (vs $0.0298 Week 9 — slightly higher,
3-turn session vs likely 2-turn; tool-call pattern still disciplined,
0 warm-up over-fetches in impact mode).

## Week 10 Day 3 — Semantic eval harness

### What shipped
- `evals/` package: eval_case.py (EvalCase dataclass), eval_runner.py
  (runner + report), cases/ (qa/apex/soql/impact, 5 cases each).
- 20 cases total across 4 capabilities. One command: `python -m evals.eval_runner`.
  Optional --mode flag for single-capability runs.
- Assertions: required substrings (grounding + structure) + forbidden substrings
  (known failure modes). Full AI output printed on failure — diagnose without
  re-running. Excluded from default pytest suite (live API, real cost ~$0.035/case).
- 20/20 passing on first clean run. Total cost $0.78.

### One case fix mid-run
impact case 2 ("States mechanism via edge label") initially required "method call"
— too brittle, one specific phrase from one tool-call path. Fixed to require "via"
+ forbid the Week 9 over-narration phrases ("core pricing logic", "query interface").
Correct behavior: assert what we're guarding (no invented mechanism), not how
Claude phrases a specific correct answer.

### Harness design notes
- Cases target specific known failure modes, not generic "does it answer."
  The forbidden strings are the regression guard; the required strings are
  the grounding check (real node names must appear).
- Non-determinism handled by asserting vocabulary, not exact phrasing.
- Transitive assertions (URSIP in impact cases) verify multi-hop reasoning
  works end-to-end, not just direct lookup.
- Cost ledger: ~$0.70-0.78/full run. Weekly regression cadence, not CI.

### Week 10 complete
304 unit tests + 20 semantic evals. All green.
Coupled fix (Refinement #10 + self-correction check + harness) delivered
in 3 days as planned. No prompt tightening needed — data fix was sufficient.
MCP server starts fresh in Week 11.

## Week 11 Day 1 — Non-streaming _ask variant + MCP server scaffold

### Environment reconciliation (week start)
- Claude Desktop: INSTALLED (Anthropic PBC, per Apps list). config json not yet
  created — normal, it's written when the first MCP server is registered (Day 3).
- Claude Code: NOT installed (`claude` not recognized). Install at Day 4 start.
- Augment AI: installed + enabled for this workspace (v0.859.7). No `mcp` key in
  VS Code settings.json — MCP config path TBD; resolve before Day 4.
- ROADMAP/README stale for Week 11 (still say 5 capabilities + Cursor) — update Day 5.

### What shipped
- `ClaudeClient.ask_collected()` — non-streaming variant. Thin consumer of
  ask(): iterates its own stream, joins chunks, returns one string. Owns NO
  loop logic — agentic loop, tool dispatch, cost tracking, max_iterations all
  stay in ask() (no duplication; ADR-013 discipline). MCP tool responses are
  single strings, so this is the bridge. Cost still on client.session after.
- `app/interfaces/mcp_server/` package created (__init__.py + server.py).
- `server.py` — Day 1 scaffold: FastMCP("salesforce-metadata-graph"), stdio
  transport, lazy graph bootstrap (_get_engine, module-cached), one `health`
  tool. Capability tools deferred to Day 2.

### Design decisions
- Lazy-load over eager: a long-lived server that exits at startup shows in the
  host as "failed to connect" with no readable reason. Lazy + GraphLoadError →
  server starts clean, returns a readable error STRING on first tool call if
  cache/tokens missing. Better failure ergonomics for the Day 3-4 debugging.
- GraphLoadError, not SystemExit: ask_cli._load() raises SystemExit (right for a
  one-shot process). A long-lived server must not kill itself on one bad call.
- stdout reserved for JSON-RPC: logging forced to stderr. A stray stdout print
  corrupts the protocol stream — the #1 MCP "won't connect" cause. Guarded.
- Graph loaded ONCE per process (vs ask_cli's per-invocation _load): the server
  is long-lived; rebuilding the 57-node graph per tool call would be wasteful.
- Working dir: _CACHE_PATH is relative to backend/ (same as cli.py/ask_cli.py).
  Server must launch from backend/. Client configs (Day 3-4) set this explicitly.

### Verification (honest status)
- ask_collected: compiles; both ask + ask_collected present; 304 tests green
  (pure addition, existing streaming path untouched).
- server.py: compiles; imports resolve; health tool registered; mcp named.
  Smoke test — server starts, logs the startup line, blocks on stdin waiting
  for a client (the pass condition). The Ctrl+C teardown produces a noisy
  WouldBlock→CancelledError→KeyboardInterrupt stack — harmless; that's anyio
  unwinding an interrupted blocked-wait, NOT a server error. Under a real host
  the process gets a clean shutdown, so the noise never appears in production.
- No live MCP client test yet — that's Day 3 (Claude Desktop). "Working" today
  means "starts, registers tools, transport initializes," not "proven end-to-end
  through a client." Same staging as Week 8 Day 1 (client compiled before live).
- No new unit tests: scaffold verified manually (same rationale as ask_cli — the
  blocking stdio loop isn't unit-testable; the real test is the Day 3 client).

### Carry-forward
- Day 2: wire 4 capability tools (qa/apex/soql/impact) over ask_collected,
  error handling, per-call cost reporting.
- mcp package added to env — add to requirements.txt on Day 2.
- Option-B/ADR-014: still tool-pull, no trigger met. (No new evidence today —
  no live calls made.)

## Week 11 Day 2 — Four capability tools wired + cost reporting (live-proven)

### Architecture decision: extract capabilities.py (Option A)
The MCP tools needed the middle of ask_cli._ask (mode → prompt + tool-subset →
configured client), but _ask returns None and streams — not reusable as-is.
Chose to EXTRACT that core to orchestration/capabilities.py rather than
duplicate the subsetting in server.py. Reasoning: CAPABILITY_REGISTRY is the
single source of truth for "impact excludes get_source" etc.; a second
enforcement point would drift (the exact CLI-vs-tool-layer duplication ADR-013
exists to prevent). Also a layering point (ADR-001): server.py importing the
registry from ask_cli would make one interface depend on another — siblings
shouldn't. capabilities.py sits in the orchestration layer below both. This is
the module the ROADMAP target structure already named ("capabilities.py — the
5 capabilities"); it arrived on schedule, not as new scope.

### What shipped
- `orchestration/capabilities.py` (NEW) — owns _ALL_TOOLS, _GRAPH_ONLY,
  CAPABILITY_REGISTRY, VALID_MODES, and build_capability_client(mode, engine,
  graph, cache, org_key, *, handler_wrapper=None) -> (client, schemas). One
  function: registry lookup → prompt build → build_tools → subset → register.
  handler_wrapper hook lets each interface add its own observability without
  the builder knowing CLI from MCP. Raises ValueError (not SystemExit) on bad
  mode — callers decide.
- `ask_cli.py` (refactored) — imports + re-exports CAPABILITY_REGISTRY/
  VALID_MODES/_ALL_TOOLS from capabilities (back-compat aliases, same trick
  cli.py used in the ADR-013 refactor so test_ask_cli's import paths resolve).
  _ask now calls build_capability_client. _load, _announce, parser, main
  untouched. Streaming behaviour byte-identical.
- `mcp_server/server.py` — four capability tools (metadata_qa, explain_apex,
  generate_soql, analyze_deployment_impact) + health. All route through
  _run_capability(mode, question): cached engine → shared client wiring →
  ask_collected (NON-streaming, single string) → compact cost footer + stderr
  cost log. _log_tool wrapper logs INTERNAL agentic-loop tool calls to stderr
  (host can't see them; this is the Day 3-4 debugging window).

### Verification
- build_capability_client subsetting validated in isolation (stubbed app deps):
  qa/apex/soql get all 6 tools; impact excludes get_source; correct prompt per
  mode; wrapper applied to every handler; ValueError on unknown mode.
- Full suite 304 passing — refactor held; re-export aliases keep test_ask_cli
  green. No new unit tests (capability tools are thin wrappers over the proven
  build_capability_client + ask_collected; the real test is the Day 3 host call).
- LIVE end-to-end: server.metadata_qa("How is PricingFlowAction invoked...")
  drove a 3-turn loop, called find_references_to/find_dependencies/
  analyze_impact + get_source×2, returned the correct @InvocableMethod /
  via-Flow-action answer with cost footer. Proves ask_collected drives the loop
  and returns one string. Cost $0.0433 (qa, but source-reading — higher than
  Week-9's ~$0.024 simple-qa; tracks apex profile because it did apex-like work;
  not a regression).

### Stale-download gotcha (future-me)
First server.py copy registered only `health` — browser had saved the Day-2
download as "server (1).py" and Copy-Item grabbed the stale Day-1 "server.py".
Fingerprint check before trusting a copied file:
  Select-String -Path <file> -Pattern "@mcp.tool\(\)" | Measure-Object | Select -ExpandProperty Count

### Carry-forward
- Day 3: install/verify Claude Desktop, register the server, test all 4 tools
  through the host on Windows. The _log_tool stderr lines are the debug window.
- Cost footer currently goes IN the tool response (host's Claude sees it). Fine
  for now (transparency + demo); move to stderr-only if it adds noise in Day 3.
- requirements.txt: mcp pinned this commit (was deferred from Day 1).
- Option-B/ADR-014: still tool-pull. Live qa pulled get_source twice on a
  source-needing question — expected, not a discovery over-fetch. No trigger.

## Week 11 Day 3 — Claude Desktop end-to-end (all 4 capabilities proven)

### Outcome
All four capabilities (qa/apex/soql/impact) verified end-to-end THROUGH Claude
Desktop on Windows: correct tool routing, correct answers, clean stderr cost
logging, encoding fixed. health + 4 capability tools all live in the host's
connector list. Transport chain proven: host spawn → handshake → import
resolution → graph load → agentic loop → response back through MCP.

### Per-capability cost THROUGH MCP (first real baseline)
  qa     2 turns  $0.0210
  apex   3 turns  in=8452  out=1299  $0.0448
  soql   4 turns  in=13465 out=1165  $0.0579
  impact 5 turns  in=14793 out=1492  $0.0668
Cost scales with turn count, which scales with graph-walking depth (impact
traces transitive blast radius → most round-trips). All under the <$0.10/query
Phase-1 gate. Slightly above direct-CLI numbers — the host adds a framing turn,
expected.

### ROOT CAUSE of the day: Claude Desktop does NOT honour `cwd`
The config `cwd` field was silently ignored — the server launched from
C:\Windows\System32, not backend/. This bit twice:
  1. ModuleNotFoundError: No module named 'app' (import resolution).
  2. Cache resolved to C:\Windows\System32\data\metadata_cache.db (not found).
Fix — make the server cwd-INDEPENDENT, since we can't fix how the host launches:
  - PYTHONPATH via the config `env` block (env IS honoured, unlike cwd) →
    fixes `app` import.
  - _BACKEND_DIR = Path(__file__).resolve().parents[3]; cache path resolves from
    SF_CACHE_PATH env var, else <backend>/data/... relative to the source file.
    .env also loaded from _BACKEND_DIR/.env (not cwd-searched). Fully cwd-free.
  - ask_cli.py left untouched — short-lived, user launches from backend/, cwd
    correct there. Only the host-launched server needed hardening.
This is correct hardening regardless of host, not a Desktop-specific hack.

### Cost footer → stderr-ONLY (Day-1 decision, now settled with data)
The in-response cost footer does NOT survive the MCP host round-trip. Verified:
the server sent the footer in the tool result (seen in mcp-server log payload),
but Claude Desktop's model absorbed the tool result as content to interpret and
rewrote the answer WITHOUT the footer — invisible to the user, while still
cluttering the model's context. Removed the footer from the response string;
kept the stderr `capability=... in=... out=... cost=$...` log line (reliable,
in a channel we control). Cost reporting deliverable still met — just on the
right channel.

### UTF-8 forced on stdio
Day-3 logs showed `·`→`Â·`, `—`→`â€"` — Windows defaulting stdout/stderr to
cp1252. Forced sys.stdout/stderr.reconfigure(encoding="utf-8") at startup
(guarded for hosts that swap the streams). Protects tool ANSWERS (Apex/SOQL/
punctuation) the model reads, not just log cosmetics.

### Windows / MSIX gotchas (for docs/mcp-server.md troubleshooting)
- Claude Desktop is an MSIX install: logs + the config the app actually reads
  live under
  %LOCALAPPDATA%\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Roaming\Claude\
  NOT the documented %APPDATA%\Claude\. "Edit Config" opens the real one.
- Window-close does NOT reload config — app stays in the tray. Must fully Quit,
  or force: Get-Process *claude* | Stop-Process -Force, then relaunch.
- JSON is unforgiving: a hand-edit dropped the file's leading `{` →
  "Extra data: line 1 column 13". Validate before restart:
  python -c "import json; json.load(open(r'<path>', encoding='utf-8-sig'))"
- Diagnosis path that worked: read mcp-server-<name>.log — it shows the exact
  Python error (ModuleNotFoundError, then GraphLoadError) on each failed launch.

### Verification
- 304 tests still green (server changes don't touch tested paths).
- All 4 capabilities answered correctly through the host; impact confirmed
  TOPOLOGY-ONLY through MCP (the _GRAPH_ONLY subset correctly excluded
  get_source — the one code path the other three don't exercise).

### Carry-forward
- Day 4: install Claude Code; configure + test Claude Code AND Augment AI.
  Reuse the same cwd-independent server — only client configs differ. The
  PYTHONPATH/SF_CACHE_PATH/UTF-8 hardening should make other hosts smoother.
- Augment AI MCP config path still unknown — discovery step needed (NOTES Day 1).
- Config saga is the seed of the Day-5 docs/mcp-server.md troubleshooting section.
- Option-B/ADR-014: still tool-pull. impact pulled 5 turns of graph tools through
  the host as expected — no repeated-discovery over-fetch pattern. No trigger.

## Week 11 Day 4 — Cross-client verification (Claude Code + Augment AI)

### Outcome
All 3 target clients proven END-TO-END on a real capability (not just health):
  - Claude Desktop  ✓ (Day 3)
  - Claude Code     ✓ (today)
  - Augment AI      ✓ (today)
Same unchanged cwd-independent server across all three. Zero server code
changes between clients — only per-host registration differs. The protocol-not-
vendor thesis, proven: build to stdio MCP, hosts are interchangeable.

### Claude Code
- Installed via official native PowerShell installer (irm claude.ai/install.ps1
  | iex). v2.1.168. Native installer — no Node needed (npm method deprecated 2026).
  Binary → %USERPROFILE%\.local\bin\claude.exe.
- PATH gotcha: installer added .local\bin to USER PATH (registry) but VS Code's
  integrated terminal caches the env from when VS Code launched — `claude` not
  found until VS Code FULLY restarted (reopening just the terminal panel is not
  enough). Verified binary worked via full path before fixing PATH.
- Registered: `claude mcp add salesforce-metadata-graph --scope user --env
  PYTHONPATH=... --env SF_CACHE_PATH=... -- <python> -m
  app.interfaces.mcp_server.server`. Stored in ~/.claude.json. Same env-var
  shape as Desktop — cwd-independence meant it dropped straight in.
- `claude mcp list` → ✓ Connected. health + impact both correct through the
  interactive `claude` session. Host model: Opus 4.8 (its choice). Routed
  correctly to analyze_deployment_impact; answer topology-only as designed.
- Login: chose "Claude account with subscription" (Pro) for Claude Code's OWN
  model usage. Distinct from the server's internal Sonnet calls (billed to the
  project ANTHROPIC_API_KEY / $5 credits). Two independent billing layers —
  noted for open-core economics (who pays for server inference = Phase-2 Q).

### Augment AI
- MCP config path (the Day-1 unknown), resolved: Augment panel → Settings →
  Integrations → MCP Servers → "Import from JSON" button. Pasted the same
  mcpServers JSON (command/args/env). Augment keeps env vars in their own
  section, so PYTHONPATH/SF_CACHE_PATH carry cleanly.
- Result: list shows "● salesforce-metadata-graph (5) tools" — green, all 5
  tools discovered, connected on import. health + impact both correct through
  an Augment AGENT thread (MCP tools are an Agent feature, not Chat/Completions).
- "AUGMENT: SYNCING PERMISSION NEEDED" banner was about codebase indexing, NOT
  MCP — MCP connected & ran fine regardless. The Day-1 auth worry was a non-issue.
- Augment's own docs caveat (not all servers model-compatible) did not bite —
  full capability path worked.

### Why this all "just worked" on clients 2 & 3
The Day-3 hardening (PYTHONPATH for import resolution, file-relative/SF_CACHE_PATH
for the cache, UTF-8 stdio) was the correct host-independent fix, not a Desktop
patch. Clients 2 and 3 each took one registration step and connected first try.
The pain was all Day 3 (one host); the generality paid off here.

### Cross-client config reference (for docs/mcp-server.md, Day 5)
  Claude Desktop: claude_desktop_config.json (MSIX path), cwd+env block.
  Claude Code:    claude mcp add ... --env ... -- <cmd>  (→ ~/.claude.json)
  Augment AI:     Settings → MCP Servers → Import from JSON (env in own section)
All three consume the same command/args/env triple.

### Carry-forward
- Day 5: docs/mcp-server.md (install + all-3-client config + troubleshooting:
  the cwd/PYTHONPATH issue, MSIX log paths, JSON pitfalls, VS-Code-terminal PATH
  cache, full-quit-to-reload). README update. Stale ROADMAP (5 caps + Cursor)
  → fix to 4 caps + the actual 3 clients.
- Consider committing a docs/examples/claude_desktop_config.example.json with
  placeholder paths (canonical example + backup).
- Option-B/ADR-014: still tool-pull. No new signal — clients just relay tool
  calls; the loop behaviour is unchanged from Day 3. No trigger.

## Week 11 Day 5 — Documentation + week-end reconciliation

### What shipped
- `docs/mcp-server.md` — the MCP server install & config guide. Covers: the 5
  exposed tools (health + 4 capabilities), prerequisites (Python 3.11+, populated
  cache, ANTHROPIC_API_KEY), the cwd-independence rationale, per-client config for
  all 3 hosts (Claude Desktop / Claude Code / Augment AI), verification via health,
  cost reporting (stderr, two billing layers), and a troubleshooting section that
  is a direct distillation of the Day 3-4 failures (No module named 'app' →
  PYTHONPATH; cache-not-found → SF_CACHE_PATH; MSIX log path; JSON validation;
  VS Code terminal PATH cache; full-quit-to-reload; UTF-8 garbling; host/model
  compatibility differences). Paths written as placeholders for public/open-core.
- ROADMAP reconciled (Option A — fix errors inline + append actuals, same as
  Weeks 9/10): Week 11 goal 5→"developer capabilities (4, debug-log parked)";
  SDK name corrected to the official `mcp` package; Cursor→Augment AI in
  deliverables and Definition-of-Done; "Week 11 actuals" block appended; DoD
  MCP line checked off.

### Decision: README rewrite DEFERRED to Week 14
README is frozen at Week 4 state (says "9 REST endpoints, 19 tests, coming soon:
metadata graph"). Considered updating now; deferred deliberately. Reasoning:
Week 14 Day 2 already schedules the full public-facing README polish (hero,
screenshots, quick start, full feature list) when the VS Code extension + demo
exist. A heavy rewrite now would be redone in 3 weeks. Prior weeks correctly
skipped README updates because nothing public existed; Week 11 is the first
public artifact, so the ONLY real risk is the repo's public face misrepresenting
the MCP server. Mitigation: don't share the repo link before Week 14, and a
10-min "remove contradictions" touch is available if that changes. Tracked in
two places: Week 11 actuals (what happened) + a new Week 14 Day 2 bullet (what
to do). Not silently dropped.

### Capability count clarified (recurring reconciliation)
docs say 4 capabilities, debug-log noted as planned-not-stubbed. Considered
building the 5th today; declined — it needs a real log parser (~2-3 days), is
scoped for Week 12, and cramming a thin version onto a docs day breaks the
no-stubs decision. Four graph-exercising capabilities remains the stronger
portfolio story. Held the line.

### Shell note
Hit "'Copy-Item' is not recognized" — terminal was cmd.exe (bare `D:\...>`),
not PowerShell (`PS D:\...>`). All project command blocks are PowerShell; run
`powershell` first, or open a PowerShell terminal via the VS Code terminal
dropdown. Fingerprint for future-me: no `PS` prefix = wrong shell.

### Carry-forward
- README full rewrite → Week 14 Day 2 (explicit bullet added).
- docs/examples/claude_desktop_config.example.json (placeholder paths) — nice-to-
  have, deferred; the config block is already in docs/mcp-server.md.
- Option-B/ADR-014: still tool-pull. Documentation day — no new tool-call
  evidence. No trigger.

## Week 12 Day 1 — REST foundation: shared graph loader + decisions locked

### ADR-015 — Shared graph loader (intelligence/graph/bootstrap.py)
Context: tokens→cache→build→engine existed in 3 hand-copied variants
(ask_cli._load, cli._load_graph, MCP _get_engine); REST would be the 4th.
Drift risk — e.g. the cwd-independence fix lived only in MCP.
Decision: extract a PURE, timing-agnostic load_graph(cache_path=None) ->
(engine, graph, cache, org_key) raising a shared GraphLoadError. Lifecycle
stays at each edge: CLI per-invocation/SystemExit, MCP lazy+module-cache/
error-string, REST eager-in-lifespan/503. Cache path resolved cwd-independently
(SF_CACHE_PATH or file-relative).
Consequences: REST consumes it now. MCP/CLI keep their loaders this week and
migrate in the Day-6 buffer (behaviour-preserving, suite-green) so proven
surfaces aren't disturbed mid-deliverable. GraphLoadError still also defined in
server.py; the MCP migration deletes the local copy. Status: Accepted.

### ADR-016 — REST capability surface: four explicit routes
Decision: four named routes (/api/v1/metadata-qa, /apex-explain, /soql-generate,
/deployment-impact), each a thin wrapper over one shared internal handler.
5th capability (debug-log) drops in as one more route.
Rationale: typed/discoverable client surface for the Week-13 extension;
per-capability clarity in /docs; near-zero cost via build_capability_client.
Mode-parametrized single route rejected (opaque, validation-in-body, weaker
generated client). Consequence: route shape is now a public compatibility
surface. Status: Accepted.

### Auth gating: precondition (not caller auth — API keys stay Phase-2).
Missing graph → 503, not 401 (consumer can't fix by re-authing; it's server
readiness). Reuses Week-4 OAuth state via the loader's token check.

### SSE: sse-starlette (heartbeat over quiet tool-turns + disconnect cancel). Pinned.

### Shipped: bootstrap.py + GraphLoadError; 5 hermetic tests (precondition trio
+ happy path + env override). Pure addition; suite green.

### Shipped (Step 2): qa endpoint end-to-end
- main.py lifespan: eager-but-tolerant load_graph -> app.state.graph_bundle
  (None on failure, no crash — keeps account endpoints + tests up).
- dependencies.get_graph_engine: 503 when bundle is None (precondition gate).
- routes/capabilities.py: POST /api/v1/metadata-qa. Four-routes-one-handler seam
  (_capability_response); SSE via EventSourceResponse; REST = STREAMING consumer
  of ask() (mirror of MCP's collected consumer).
- 3 hermetic route tests (503 / streams chunks / 422 empty question).
- Live-verified against the real 57-node graph through Claude over SSE.
- Thin pattern proven: apex/soql/impact on Day 2 are one _capability_response
  call each; debug-log (if it survives the Day-3 gate) is one more route.

## Week 12 Day 2 — REST completion: all 4 capability routes + /graph + tests
- capabilities.py: apex-explain / soql-generate / deployment-impact added — each
  one _capability_response(mode,...) wrapper over the Day-1 seam. impact's
  _GRAPH_ONLY subset handled in build_capability_client (routes stay uniform).
- routes/graph.py: GET /api/v1/graph — deterministic GraphSummary (node/edge
  counts + per-type breakdowns) from MetadataGraph.stats(). No Claude/SSE/cost;
  own "graph" OpenAPI tag; behind get_graph_engine (503 if absent).
- main.py: graph router wired (imported as graph_routes to avoid shadowing the
  lifespan's local `graph`).
- Tests: test_rest_capabilities.py rewritten — parametrized 503 (4) +
  streaming/mode-routing (4) + empty-question 422 (1) = 9. test_rest_graph.py
  new — 503 + counts (2). Suite 312 -> 320.
- docs/examples/claude_desktop_config.example.json added (placeholder paths;
  mirrors docs/mcp-server.md so they can't drift).
- Error handling covered: 422 malformed (Pydantic), 503 graph-absent
  (dependency), loop/API failure -> SSE 'error' event.
- Seam confirmed: 5th capability (debug-log, if it clears the Day-3 gate) is one
  registry entry + one route. REST = Week 12 committed deliverable: LANDED GREEN.

## Week 12 Day 3 — Capability 5 (debug-log): parser + GATE PASS

### Step 0 — real-log capture (the gate's input)
- Opportunity DML (Log1/Log2): Flow-only automation — ZERO METHOD_ENTRY,
  apex_units empty -> would have FAILED the gate. Real finding: Opportunity is
  Flow-driven, not Apex; wrong capture target, not a dead capability.
- Re-captured from Case (Apex trigger-action framework): 19 METHOD_ENTRY,
  apex_units = {Case_Trigger_Handler, TriggerHandler, CaseObjectTrigger}.

### Parser — intelligence/debuglog/parser.py (pure: text -> events)
- Generic tokenizer + typed extractors; unknown event types captured
  generically (never crash the parse). Lean LogEvent + derived convenience
  fields (code_line, apex_unit, apex_class_id) for core types only.
- Handles header (api + categories), Execute-Anonymous source echo (skipped),
  continuation lines (FATAL_ERROR stack, LIMIT_USAGE block). Verified against
  all three real logs.
- BONUS: METHOD_ENTRY/CONSTRUCTOR carry the ApexClass/Trigger Id (01p/01q) ->
  Day-4 correlation can match on Id, not just name.
- 10 hermetic tests (synthetic fixture, no org PII). Suite 320 -> 330.

### GATE (locked pre-build) — PASS
- Clause 1 (>=1 METHOD_ENTRY/EXCEPTION unit is a graph node): PASS.
- Clause 2 (>=30% distinct apex_units are nodes): 100% (3/3) -> PASS.
- scripts/debuglog_gate_check.py reuses load_graph + graph.all_nodes().
- Real org logs gitignored (PII); committed = parser + synthetic test + script.

### Decision: CONTINUE to Day 4 (analyze_debug_log tool + wiring).

## Week 12 Day 4 — Capability 5 (debug-log): tool + wiring

### ADR-017 — debug-log capability interface ({log reference}, not {question})
- analyze_debug_log(log_path): handler reads file (cwd-independent resolve) ->
  pure parser -> correlate_log_to_graph. Claude gets STRUCTURED prose, never raw
  log (the data-fix-before-prompt principle + cost control).
- Asymmetry recorded: the other 4 take {question}; debuglog takes a log
  reference. Day-5 consequence: its REST route uses DebugLogRequest{log_path,
  question?}, not the shared CapabilityRequest. log_text deferred (hosted-client
  extension), not built.

### correlate.py (intelligence/debuglog/correlate.py)
- Joins parsed apex_units to graph nodes: exception (type/msg/line), units that
  ran + which are graph nodes, and each in-graph unit's direct deps/dependents
  WITH edge labels. Name-first via resolve_one (ADR-013); 15-char Id tie-breaker.
- Verified across branches: in-graph + labelled edges, managed/not-in-graph
  flagged, Flow-only -> "none executed", exception path.

### tool_definitions.py — analyze_debug_log added to the always-built graph
  family (engine+graph, no cache). Catalogue 6->7; no-cache set 5->6 (two test
  assertions updated to match).

### system_prompt.py — build_debuglog_prompt: evidence-bounded, mirrors impact
  discipline. Bakes in the Opportunity-log finding: Flow-only logs -> say the
  failure isn't in the Apex graph, don't manufacture a cause.

### capabilities.py — registry entry "debuglog": (build_debuglog_prompt,
  _GRAPH_ONLY | {analyze_debug_log}). get_source EXCLUDED (Decision 4; flip
  trigger = a Day-5 eval failing specifically for lack of source).

### Tests: test_debuglog_correlate.py (6 — 4 correlation branches + 2 wiring).
  Suite 330 -> 336.

### Day 5: expose debuglog on CLI/MCP/REST + debuglog eval cases (20->25) +
  cross-surface proof. The registry entry already propagates the capability;
  Day 5 wires the 3 transports + the DebugLogRequest REST shape.

## Week 12 Day 5 — debug-log exposed on all 3 surfaces + evals (20 -> 25)

### Cross-surface wiring — one registry entry, three transports
- compose_debuglog_input(log_path, question) in capabilities.py: SINGLE source
  for turning a log reference into the capability message (ADR-017 asymmetry).
  CLI/MCP/REST all route through it — no per-surface framing.
- CLI: ask_cli --log <path>; _ask composes for mode=debuglog (guard fires before
  _load -> missing --log fails fast/free). question stays required.
- MCP: diagnose_debug_log(log_path, question="") -> _run_debuglog ->
  _run_capability("debuglog", ...). Named distinctly from the internal
  analyze_debug_log graph tool (host-facing vs loop-internal don't collide in
  stderr). Tools 5 -> 6.
- REST: POST /api/v1/debug-log-analysis, DebugLogRequest{log_path, question?}
  (distinct from CapabilityRequest as ADR-017 predicted); reuses the
  _capability_response SSE seam. Routes 4 -> 5. No main.py change.

### Unit tests (hermetic): 341 -> 344
- test_ask_cli (+3): --log parse / default None / debuglog-without-log SystemExit.
- test_debuglog_correlate (+2): compose path-only + path+question.
- test_rest_capabilities (+3): debuglog 503 / streams (mode + path in message) /
  422 missing log_path.

### Semantic evals: 20 -> 25
- EvalCase gains a `log` field; eval_runner forwards it to _ask.
- evals/cases/debuglog_cases.py: 5 cases over 2 fixtures.
- evals/fixtures/ (format-valid real SF log STRUCTURE, synthetic PII-free
  ids/data; committed because synthetic, unlike the gitignored real captures):
  debuglog_case_exception.log (Case framework + DmlException, names real graph
  nodes -> grounding path) + debuglog_flow_only.log (Opportunity Flow-only ->
  honesty path; the Day-3 Opportunity-is-Flow-driven finding as an eval).
- Result: __/5 passing, ~$____ run.

- Result: 5/5 passing, ~$0.16 run (per-case $0.022-$0.044, 2-3 turns).

### GOTCHA (future-me): evals/fixtures/*.log was swept by the repo-wide *.log
  ignore -> the Day-5 commit silently dropped both fixtures (git add skips
  ignored paths; the "Use -f" hint + an 11-file commit were the tells). Fix:
  evals/fixtures/.gitignore with `!*.log` (deeper .gitignore overrides root;
  dir isn't excluded so re-inclusion is allowed). Diagnose with
  `git check-ignore -v <path>`. Lesson: never chain a stop-gate check into the
  same command block as the commit it's gating.

### Naming: REST route = /api/v1/debug-log-analysis (noun, like deployment-impact).
  ROADMAP's stale "debug-log-analyze" -> reconcile Day 6.

## Week 12 Day 6 — Regression, ADR-015 migration, Week-12 retro

### Regression baseline: 344 unit tests green. [+ 25 evals if full run.]

### ADR-015 migration (Day-1 buffer item, completed)
- CLI _load and MCP _get_engine now both call bootstrap.load_graph — the
  duplicated tokens/cache/build/empty-check is deleted from both.
- Contracts preserved: CLI translates GraphLoadError -> SystemExit (short-lived
  process); MCP keeps its module-level engine cache around the call (long-lived)
  and catches GraphLoadError -> readable string.
- Side benefit: CLI is now cwd-independent (was Path("data")/..., now
  backend-relative via bootstrap) — works from any directory.
- ADR-015 FULLY adopted: one loader, three consumers (CLI/MCP/REST). The
  3-hand-copied-copies drift risk the ADR was created to kill is gone. Suite
  green post-migration (the backstop held).

### Week-12 retrospective
Shipped:
- REST API (ADR-015/016): bootstrap loader, 4 capability routes + /graph, SSE
  streaming, 503 precondition-gating.
- Debug-log capability (ADR-017): the parked 5th. Pure parser + graph correlator
  + analyze_debug_log tool + debuglog mode, on all 3 transports, 5 evals. Both
  paths proven live (grounded correlation + Flow-only honesty).
- ADR-015 fully adopted (Day 6).

Held (process):
- Data-fix-before-prompt: correlation feeds Claude structured prose, never the
  raw log — no prompt band-aid for cost or over-narration.
- Gate-before-stacking: Day-3 gate passed before the tool was built; each
  surface verified before the next.
- Trigger-gated parking over vague "Phase 2": every deferral has a named trigger.
- Single-source discipline extended: compose_debuglog_input is the one home for
  the log-reference framing across CLI/MCP/REST.

Honest deltas:
- Stale ROADMAP Week-12 lines (API-key, rate-limiting, "5 endpoints") corrected
  in the reconciliation — trigger-deferred, not done.
- Day-5 commit silently dropped the eval fixtures (repo-wide *.log ignore);
  caught + fixed with a scoped .gitignore negation. Lesson: never chain a
  stop-gate check into the commit it gates.

### Week 13 readiness: REST API is the extension's spine; /docs exposes the
  typed routes (incl. DebugLogRequest) the extension generates its client from.

## Week 13 Day 1 — VS Code extension scaffold (first non-Python surface)

Architecture (kickoff, resolved before code):
- MVP surface = metadata-qa, command palette -> input box -> OutputChannel
  streaming. Cheapest renderer that proves the spine; webview + editor-context
  binding deferred to later days THIS week.
- Connection model = assume uvicorn running; readiness probe GET /api/v1/graph
  (200 ready / 503 "metadata graph not loaded" / ECONNREFUSED down). Extension
  does NOT manage the server process (parked: trigger = packaging for non-author
  users, downstream of the multi-user auth trigger).
- Typed client = hand-rolled thin client, NOT OpenAPI codegen. Surface too small
  (2 request models) and SSE responses defeat codegen. Revisit trigger: >~10
  models.
- SSE consumed via fetch streaming, NOT EventSource (routes are POST). Frame
  parser kept pure + unit-tested, mirroring the debuglog parser discipline.
- Renderer seam: SSE/client talk to a Renderer interface (start/appendChunk/
  done/error == chunk/done/error events). OutputChannel renderer Day 3; webview
  renderer Day 4 is then a renderer swap, not a plumbing rewrite. Webview is a
  named deliverable this week for Week-14 README screenshots.
- Stack: vscode-extension/ at repo root (Node module beside backend/);
  esbuild bundle + tsc --noEmit typecheck; hand-scaffolded (not yo code).
  vsce/.vsix packaging deferred to week-end.

Shipped Day 1:
- Scaffold: package.json (1 command: salesforceGraph.ask), tsconfig (strict),
  esbuild.js (external: vscode), src/extension.ts (activate/deactivate),
  .gitignore, .vscode/launch.json.
- npm install + npm run build + npm run typecheck all green; dist/extension.js
  emitted (~2kb). F5 -> Extension Dev Host -> command fires -> info message.
  TS toolchain proven on Windows.
- Windows first-run gotchas cleared: PATH stale after Node install (new shell
  needed); PowerShell execution policy Restricted blocked npm.ps1 (fixed:
  Set-ExecutionPolicy -Scope CurrentUser RemoteSigned); VS Code integrated
  terminal defaulted to cmd not PowerShell (Test-Path/Select-String failed
  there) -> set default profile to PowerShell. F5 was intercepted by a system
  overlay; Run -> Start Debugging is the reliable launch path.
- npm audit flags 1 moderate (esbuild dev-server advisory): ignored by design,
  build-time-only tool, NOT npm audit fix --force.

Next (Day 2): apiBaseUrl setting + readiness-probe command against GET
/api/v1/graph; three-state handling (ready / 503 not-ready / connection-refused).

## Week 13 Day 2 — API connection model + readiness probe

- Setting salesforceGraph.apiBaseUrl (default http://127.0.0.1:8000). 127.0.0.1
  not localhost: dodges Windows IPv6 (::1) resolution stall vs uvicorn's IPv4 bind.
- src/client.ts: hand-rolled thin client, vscode-free (unit-testable later, like
  the pure debuglog parser). fetchGraphSummary() returns a discriminated union
  ProbeResult {ready|not-ready|unreachable|http-error} instead of throwing —
  caller switches on .status, compiler enforces exhaustiveness. AbortController
  5s timeout bounds a hung connection.
- Three-state mapping onto the REST contract: fetch throw -> unreachable;
  503 -> not-ready (the precondition gate, first consumer of 503-not-401);
  200 -> ready (parse GraphSummary, show node/edge counts).
- GraphSummary TS interface mirrors routes/graph.py field-for-field
  (org_key, node_count, edge_count, node_type_counts, edge_type_counts).
- Verified live: unreachable (server off) + ready ("Connected to <org> — 57
  nodes / 172 edges") end to end. [503 path = backend hermetic tests.]
- Build green: dist/extension.js ~4.6kb; tsc --noEmit clean.

ROADMAP reconcile (week-end): stale Week-13 detail (Yeoman, API-key Settings UI,
Day-5 client) superseded by kickoff — hand-scaffold, apiBaseUrl not API key,
client pulled forward. API-key auth still parked (trigger: >1 user).

Next (Day 3): hand-rolled SSE consumer (fetch streaming, NOT EventSource — POST
routes) + pure frame parser (unit-tested) + Renderer seam + OutputChannel
renderer -> first streaming capability (metadata-qa) end to end.

## Week 13 Day 3 — SSE streaming + Renderer seam + first live capability

- src/sse.ts: PURE incremental SSE frame parser (no fetch/vscode), unit-tested
  with vitest (8 cases). Handles spec edge cases: multi-data-line values rejoined
  with \n, frames split across byte-chunk boundaries (buffered), CRLF normalized,
  ": ping" heartbeat comments ignored. The pure-parser-with-tests discipline,
  ported from the backend debuglog parser to TS.
- src/renderer.ts: Renderer seam (note-1). Interface start/appendChunk/done/error
  maps 1:1 onto the SSE lifecycle. OutputChannelRenderer implements it now;
  Day-4 webview implements the SAME interface -> renderer swap, not a rewrite
  (dependency inversion). client.ts depends on the interface (type-only import),
  never the concrete UI.
- src/client.ts: streamCapability() — POST + fetch streaming body reader (NOT
  EventSource: routes are POST, host is Node not a browser). Feeds bytes ->
  SSEParser -> dispatch to renderer (chunk/done/error; unknown events ignored).
  Optional AbortSignal -> cancellation -> backend disconnect-cancel (cost control).
  Stays runtime vscode-free (verified: 0 vscode imports).
- src/extension.ts: salesforceGraph.ask now does input box -> renderer.start ->
  stream into "Salesforce Graph" OutputChannel, in a cancellable progress notif.
- Testing: vitest added (npm test = vitest run). First automated tests on the
  TS surface. 8/8 green.
- Build green: dist/extension.js ~9.2kb; tsc --noEmit clean.
- Verified live: metadata-qa streams token-by-token from Claude into the editor;
  uvicorn logs POST /api/v1/metadata-qa 200. Spine fully alive end to end.

Next (Day 4): webview renderer implementing the SAME Renderer interface (the
swap note-1 set up) -> a real panel for Week-14 README screenshots.

## Week 13 Day 4 — Webview renderer (the Renderer seam pays off)

- WebviewRenderer (src/renderer.ts) implements the SAME Renderer interface as
  OutputChannelRenderer — client.ts/sse.ts/sse.test.ts UNTOUCHED. Proof of
  note-1: a whole new rendering surface = zero plumbing changes (dependency
  inversion validated).
- Webview hazards handled: strict CSP + per-load nonce; load-race ready-handshake
  (buffer outbound messages until webview posts {type:"ready"}, then flush) so
  first tokens are never dropped on a cold panel.
- src/webview/main.ts: browser-context client script, bundled with marked to
  dist/webview.js. Re-renders full markdown buffer per chunk -> formatted tables/
  code blocks; themed with --vscode-* CSS vars to match the user's theme.
- Two-bundle esbuild (extension cjs/node + webview iife/browser). Split tsconfigs:
  tsconfig.json (node, excludes src/webview) + tsconfig.webview.json (adds DOM
  lib, only src/webview). typecheck runs both -> fetch/Response stay node-typed,
  webview gets DOM. npm test still 8/8.
- salesforceGraph.renderer setting (webview|output, default webview): same SSE
  stream routes to either renderer at runtime — the seam made switchable.
- Verified live: metadata-qa renders as formatted Markdown in a themed panel
  beside the editor; renderer setting toggles surface with no plumbing change.
  README screenshot captured.

Next (Day 5): broaden capabilities in-editor (apex/impact/debuglog with editor-
context binding: explain current Apex file, impact on selection, analyze open
.log) — each is the same client + same renderer + a different route/input.
---