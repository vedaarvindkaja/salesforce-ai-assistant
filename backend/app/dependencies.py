"""Shared dependencies for FastAPI endpoints."""

from typing import Any

from fastapi import Request


def get_sf_client(request: Request) -> Any:
    """Get the shared Salesforce client from app state.

    Returns whichever client (mock or real) was registered in main.py's
    lifespan. Endpoints type-hint the specific client they expect.

    Used as a FastAPI dependency:
        async def my_endpoint(client: MockSalesforceClient = Depends(get_sf_client)):
            ...
    """
    return request.app.state.sf_client