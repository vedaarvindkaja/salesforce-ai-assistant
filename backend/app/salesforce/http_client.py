"""Shared HTTP transport for Salesforce APIs.

Owns the OAuth lifecycle for any Salesforce API call:
- httpx.AsyncClient instance + connection pool
- access_token + refresh_token state (loaded from token_storage)
- transparent refresh-on-401 with single retry
- persistence of rotated refresh_tokens

Higher-level clients (RestAPIClient, ToolingAPIClient, future MetadataAPIClient)
hold an instance of this class and call `request()`. They don't see auth or
refresh logic — that's this module's job.

Built Week 5 Day 1 by extracting the HTTP+auth logic from the original
Week 4 SalesforceClient. See ADR-003 for the design rationale.
"""

import urllib.parse
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

from app.salesforce import auth as oauth
from app.salesforce.oauth_models import StoredTokens
from app.salesforce.token_storage import load_tokens, save_tokens


class SalesforceHTTPClient:
    """An async, OAuth-aware Salesforce HTTP transport.

    Not used directly by FastAPI endpoints — wrapped by RestAPIClient,
    ToolingAPIClient, etc.

    Usage (from a higher-level client):
        http = SalesforceHTTPClient()
        async with http:
            await http.authenticate()
            response = await http.request("GET", "/services/data/v60.0/query",
                                          params={"q": "SELECT Id FROM Account"})
    """

    def __init__(self):
        self._tokens: Optional[StoredTokens] = None
        self._http: Optional[httpx.AsyncClient] = None

    # ----- async context manager -----

    async def __aenter__(self):
        """Open httpx client when entering 'async with' block."""
        self._http = httpx.AsyncClient(timeout=30.0)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Close httpx client when exiting 'async with' block."""
        if self._http is not None:
            await self._http.aclose()
            self._http = None

    # ----- authentication -----

    async def authenticate(self) -> None:
        """Load tokens from storage. Raises if none exist.

        Does not perform a network call. The first actual API request will
        validate the token; if Salesforce rejects it (401), we refresh then.
        """
        tokens = load_tokens()
        if tokens is None:
            raise RuntimeError(
                "No OAuth tokens found. Visit http://localhost:8000/auth/login "
                "to authenticate, then restart the server."
            )
        self._tokens = tokens

    # ----- public HTTP API -----

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[dict[str, Any]] = None,
        json: Optional[dict[str, Any]] = None,
    ) -> httpx.Response:
        """Make an HTTP call against the Salesforce instance.

        `path` is a Salesforce-relative path like "/services/data/v60.0/query".
        The instance_url from stored tokens is prepended automatically.

        Transparently refreshes the access_token on 401 and retries the
        original request once. Other status codes are returned to the caller
        unchanged — callers decide whether to raise.

        Args:
            method: "GET", "POST", "PATCH", "DELETE", etc.
            path: Salesforce-relative path (must start with /)
            params: Query-string parameters (urlencoded for you)
            json: JSON body for POST/PATCH

        Returns:
            httpx.Response — caller is responsible for status checks and parsing.
        """
        if self._tokens is None:
            raise RuntimeError("Not authenticated. Call authenticate() first.")

        response = await self._do_request(method, path, params=params, json=json)

        if response.status_code == 401:
            # Token expired or invalidated — refresh and retry once
            await self._refresh_tokens()
            response = await self._do_request(method, path, params=params, json=json)

        return response

    # ----- internals -----

    async def _do_request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[dict[str, Any]] = None,
        json: Optional[dict[str, Any]] = None,
    ) -> httpx.Response:
        """Single HTTP attempt. Returns raw response without parsing or 401 handling."""
        if self._http is None:
            raise RuntimeError("HTTP client not initialized. Use 'async with' block.")
        assert self._tokens is not None

        url = self._tokens.instance_url + path
        if params:
            url += "?" + urllib.parse.urlencode(params)

        headers = {"Authorization": f"Bearer {self._tokens.access_token}"}

        return await self._http.request(method, url, headers=headers, json=json)

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
# In Apex, this whole class is replaced by the platform's Named Credential
# infrastructure. The platform owns the auth lifecycle; your code just makes
# callouts to `callout:My_Named_Credential/path` and Bearer headers + refresh
# happen invisibly.
#
# If you HAD to implement this manually in Apex (rare — for OAuth flows
# Named Credentials don't support):
#
#    public virtual class SalesforceHttpClient {
#        protected Auth_Token__c tokens;
#
#        public SalesforceHttpClient() {
#            this.tokens = [SELECT Access_Token__c, Refresh_Token__c, Instance_URL__c
#                           FROM Auth_Token__c LIMIT 1];
#        }
#
#        public HttpResponse request(String method, String path,
#                                    Map<String, String> queryParams,
#                                    String jsonBody) {
#            HttpResponse res = doRequest(method, path, queryParams, jsonBody);
#            if (res.getStatusCode() == 401) {
#                refreshTokens();
#                res = doRequest(method, path, queryParams, jsonBody);
#            }
#            return res;
#        }
#
#        protected HttpResponse doRequest(String method, String path,
#                                         Map<String, String> queryParams,
#                                         String jsonBody) {
#            HttpRequest req = new HttpRequest();
#            String url = this.tokens.Instance_URL__c + path;
#            if (queryParams != null && !queryParams.isEmpty()) {
#                url += '?' + buildQueryString(queryParams);
#            }
#            req.setEndpoint(url);
#            req.setMethod(method);
#            req.setHeader('Authorization', 'Bearer ' + this.tokens.Access_Token__c);
#            if (jsonBody != null) {
#                req.setHeader('Content-Type', 'application/json');
#                req.setBody(jsonBody);
#            }
#            return new Http().send(req);
#        }
#
#        protected void refreshTokens() {
#            // POST to /services/oauth2/token, update Auth_Token__c record
#        }
#    }
#
# Then RestApiClient and ToolingApiClient EXTEND SalesforceHttpClient
# (composition is awkward in Apex without dependency injection frameworks):
#
#    public class RestApiClient extends SalesforceHttpClient {
#        public QueryResponse query(String soql) {
#            HttpResponse res = request('GET', '/services/data/v60.0/query',
#                new Map<String, String>{'q' => soql}, null);
#            return (QueryResponse) JSON.deserialize(res.getBody(), QueryResponse.class);
#        }
#    }
#
# Concept mapping:
# - Composition (HTTPClient held by RestAPIClient)  → Inheritance in Apex
#                                                     (Apex lacks easy DI for this)
# - async / await                                   → Apex is synchronous (use
#                                                     Queueable / @future for async)
# - request(method, path, *, params, json)         → request(String, String,
#                                                     Map<String,String>, String)
# - keyword-only arguments (the * separator)        → Apex method overloading
# - urllib.parse.urlencode                          → manual string building or
#                                                     EncodingUtil.urlEncode per key
# - Optional[StoredTokens] / typed None             → Apex `null` (untyped)
#
# Pythonic note: the `*` in `def request(self, method, path, *, params=None, json=None)`
# forces `params` and `json` to be passed as keyword arguments. This is good API
# design — `request("GET", "/foo", {"q": "..."}, None)` is hard to read; forcing
# `request("GET", "/foo", params={"q": "..."})` is self-documenting. Apex doesn't
# have an equivalent; you'd use a builder pattern or a request struct.
# ============================================================