"""Salesforce REST API client.

Async, typed client that authenticates and runs SOQL queries.
Built during Week 2 (async learning); will be wrapped by FastAPI in Week 3.

Note: requires a valid sf_secrets.py file (not committed, see .gitignore).
For now, use MockSalesforceClient instead — real auth is broken until Week 4.
"""

import asyncio
import urllib.parse
from typing import Optional

import httpx

from app.models.salesforce import (
    SalesforceAuthResponse,
    SalesforceQueryResponse,
)


class SalesforceClient:
    """An async, typed Salesforce REST API client.

    Usage:
        async with SalesforceClient() as client:
            await client.authenticate()
            result = await client.query("SELECT Id, Name FROM Account LIMIT 5")
    """

    def __init__(self):
        self.auth: Optional[SalesforceAuthResponse] = None
        self._http: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        """Open HTTP client when entering 'async with' block."""
        self._http = httpx.AsyncClient(timeout=30.0)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Close HTTP client when exiting 'async with' block."""
        if self._http:
            await self._http.aclose()

    async def authenticate(self) -> None:
        """Authenticate to Salesforce and store credentials."""
        if self._http is None:
            raise RuntimeError("Use this client inside 'async with' block.")

        # Imported here so the module loads even when sf_secrets.py is missing
        # sf_secrets.py is gitignored — only exists locally with real credentials
        from sf_secrets import credentials   # type: ignore
        creds = credentials()

        token_url = creds["login_url"] + "/services/oauth2/token"
        data = {
            "grant_type": "password",
            "client_id": creds["client_id"],
            "client_secret": creds["client_secret"],
            "username": creds["username"],
            "password": creds["password"],
        }

        response = await self._http.post(token_url, data=data)
        response.raise_for_status()
        self.auth = SalesforceAuthResponse.model_validate_json(response.text)

    async def query(self, soql: str) -> SalesforceQueryResponse:
        """Run a SOQL query — returns typed Pydantic response."""
        if self.auth is None:
            raise RuntimeError("Not authenticated. Call authenticate() first.")

        query_url = (
            self.auth.instance_url
            + "/services/data/v60.0/query?"
            + urllib.parse.urlencode({"q": soql})
        )
        headers = {"Authorization": f"Bearer {self.auth.access_token}"}

        response = await self._http.get(query_url, headers=headers)
        response.raise_for_status()
        return SalesforceQueryResponse.model_validate_json(response.text)

    async def query_all(self, *soqls: str) -> list[SalesforceQueryResponse]:
        """Run multiple SOQL queries concurrently."""
        if self.auth is None:
            raise RuntimeError("Not authenticated.")
        return await asyncio.gather(*[self.query(s) for s in soqls])