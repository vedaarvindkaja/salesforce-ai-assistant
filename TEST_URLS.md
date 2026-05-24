# Test URLs for Salesforce Assistant API

A reference list of URLs to test all endpoints. Open each URL in your browser
to verify the API works as expected.

## How to use

1. Start the server in your backend terminal:

       cd backend
       uvicorn app.main:app --reload

2. Wait for "Application startup complete." in the terminal
3. Open each URL below in your browser
4. Compare what you see to the "Expected" description

---

## 🟢 Tests that should SUCCEED

### Test 1 — Health check

URL: http://localhost:8000/health

Expected: JSON `{"status":"ok","message":"Salesforce AI Assistant is alive"}`

---

### Test 2 — Auto-generated docs (interactive Swagger UI)

URL: http://localhost:8000/docs

Expected: Interactive page with all endpoints listed:
- GET /accounts/
- GET /accounts/search/
- GET /accounts/{account_id}
- GET /health

---

### Test 3 — Alternative docs (read-only style)

URL: http://localhost:8000/redoc

Expected: Same endpoints, different layout (more documentation-style)

---

### Test 4 — Raw OpenAPI spec (debugging aid)

URL: http://localhost:8000/openapi.json

Expected: Large JSON document showing all paths and schemas.
Useful for troubleshooting which endpoints FastAPI knows about.

---

### Test 5 — List accounts (default limit)

URL: http://localhost:8000/accounts/

Expected: JSON array of 3 accounts:
- Edge Communications
- Burlington Textiles Corp
- GenePoint

---

### Test 6 — List accounts with limit parameter

URL: http://localhost:8000/accounts/?limit=5

Expected: Same 3 accounts.
Mock always returns 3 regardless of limit, but the parameter is accepted.

---

### Test 7 — Get specific account by ID (Edge)

URL: http://localhost:8000/accounts/0015g00000Abc1AAB

Expected: Single account JSON — Edge Communications

---

### Test 8 — Get specific account by ID (Burlington)

URL: http://localhost:8000/accounts/0015g00000Def2BBC

Expected: Single account JSON — Burlington Textiles Corp

---

### Test 9 — Get specific account by ID (GenePoint)

URL: http://localhost:8000/accounts/0015g00000Ghi3CCD

Expected: Single account JSON — GenePoint

---

### Test 10 — Search with no filters

URL: http://localhost:8000/accounts/search/

Expected: All 3 accounts (no filter applied)

---

### Test 11 — Search by industry: Electronics

URL: http://localhost:8000/accounts/search/?industry=Electronics

Expected: 1 account — Edge Communications only

---

### Test 12 — Search by industry: Apparel

URL: http://localhost:8000/accounts/search/?industry=Apparel

Expected: 1 account — Burlington Textiles only

---

### Test 13 — Search by industry that doesn't match

URL: http://localhost:8000/accounts/search/?industry=Healthcare

Expected: Empty array []

---

### Test 14 — Search by minimum revenue

URL: http://localhost:8000/accounts/search/?min_revenue=200000000

Expected: 1 account — Burlington Textiles (350M revenue, only one above 200M)

---

### Test 15 — Search combining filters

URL: http://localhost:8000/accounts/search/?industry=Electronics&min_revenue=100000000

Expected: 1 account — Edge Communications (Electronics AND 139M >= 100M)

---

### Test 16 — Search with filters matching nothing

URL: http://localhost:8000/accounts/search/?industry=Electronics&min_revenue=500000000

Expected: Empty array [] (Edge has 139M, doesn't meet 500M threshold)

---

---

### Test 16b — Batch queries (POST endpoint, test via /docs)

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

Expected: Response with total_queries=3, total_records=9, results array with 3 inner arrays.
Notice: response takes ~0.8 seconds (not 2.4s) — proves async concurrency works.

## 🔴 Tests that should FAIL with proper error messages

These are NOT bugs — they prove your validation and error handling work correctly.

### Test 17 — Account not found (HTTP 404)

URL: http://localhost:8000/accounts/INVALID_ID

Expected: {"detail":"Account not found: INVALID_ID"} with status 404

---

### Test 18 — Validation: limit too low (HTTP 422)

URL: http://localhost:8000/accounts/?limit=0

Expected: Validation error — "Input should be greater than or equal to 1"

---

### Test 19 — Validation: limit too high (HTTP 422)

URL: http://localhost:8000/accounts/?limit=999

Expected: Validation error — "Input should be less than or equal to 100"

---

### Test 20 — Validation: limit not a number (HTTP 422)

URL: http://localhost:8000/accounts/?limit=abc

Expected: Validation error — "Input should be a valid integer"

---

### Test 21 — Validation: negative revenue (HTTP 422)

URL: http://localhost:8000/accounts/search/?min_revenue=-100

Expected: Validation error — "Input should be greater than or equal to 0"

---

### Test 22 — URL doesn't exist (HTTP 404)

URL: http://localhost:8000/this-route-does-not-exist

Expected: {"detail":"Not Found"} with status 404

---

## ⚡ Quick smoke test

If you just want to spot-check that things work, run these 4 URLs in order.
They cover the main code paths:

1. http://localhost:8000/health
2. http://localhost:8000/docs
3. http://localhost:8000/accounts/
4. http://localhost:8000/accounts/INVALID_ID

If all 4 behave as expected, your API is working correctly.

---

## How to check the HTTP status code in Chrome/Edge

1. Press F12 to open DevTools
2. Click the Network tab
3. Refresh the page
4. Click the request in the list
5. Look at the "Status" column or the "Headers" tab

Or just read the JSON response:
- `{"detail": "..."}` typically means error
- An array `[...]` or object with data means success

---

## URL pattern reference (for building your own test URLs)

| Pattern | Format | Example |
|---|---|---|
| Simple endpoint | http://localhost:8000/PATH | /chat |
| Query param | http://localhost:8000/PATH?param=value | /chat?stream=true |
| Path param | http://localhost:8000/PATH/VALUE | /accounts/abc123 |
| Multiple params | http://localhost:8000/PATH?a=1&b=2 | /accounts/search/?industry=Tech&min_revenue=1000 |

Key separators:
- `?` introduces query parameters
- `&` separates multiple query parameters
- `/` separates path segments

---

## Sample Salesforce IDs in mock data

These are the only 3 IDs that will return data. Any other ID returns 404.

| Account Name | ID | Industry | Revenue |
|---|---|---|---|
| Edge Communications | 0015g00000Abc1AAB | Electronics | 139,000,000 |
| Burlington Textiles Corp | 0015g00000Def2BBC | Apparel | 350,000,000 |
| GenePoint | 0015g00000Ghi3CCD | null | null |

---

## To be updated

This file will be updated as new endpoints are added in upcoming weeks:
- Week 4: Real Salesforce auth (same URLs, real data)
- Week 5: /chat endpoint for Claude API
- Week 6: Tool use — Claude queries Salesforce
- Week 7: Cache endpoints
- Week 8+: Frontend usage