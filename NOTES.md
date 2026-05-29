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

---