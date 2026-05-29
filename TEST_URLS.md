# Test URLs for Salesforce Assistant API

A reference list of URLs to test all endpoints. Open each URL in your browser,
or use `Invoke-RestMethod` from PowerShell, to verify the API works as expected.

## How to use

### Recommended: run the automated test suite

Before testing manually, run the automated tests:

    cd backend
    pytest tests/ -v

This runs all 19 tests in ~12 seconds and confirms every endpoint works correctly.
Tests are hermetic — they force `USE_MOCK_DATA=true` via `monkeypatch.setenv`,
so they don't depend on your `.env` state.

Manual URL testing below is useful for exploring behavior interactively.

### Start the server

```powershell
cd backend
uvicorn app.main:app --reload
```

Wait for `Application startup complete.` Then check the startup log line —
it tells you which client is running:

- `Starting MOCK Salesforce client (USE_MOCK_DATA=true)...` → mock data
- `Starting REAL Salesforce client (USE_MOCK_DATA=false)...` → your real org

### Two ways to call URLs

| Method | Best for |
|---|---|
| Open in browser | GET endpoints with simple visual JSON |
| `Invoke-RestMethod <url>` in PowerShell | Returns parsed objects; better for scripting |
| Open `/docs` in browser | Interactive UI for POST/complex requests |

---

## Mode reference

These test URLs behave **differently** depending on `USE_MOCK_DATA`:

- **Mock mode** (`USE_MOCK_DATA=true`) — returns 3 fixed accounts:
  Edge Communications, Burlington Textiles Corp, GenePoint
- **Real mode** (`USE_MOCK_DATA=false`) — returns whatever's in your dev org
  (typically 10 sample accounts: Pyramid Construction, Dickenson plc, etc.)

URLs that should behave identically in both modes are marked **[mode-agnostic]**.

---

## 🟢 Tests that should SUCCEED

### Test 1 — Health check [mode-agnostic]

URL: http://localhost:8000/health

Expected: `{"status":"ok","message":"Salesforce AI Assistant is alive"}`

---

### Test 2 — Auto-generated docs [mode-agnostic]

URL: http://localhost:8000/docs

Expected: Interactive Swagger UI showing all endpoint groups:
- `accounts` (4 endpoints)
- `auth` (3 endpoints)
- default (`/health`)

---

### Test 3 — Raw OpenAPI spec [mode-agnostic]

URL: http://localhost:8000/openapi.json

Expected: Large JSON showing all paths and schemas. Useful for debugging
"is this endpoint actually registered."

---

## 🔐 Authentication endpoints (REAL mode only)

These are skipped/no-op in mock mode. Set `USE_MOCK_DATA=false` first.

### Test 4 — Auth status (no tokens yet)

URL: http://localhost:8000/auth/status

Expected (if tokens.json doesn't exist):
```json
{"authenticated": false, "message": "No tokens stored. Visit /auth/login."}
```

Expected (if tokens are present):
```json
{"authenticated": true, "instance_url": "https://...", "issued_at": "2026-..."}
```

---

### Test 5 — Login flow

URL: http://localhost:8000/auth/login

Expected behavior:
1. Browser shows brief localhost URL → redirects to Salesforce
2. Salesforce login page (if not already logged in)
3. "Allow Access?" page showing scopes (`api`, `refresh_token`, `id`)
4. Click Allow
5. Browser lands on `http://localhost:8000/auth/callback?code=...&state=...`
6. Response JSON:
```json
   {
     "status": "authenticated",
     "instance_url": "https://yourorg.my.salesforce.com",
     "scope": "id api refresh_token",
     "message": "Authentication successful. You can now use the API."
   }
```
7. `backend/tokens.json` now exists with access_token + refresh_token

---

### Test 6 — Callback URL (manual invalid call) [mode-agnostic]

URL: http://localhost:8000/auth/callback

Expected: 400 error — missing code/state parameters.
This is expected behavior; the callback URL is only meaningful when
called by Salesforce with `?code=...&state=...`.

---

## 📋 Account endpoints

### Test 7 — List accounts (default limit)

URL: http://localhost:8000/accounts/

Expected (mock): JSON array of 3 accounts —
Edge Communications, Burlington Textiles Corp, GenePoint

Expected (real): JSON array of accounts from your dev org —
typically Pyramid Construction, Dickenson plc, etc.

---

### Test 8 — List accounts with limit

URL: http://localhost:8000/accounts/?limit=5

Expected (mock): Same 3 accounts (mock ignores limit and returns fixed data)

Expected (real): Up to 5 accounts from your org

---

### Test 9 — Get specific account by ID

**Mock mode IDs:** `0015g00000Abc1AAB`, `0015g00000Def2BBC`, `0015g00000Ghi3CCD`

URL: http://localhost:8000/accounts/0015g00000Abc1AAB

Expected (mock): Edge Communications JSON

Expected (real): 404 — that ID doesn't exist in your real org.
Use a real ID from `/accounts/` first to test this in real mode.

---

### Test 10 — Search with no filters

URL: http://localhost:8000/accounts/search/

Expected: All accounts (mock: 3, real: as many as your org has)

---

### Test 11 — Search by industry: Electronics

URL: http://localhost:8000/accounts/search/?industry=Electronics

Expected (mock): 1 account — Edge Communications

Expected (real): Whatever accounts in your org have Industry=Electronics
(probably empty for fresh dev orgs)

---

### Test 12 — Search by industry that doesn't match

URL: http://localhost:8000/accounts/search/?industry=NonExistent

Expected: Empty array `[]`

---

### Test 13 — Search by minimum revenue

URL: http://localhost:8000/accounts/search/?min_revenue=200000000

Expected (mock): 1 account — Burlington Textiles (350M revenue)

Expected (real): Accounts in your org with AnnualRevenue >= 200M

---

### Test 14 — Search combining filters

URL: http://localhost:8000/accounts/search/?industry=Electronics&min_revenue=100000000

Expected (mock): 1 account — Edge Communications (Electronics + 139M revenue)

---

### Test 15 — Batch queries (POST endpoint, test via /docs)

URL: http://localhost:8000/docs

How to test:
1. Find POST /accounts/batch in the docs
2. Click "Try it out"
3. Use this request body:

       {
         "queries": [
           "SELECT Id, Name FROM Account LIMIT 3",
           "SELECT Id, Name FROM Account WHERE Industry = 'Electronics'",
           "SELECT Id, Name FROM Account WHERE AnnualRevenue > 100000000"
         ]
       }

4. Click "Execute"

Expected: Response with `total_queries: 3`, results array with 3 inner arrays.

Notice the response time:
- Mock mode: ~0.8 seconds (proves async concurrency works — 3 queries in 1's time)
- Real mode: 0.5-1.5 seconds depending on network

---

## 🔴 Tests that should FAIL with proper error messages

These prove validation and error handling work correctly.

### Test 16 — Account not found (HTTP 404)

URL: http://localhost:8000/accounts/INVALID_ID

Expected: `{"detail":"Account not found: INVALID_ID"}` with status 404

---

### Test 17 — Validation: limit too low (HTTP 422)

URL: http://localhost:8000/accounts/?limit=0

Expected: 422 validation error — "Input should be greater than or equal to 1"

---

### Test 18 — Validation: limit too high (HTTP 422)

URL: http://localhost:8000/accounts/?limit=999

Expected: 422 validation error — "Input should be less than or equal to 100"

---

### Test 19 — Validation: limit not a number (HTTP 422)

URL: http://localhost:8000/accounts/?limit=abc

Expected: 422 validation error — "Input should be a valid integer"

---

### Test 20 — Validation: negative revenue (HTTP 422)

URL: http://localhost:8000/accounts/search/?min_revenue=-100

Expected: 422 validation error — "Input should be greater than or equal to 0"

---

### Test 21 — Unknown route (HTTP 404)

URL: http://localhost:8000/this-route-does-not-exist

Expected: `{"detail":"Not Found"}` with status 404

---

## ⚡ Quick smoke tests

### Mock mode smoke test (4 URLs)

If `USE_MOCK_DATA=true`, hit these in order:
1. http://localhost:8000/health
2. http://localhost:8000/docs
3. http://localhost:8000/accounts/
4. http://localhost:8000/accounts/INVALID_ID

If all 4 behave as expected (status 200, 200, 3 accounts, 404), mock plumbing
is working.

### Real mode smoke test (5 URLs)

If `USE_MOCK_DATA=false`, also verify auth works:
1. http://localhost:8000/health
2. http://localhost:8000/auth/status (expect "authenticated: false" initially)
3. http://localhost:8000/auth/login (run through OAuth flow)
4. http://localhost:8000/auth/status (expect "authenticated: true")
5. http://localhost:8000/accounts/ (expect real org accounts, NOT Edge/Burlington/GenePoint)

If all 5 work, real plumbing including refresh-on-401 is wired up correctly.

---

## Testing refresh-on-401 manually

The most interesting OAuth behavior to verify by hand:

1. Authenticate via `/auth/login` to get fresh tokens
2. Wait 2-3 hours (or come back the next day) so the access_token expires
3. Hit any `/accounts/*` endpoint
4. The first request takes ~1 second longer than usual
5. Check `/auth/status` — `issued_at` is now a fresh timestamp

The slow first request is the refresh dance:
- 401 from Salesforce → refresh_token POST → new tokens saved → original query retried

If you don't want to wait, you can also expire the token manually by editing
`tokens.json` to set `access_token` to a garbage string. The 401 + refresh
+ retry should fire on the next request.

---

## How to check the HTTP status code

### In PowerShell

```powershell
$response = Invoke-WebRequest http://localhost:8000/accounts/ -UseBasicParsing
$response.StatusCode    # Just the number
$response.Content       # The JSON body as text
```

### In Chrome/Edge

1. F12 → Network tab
2. Refresh the page
3. Click the request → "Status" column

---

## Sample data reference

### Mock client always returns these 3 accounts:

| Account Name | ID | Industry | Revenue |
|---|---|---|---|
| Edge Communications | 0015g00000Abc1AAB | Electronics | 139,000,000 |
| Burlington Textiles Corp | 0015g00000Def2BBC | Apparel | 350,000,000 |
| GenePoint | 0015g00000Ghi3CCD | null | null |

### Real dev orgs typically ship with these sample accounts:

- Edge Communications
- Burlington Textiles Corp of America
- Pyramid Construction Inc.
- Dickenson plc
- Grand Hotels & Resorts Ltd
- United Oil & Gas Corp.
- Express Logistics and Transport
- University of Arizona
- United Oil & Gas, UK
- United Oil & Gas, Singapore

(IDs in real orgs use the format `001dM00002...`, not the mock's
`0015g00000...` format — useful for telling at a glance which mode you're in.)

---

## URL pattern reference

| Pattern | Format | Example |
|---|---|---|
| Simple endpoint | http://localhost:8000/PATH | /health |
| Query param | http://localhost:8000/PATH?param=value | /accounts/?limit=5 |
| Path param | http://localhost:8000/PATH/VALUE | /accounts/abc123 |
| Multiple params | http://localhost:8000/PATH?a=1&b=2 | /accounts/search/?industry=Tech&min_revenue=1000 |

Key separators:
- `?` introduces query parameters
- `&` separates multiple query parameters
- `/` separates path segments

---

## To be updated

This file will be updated as new endpoints are added in upcoming weeks:
- Week 5: Metadata API endpoints (`/metadata/objects`, etc.)
- Week 6: Graph query endpoints
- Week 8: `/chat` endpoint for Claude API
- Week 11: MCP server tools (different protocol, not URLs)