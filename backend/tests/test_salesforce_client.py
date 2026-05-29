"""Tests for SalesforceHTTPClient — the refresh-on-401 lifecycle.

After the Week 5 Day 1 layered-HTTP-client refactor (ADR-003), refresh
behavior lives in SalesforceHTTPClient, not in the REST or Tooling API
clients. These tests target that layer directly using httpx.MockTransport
to fake Salesforce responses.

Tests for RestAPIClient itself live elsewhere (test_endpoints.py exercises
it via the FastAPI HTTP contract, using the mock client). If REST-specific
behavior grows (e.g., REST-only error parsing), add unit tests in a
test_rest_api.py file.
"""

import pytest
import httpx

from app.salesforce.oauth_models import StoredTokens
from app.salesforce.http_client import SalesforceHTTPClient
from app.salesforce import token_storage


# ============================================================
# Fixtures: realistic Salesforce responses
# ============================================================

VALID_QUERY_RESPONSE = {
    "totalSize": 1,
    "done": True,
    "records": [
        {
            "attributes": {
                "type": "Account",
                "url": "/services/data/v60.0/sobjects/Account/001dM00002Test",
            },
            "Id": "001dM00002Test",
            "Name": "Test Account",
        }
    ],
}

VALID_TOKEN_RESPONSE = {
    "access_token": "00DdM00000I-newtoken",
    "refresh_token": "5Aep861-newrefresh",
    "instance_url": "https://test.my.salesforce.com",
    "id": "https://login.salesforce.com/id/00D/005",
    "token_type": "Bearer",
    "issued_at": "1759104000000",
    "signature": "fakeSig=",
    "scope": "id api refresh_token",
}

EXPIRED_TOKENS = StoredTokens(
    access_token="OLD_ACCESS_TOKEN",
    refresh_token="OLD_REFRESH_TOKEN",
    instance_url="https://test.my.salesforce.com",
)


# ============================================================
# Helper: build a SalesforceHTTPClient wired to a MockTransport
# ============================================================

def _build_http_with_handler(handler) -> SalesforceHTTPClient:
    """Construct a SalesforceHTTPClient whose HTTP layer is faked by `handler`.

    Manually bypasses __aenter__ — we inject the mocked httpx client directly.
    Also pre-loads tokens (skipping authenticate() which reads from disk).
    """
    http = SalesforceHTTPClient()
    http._http = httpx.AsyncClient(transport=httpx.MockTransport(handler), timeout=5.0)
    http._tokens = EXPIRED_TOKENS
    return http


# ============================================================
# Patch token_storage so tests don't touch the real tokens.json
# ============================================================

@pytest.fixture(autouse=True)
def isolate_token_storage(monkeypatch, tmp_path):
    """Redirect token_storage's file path to a temp dir for every test.

    autouse=True means this fixture runs for every test in this module
    without each test having to request it.
    """
    fake_path = tmp_path / "tokens.json"
    monkeypatch.setattr(token_storage, "_TOKEN_FILE", fake_path)


# ============================================================
# Tests — refresh-on-401 lifecycle at the HTTP client level
# ============================================================

@pytest.mark.asyncio
async def test_request_happy_path():
    """If Salesforce returns 200 on the first try, no refresh fires."""
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if "/query" in request.url.path:
            return httpx.Response(200, json=VALID_QUERY_RESPONSE)
        raise AssertionError(f"Unexpected request: {request.url}")

    http = _build_http_with_handler(handler)
    response = await http.request(
        "GET", "/services/data/v60.0/query", params={"q": "SELECT Id FROM Account"}
    )

    # One call, to /query — no refresh fired
    assert len(calls) == 1
    assert "/services/data/v60.0/query" in calls[0]
    assert response.status_code == 200

    await http._http.aclose()


@pytest.mark.asyncio
async def test_request_refreshes_on_401_and_retries():
    """If first request returns 401, client refreshes and retries — caller sees success."""
    query_call_count = 0
    refresh_call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal query_call_count, refresh_call_count
        path = request.url.path

        if "/services/oauth2/token" in path:
            refresh_call_count += 1
            return httpx.Response(200, json=VALID_TOKEN_RESPONSE)

        if "/services/data/v60.0/query" in path:
            query_call_count += 1
            # First call = 401 (token expired), second call = 200 (refreshed)
            if query_call_count == 1:
                return httpx.Response(401, json={"error": "INVALID_SESSION_ID"})
            return httpx.Response(200, json=VALID_QUERY_RESPONSE)

        raise AssertionError(f"Unexpected request: {request.url}")

    http = _build_http_with_handler(handler)
    response = await http.request(
        "GET", "/services/data/v60.0/query", params={"q": "SELECT Id FROM Account"}
    )

    # Exactly: query → refresh → query (3 HTTP calls in total)
    assert query_call_count == 2
    assert refresh_call_count == 1
    assert response.status_code == 200

    # Client now holds the NEW access token
    assert http._tokens.access_token == "00DdM00000I-newtoken"

    await http._http.aclose()


@pytest.mark.asyncio
async def test_refresh_persists_new_tokens_to_disk():
    """After a successful refresh, the new tokens should be in tokens.json."""
    refreshed = {"yes": False}

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if "/services/oauth2/token" in path:
            refreshed["yes"] = True
            return httpx.Response(200, json=VALID_TOKEN_RESPONSE)
        if "/services/data/v60.0/query" in path:
            if not refreshed["yes"]:
                return httpx.Response(401, json={"error": "expired"})
            return httpx.Response(200, json=VALID_QUERY_RESPONSE)
        raise AssertionError(request.url)

    http = _build_http_with_handler(handler)
    await http.request(
        "GET", "/services/data/v60.0/query", params={"q": "SELECT Id FROM Account"}
    )

    # Tokens were saved to (mocked) disk
    saved = token_storage.load_tokens()
    assert saved is not None
    assert saved.access_token == "00DdM00000I-newtoken"
    assert saved.refresh_token == "5Aep861-newrefresh"  # RTR rotated it

    await http._http.aclose()


@pytest.mark.asyncio
async def test_request_raises_when_refresh_also_fails():
    """If the refresh itself fails, the original error surfaces cleanly."""
    def handler(request: httpx.Request) -> httpx.Response:
        if "/services/oauth2/token" in request.url.path:
            return httpx.Response(400, json={
                "error": "invalid_grant",
                "error_description": "expired refresh token",
            })
        if "/services/data/v60.0/query" in request.url.path:
            return httpx.Response(401, json={"error": "expired"})
        raise AssertionError(request.url)

    http = _build_http_with_handler(handler)

    with pytest.raises(RuntimeError, match="Salesforce OAuth error"):
        await http.request(
            "GET", "/services/data/v60.0/query", params={"q": "SELECT Id FROM Account"}
        )

    await http._http.aclose()


@pytest.mark.asyncio
async def test_request_propagates_non_401_errors():
    """500 errors should NOT trigger a refresh — they're not auth problems."""
    refresh_attempted = {"yes": False}

    def handler(request: httpx.Request) -> httpx.Response:
        if "/services/oauth2/token" in request.url.path:
            refresh_attempted["yes"] = True
            return httpx.Response(200, json=VALID_TOKEN_RESPONSE)
        if "/services/data/v60.0/query" in request.url.path:
            return httpx.Response(500, json={"error": "server error"})
        raise AssertionError(request.url)

    http = _build_http_with_handler(handler)

    # 500 is returned to caller, NOT raised — caller decides via raise_for_status
    response = await http.request(
        "GET", "/services/data/v60.0/query", params={"q": "SELECT Id FROM Account"}
    )
    assert response.status_code == 500

    # 500 != 401, so we should NOT have tried to refresh
    assert refresh_attempted["yes"] is False

    await http._http.aclose()