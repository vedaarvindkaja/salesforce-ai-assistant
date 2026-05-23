"""Mock Salesforce client for development without live Salesforce.

Useful when auth is broken or you don't want to burn API limits.
Has the same interface as SalesforceClient — your code calls them identically.
Will be used during Week 3 (FastAPI build) until Salesforce auth is fixed in Week 4.
"""

import asyncio
from typing import Optional

from app.models.salesforce import (
    SalesforceAuthResponse,
    SalesforceQueryResponse,
)


class MockSalesforceClient:
    """Mock async Salesforce client with same shape as the real one."""

    def __init__(self):
        self.auth: Optional[SalesforceAuthResponse] = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    async def authenticate(self) -> None:
        """Simulate the auth call."""
        await asyncio.sleep(0.3)   # simulate network delay

        mock_auth_json = """
        {
            "access_token": "00D5g00000FakeToken",
            "instance_url": "https://your-org.my.salesforce.com",
            "id": "https://login.salesforce.com/id/00D/005",
            "token_type": "Bearer",
            "issued_at": "1734567890123",
            "signature": "FakeSig="
        }
        """
        self.auth = SalesforceAuthResponse.model_validate_json(mock_auth_json)

    async def query(self, soql: str) -> SalesforceQueryResponse:
        """Simulate a SOQL query — returns realistic mock data."""
        if self.auth is None:
            raise RuntimeError("Not authenticated. Call authenticate() first.")

        await asyncio.sleep(0.8)   # simulate network delay

        mock_response = """
        {
            "totalSize": 3,
            "done": true,
            "records": [
                {
                    "attributes": {"type": "Account", "url": "/services/.../001"},
                    "Id": "0015g00000Abc1AAB",
                    "Name": "Edge Communications",
                    "Industry": "Electronics",
                    "AnnualRevenue": 139000000,
                    "Phone": "(512) 757-6000",
                    "Website": "http://edgecomm.com",
                    "CreatedDate": "2024-03-15T10:30:00.000+0000"
                },
                {
                    "attributes": {"type": "Account", "url": "/services/.../002"},
                    "Id": "0015g00000Def2BBC",
                    "Name": "Burlington Textiles Corp",
                    "Industry": "Apparel",
                    "AnnualRevenue": 350000000,
                    "Phone": "(336) 222-7000",
                    "Website": null,
                    "CreatedDate": "2024-01-22T08:15:00.000+0000"
                },
                {
                    "attributes": {"type": "Account", "url": "/services/.../003"},
                    "Id": "0015g00000Ghi3CCD",
                    "Name": "GenePoint",
                    "Industry": null,
                    "AnnualRevenue": null,
                    "Phone": null,
                    "Website": null,
                    "CreatedDate": "2023-11-10T14:45:00.000+0000"
                }
            ]
        }
        """
        return SalesforceQueryResponse.model_validate_json(mock_response)

    async def query_all(self, *soqls: str) -> list[SalesforceQueryResponse]:
        """Run multiple SOQL queries concurrently."""
        if self.auth is None:
            raise RuntimeError("Not authenticated.")
        return await asyncio.gather(*[self.query(s) for s in soqls])