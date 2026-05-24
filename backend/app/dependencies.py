"""Shared dependencies for FastAPI endpoints."""

from fastapi import Request
from app.services.salesforce_mock import MockSalesforceClient


def get_sf_client(request: Request) -> MockSalesforceClient:
    """Get the shared Salesforce client from app state.
    
    Used as a FastAPI dependency:
        async def my_endpoint(client: MockSalesforceClient = Depends(get_sf_client)):
            ...
    """
    return request.app.state.sf_client