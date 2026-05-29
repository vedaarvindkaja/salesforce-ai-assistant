"""REST API client — high-level wrapper for Salesforce's data REST API.

Holds a SalesforceHTTPClient (composition) and exposes domain methods:
    - query() — run a SOQL query, return typed response

This client does NOT manage tokens, refresh, or HTTP lifecycle. That's
SalesforceHTTPClient's job. This file is purely about REST API operations:
URL paths, query parameters, response parsing.

Drop-in replacement for MockSalesforceClient — same async interface
(__aenter__, authenticate, query, query_all) so endpoints don't know
which one's behind the dependency.

See ADR-003 for the design rationale of this split.
"""

import asyncio

from app.models.salesforce import SalesforceQueryResponse
from app.salesforce.http_client import SalesforceHTTPClient


class RestAPIClient:
    """High-level Salesforce REST API client.

    Usage:
        async with RestAPIClient() as client:
            await client.authenticate()
            result = await client.query("SELECT Id, Name FROM Account LIMIT 5")
    """

    def __init__(self, http: SalesforceHTTPClient | None = None):
        """Construct a REST client.

        Args:
            http: Optional SalesforceHTTPClient. If omitted, a new one is created.
                  Pass an existing one to share connection pool / token state
                  with other API clients (e.g., RestAPIClient + ToolingAPIClient
                  sharing the same HTTP transport).
        """
        self._http = http if http is not None else SalesforceHTTPClient()

    # ----- async context manager (mirrors MockSalesforceClient) -----

    async def __aenter__(self):
        await self._http.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._http.__aexit__(exc_type, exc_val, exc_tb)

    # ----- authentication (delegates to HTTP client) -----

    async def authenticate(self) -> None:
        """Load OAuth tokens from storage via the underlying HTTP client."""
        await self._http.authenticate()

    # ----- REST operations -----

    async def query(self, soql: str) -> SalesforceQueryResponse:
        """Run a SOQL query against the REST API and parse the response.

        Refresh-on-401 happens transparently in the HTTP client — this method
        just handles URL construction and Pydantic parsing.
        """
        response = await self._http.request(
            "GET",
            "/services/data/v60.0/query",
            params={"q": soql},
        )
        response.raise_for_status()
        return SalesforceQueryResponse.model_validate_json(response.text)

    async def query_all(self, *soqls: str) -> list[SalesforceQueryResponse]:
        """Run multiple SOQL queries concurrently.

        Note: if multiple queries simultaneously trigger a refresh, the
        refreshes may race. For Phase 1 single-user this is acceptable
        (worst case: a few extra refresh calls). Phase 2 needs an asyncio.Lock
        around _refresh_tokens.
        """
        return await asyncio.gather(*[self.query(s) for s in soqls])


# Backwards-compatibility alias — Week 4 code and tests imported `SalesforceClient`.
# Keeping the name available so we don't have to edit every import in a single PR.
# Plan to remove the alias in Week 6 when the codebase has fully internalized
# the RestAPIClient name.
SalesforceClient = RestAPIClient


# ============================================================
# APEX EQUIVALENT (for comparison)
# ============================================================
#
# In Apex, you almost never see this split because Named Credentials handle
# the auth layer. Your "REST client" is just a class that builds URLs:
#
#    public class RestApiClient {
#        public SalesforceQueryResponse query(String soql) {
#            HttpRequest req = new HttpRequest();
#            req.setEndpoint('callout:My_NC/services/data/v60.0/query?q=' +
#                            EncodingUtil.urlEncode(soql, 'UTF-8'));
#            req.setMethod('GET');
#            // No auth header — platform injects it via Named Credential
#            HttpResponse res = new Http().send(req);
#            return (SalesforceQueryResponse) JSON.deserialize(
#                res.getBody(), SalesforceQueryResponse.class);
#        }
#    }
#
# If you HAD to do the layered split in Apex (e.g., to share auth logic
# across multiple API endpoint families when not using Named Credentials):
#
#    public class RestApiClient {
#        private SalesforceHttpClient http;
#
#        public RestApiClient(SalesforceHttpClient http) {
#            this.http = http;  // dependency injection via constructor
#        }
#
#        public SalesforceQueryResponse query(String soql) {
#            HttpResponse res = http.request('GET',
#                '/services/data/v60.0/query',
#                new Map<String, String>{'q' => soql},
#                null);
#            return (SalesforceQueryResponse) JSON.deserialize(
#                res.getBody(), SalesforceQueryResponse.class);
#        }
#    }
#
# Then the lifespan/composition root creates one HTTP client and shares it:
#
#    SalesforceHttpClient http = new SalesforceHttpClient();
#    RestApiClient rest = new RestApiClient(http);
#    ToolingApiClient tooling = new ToolingApiClient(http);   // same instance
#
# Concept mapping:
# - Composition (RestAPIClient holds SalesforceHTTPClient)  → Same in Apex
#                                                              with explicit DI
# - `http: SalesforceHTTPClient | None = None`              → Apex requires
#                                                              constructor overloading
# - `SalesforceClient = RestAPIClient` (rename alias)       → Apex requires
#                                                              actually renaming all
#                                                              callsites (no alias)
# - asyncio.gather(*[...])                                  → @future methods or
#                                                              Queueable.attach chain
# - response.raise_for_status()                             → manual: if (res.getStatusCode()
#                                                              >= 400) throw new ...
#
# Pythonic note: the `SalesforceClient = RestAPIClient` line at module bottom is
# a Python idiom for "I renamed this but want the old name to still work."
# Classes are first-class objects; assigning one to another name creates a
# second reference to the same class. Apex has no equivalent; renames require
# touching every callsite atomically.
# ============================================================