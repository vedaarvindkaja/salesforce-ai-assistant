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
---