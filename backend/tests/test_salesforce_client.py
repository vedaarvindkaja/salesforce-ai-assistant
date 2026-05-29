"""Tests for SalesforceClient — the refresh-on-401 logic.

Uses httpx.MockTransport to fake Salesforce responses without making real
network calls. Each test scenario sets up a handler that decides what to
return for each request type, then asserts the client's behavior.

These tests are complementary to test_endpoints.py:
- test_endpoints.py tests the FastAPI HTTP contract using the mock client
- test_salesforce_client.py tests the real client's auth lifecycle in isolation
"""

import pytest
import httpx

from app.salesforce.oauth_models import StoredTokens
from app.salesforce.rest_api import SalesforceClient
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
# Helper: build a SalesforceClient wired to a MockTransport
# ============================================================

def _build_client_with_handler(handler) -> SalesforceClient:
    """Construct a SalesforceClient whose HTTP layer is faked by `handler`.
    
    Manually bypasses __aenter__ — we inject the mocked httpx client directly.
    Also pre-loads tokens (skipping authenticate() which reads from disk).
    """
    client = SalesforceClient()
    client._http = httpx.AsyncClient(transport=httpx.MockTransport(handler), timeout=5.0)
    client._tokens = EXPIRED_TOKENS
    return client


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
# Tests
# ============================================================

@pytest.mark.asyncio
async def test_query_happy_path():
    """If Salesforce returns 200 on the first try, no refresh fires."""
    calls: list[str] = []
    
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if "/query" in request.url.path:
            return httpx.Response(200, json=VALID_QUERY_RESPONSE)
        raise AssertionError(f"Unexpected request: {request.url}")
    
    client = _build_client_with_handler(handler)
    result = await client.query("SELECT Id FROM Account")
    
    # One call, to /query — no refresh fired
    assert len(calls) == 1
    assert "/services/data/v60.0/query" in calls[0]
    assert result.totalSize == 1
    assert result.records[0].Name == "Test Account"
    
    await client._http.aclose()


@pytest.mark.asyncio
async def test_query_refreshes_on_401_and_retries():
    """If first /query returns 401, client refreshes and retries — caller sees success."""
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
    
    client = _build_client_with_handler(handler)
    result = await client.query("SELECT Id FROM Account")
    
    # Exactly: query → refresh → query (3 HTTP calls in total)
    assert query_call_count == 2
    assert refresh_call_count == 1
    assert result.totalSize == 1
    
    # Client now holds the NEW access token
    assert client._tokens.access_token == "00DdM00000I-newtoken"
    
    await client._http.aclose()


@pytest.mark.asyncio
async def test_refresh_persists_new_tokens_to_disk():
    """After a successful refresh, the new tokens should be in tokens.json."""
    def handler(request: httpx.Request) -> httpx.Response:
        if "/services/oauth2/token" in request.url.path:
            return httpx.Response(200, json=VALID_TOKEN_RESPONSE)
        if "/services/data/v60.0/query" in request.url.path:
            return httpx.Response(401, json={"error": "expired"}) \
                if not _has_refreshed(request) else httpx.Response(200, json=VALID_QUERY_RESPONSE)
        raise AssertionError(request.url)
    
    # We need to track refresh state across calls — use a closure-friendly flag
    refreshed = {"yes": False}
    
    def handler2(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if "/services/oauth2/token" in path:
            refreshed["yes"] = True
            return httpx.Response(200, json=VALID_TOKEN_RESPONSE)
        if "/services/data/v60.0/query" in path:
            if not refreshed["yes"]:
                return httpx.Response(401, json={"error": "expired"})
            return httpx.Response(200, json=VALID_QUERY_RESPONSE)
        raise AssertionError(request.url)
    
    client = _build_client_with_handler(handler2)
    await client.query("SELECT Id FROM Account")
    
    # Tokens were saved to (mocked) disk
    saved = token_storage.load_tokens()
    assert saved is not None
    assert saved.access_token == "00DdM00000I-newtoken"
    assert saved.refresh_token == "5Aep861-newrefresh"  # RTR rotated it
    
    await client._http.aclose()


@pytest.mark.asyncio
async def test_query_raises_when_refresh_also_fails():
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
    
    client = _build_client_with_handler(handler)
    
    with pytest.raises(RuntimeError, match="Salesforce OAuth error"):
        await client.query("SELECT Id FROM Account")
    
    await client._http.aclose()


@pytest.mark.asyncio
async def test_query_propagates_non_401_errors():
    """500 errors should NOT trigger a refresh — they're not auth problems."""
    refresh_attempted = {"yes": False}
    
    def handler(request: httpx.Request) -> httpx.Response:
        if "/services/oauth2/token" in request.url.path:
            refresh_attempted["yes"] = True
            return httpx.Response(200, json=VALID_TOKEN_RESPONSE)
        if "/services/data/v60.0/query" in request.url.path:
            return httpx.Response(500, json={"error": "server error"})
        raise AssertionError(request.url)
    
    client = _build_client_with_handler(handler)
    
    with pytest.raises(httpx.HTTPStatusError):
        await client.query("SELECT Id FROM Account")
    
    # 500 != 401, so we should NOT have tried to refresh
    assert refresh_attempted["yes"] is False
    
    await client._http.aclose()