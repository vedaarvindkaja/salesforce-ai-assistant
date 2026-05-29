"""Salesforce REST API client using OAuth 2.0 tokens.

This client:
- Loads OAuth tokens from token_storage (populated by /auth/login flow)
- Makes authenticated REST calls with Bearer headers
- Transparently refreshes on 401 (token expired) and retries the request
- Persists rotated refresh_tokens back to disk

Has the same async interface as MockSalesforceClient — drop-in replacement.

Built Day 4 of Week 4, replacing the Week 2 username-password code.
"""

import asyncio
import urllib.parse
from datetime import datetime, timezone
from typing import Optional

import httpx

from app.models.salesforce import SalesforceQueryResponse
from app.salesforce import auth as oauth
from app.salesforce.oauth_models import StoredTokens
from app.salesforce.token_storage import load_tokens, save_tokens


class SalesforceClient:
    """An async, typed Salesforce REST API client backed by OAuth tokens.

    Usage:
        async with SalesforceClient() as client:
            await client.authenticate()
            result = await client.query("SELECT Id, Name FROM Account LIMIT 5")

    Drop-in replacement for MockSalesforceClient — same method signatures.
    """

    def __init__(self):
        self._tokens: Optional[StoredTokens] = None
        self._http: Optional[httpx.AsyncClient] = None

    # ----- async context manager (same shape as MockSalesforceClient) -----

    async def __aenter__(self):
        """Open HTTP client when entering 'async with' block."""
        self._http = httpx.AsyncClient(timeout=30.0)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Close HTTP client when exiting 'async with' block."""
        if self._http is not None:
            await self._http.aclose()
            self._http = None

    # ----- authentication -----

    async def authenticate(self) -> None:
        """Load tokens from storage. If none exist, raise a clear error.

        Does not perform a network call. The first actual API request will
        validate the token; if Salesforce rejects it, we'll refresh then.
        """
        tokens = load_tokens()
        if tokens is None:
            raise RuntimeError(
                "No OAuth tokens found. Visit http://localhost:8000/auth/login "
                "to authenticate, then restart the server."
            )
        self._tokens = tokens

    # ----- public API -----

    async def query(self, soql: str) -> SalesforceQueryResponse:
        """Run a SOQL query — returns typed Pydantic response.

        Transparently refreshes the access_token if Salesforce returns 401.
        Retries the original request once after a successful refresh.
        """
        if self._tokens is None:
            raise RuntimeError("Not authenticated. Call authenticate() first.")

        response = await self._do_query(soql)

        if response.status_code == 401:
            # Token expired or invalidated — refresh and try once more
            await self._refresh_tokens()
            response = await self._do_query(soql)

        response.raise_for_status()
        return SalesforceQueryResponse.model_validate_json(response.text)

    async def query_all(self, *soqls: str) -> list[SalesforceQueryResponse]:
        """Run multiple SOQL queries concurrently.

        Note: if multiple queries simultaneously trigger a refresh, the
        refreshes may race. For Phase 1 single-user this is acceptable
        (worst case: a few extra refresh calls); Phase 2 needs a lock.
        """
        if self._tokens is None:
            raise RuntimeError("Not authenticated.")
        return await asyncio.gather(*[self.query(s) for s in soqls])

    # ----- internals -----

    async def _do_query(self, soql: str) -> httpx.Response:
        """Make a single SOQL HTTP call. Returns the raw response (no parsing)."""
        if self._http is None:
            raise RuntimeError("HTTP client not initialized. Use 'async with' block.")

        # Type narrowing for the checker (_tokens is set by authenticate)
        assert self._tokens is not None

        url = (
            self._tokens.instance_url
            + "/services/data/v60.0/query?"
            + urllib.parse.urlencode({"q": soql})
        )
        headers = {"Authorization": f"Bearer {self._tokens.access_token}"}
        return await self._http.get(url, headers=headers)

    async def _refresh_tokens(self) -> None:
        """Use the stored refresh_token to get a new access_token.

        With Refresh Token Rotation (mandatory May 2026), Salesforce also
        returns a new refresh_token in the response — we MUST replace the
        stored one or future refreshes will fail.

        Passes self._http to oauth.refresh_access_token so the call reuses
        our connection pool — and so MockTransport in tests intercepts it.
        """
        assert self._tokens is not None
        assert self._http is not None

        token_response = await oauth.refresh_access_token(
            self._tokens.refresh_token,
            http=self._http,
        )

        # RTR: use the new refresh_token if Salesforce returned one,
        # otherwise keep the old one (some configurations don't rotate).
        new_refresh = token_response.refresh_token or self._tokens.refresh_token

        self._tokens = StoredTokens(
            access_token=token_response.access_token,
            refresh_token=new_refresh,
            instance_url=token_response.instance_url,
            issued_at=datetime.now(timezone.utc),
        )
        save_tokens(self._tokens)


# ============================================================
# APEX EQUIVALENT (for comparison)
# ============================================================
#
# In Apex, this whole class would be replaced by a Named Credential.
# The platform handles token storage, refresh, and Bearer header injection.
# Your callout code is just:
#
#    HttpRequest req = new HttpRequest();
#    req.setEndpoint('callout:My_Named_Credential/services/data/v60.0/query?q=' +
#                    EncodingUtil.urlEncode('SELECT Id, Name FROM Account', 'UTF-8'));
#    req.setMethod('GET');
#    HttpResponse res = new Http().send(req);
#    // Parse JSON, handle errors — platform already added Bearer header,
#    // refreshed tokens if needed, retried, etc.
#
# IF YOU HAD TO BUILD THIS MANUALLY IN APEX (rare — you'd use Named Credentials):
#
#    public class SalesforceClient {
#        private Auth_Token__c tokens;
#
#        public SalesforceClient() {
#            // Load tokens from DB — Apex has no module-level state
#            this.tokens = [SELECT Access_Token__c, Refresh_Token__c, Instance_URL__c
#                           FROM Auth_Token__c LIMIT 1];
#        }
#
#        public SalesforceQueryResponse query(String soql) {
#            HttpResponse res = doQuery(soql);
#            if (res.getStatusCode() == 401) {
#                refreshTokens();
#                res = doQuery(soql);
#            }
#            return (SalesforceQueryResponse) JSON.deserialize(
#                res.getBody(), SalesforceQueryResponse.class);
#        }
#
#        private HttpResponse doQuery(String soql) {
#            HttpRequest req = new HttpRequest();
#            req.setEndpoint(this.tokens.Instance_URL__c +
#                            '/services/data/v60.0/query?q=' +
#                            EncodingUtil.urlEncode(soql, 'UTF-8'));
#            req.setMethod('GET');
#            req.setHeader('Authorization', 'Bearer ' + this.tokens.Access_Token__c);
#            return new Http().send(req);
#        }
#
#        private void refreshTokens() {
#            // Call /services/oauth2/token, update DB record
#            // ... (full implementation in app/salesforce/auth.py equivalent)
#        }
#    }
#
# Concept mapping:
# - httpx.AsyncClient                    → Apex Http() class (synchronous)
# - async with / __aenter__/__aexit__    → Apex has no equivalent; HTTP calls
#                                          aren't pooled/scoped in user code
# - asyncio.gather(*[...])               → Apex has NO concurrent HTTP calls
#                                          (must use @future or Continuation)
# - self._tokens (instance state)        → Apex inner class fields (same idea)
# - Module-level token_storage           → Custom object (DB-backed only)
# - 401 → refresh → retry logic          → Same pattern; Named Credentials hide it
# - urllib.parse.urlencode               → EncodingUtil.urlEncode
# - response.raise_for_status()          → Manual: if (res.getStatusCode() >= 400) throw...
# - oauth.refresh_access_token(http=...) → Apex's HttpCalloutMock injection in tests
#
# Key difference: Apex's @InvocableMethod and Named Credentials make the
# "happy path" 5 lines of code. The trade-off is you lose control of the
# auth lifecycle. Python gives you control + responsibility.
#
# Production note: the refresh logic above has a subtle race condition.
# If two queries simultaneously get 401, both call _refresh_tokens() and
# the second one might use an already-rotated refresh_token, which would
# now be invalid (RTR invalidates the old one immediately). For Phase 1
# single-user this is acceptable; Phase 2 multi-tenant needs an asyncio.Lock.
# Apex avoids this entirely because Named Credentials serialize refreshes.
# ============================================================