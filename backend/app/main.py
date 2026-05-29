"""FastAPI application entry point."""

import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.interfaces.rest_api.routes import accounts, auth
from app.salesforce.mocks.rest_mock import MockSalesforceClient
from app.salesforce.rest_api import SalesforceClient

# Load .env at startup so USE_MOCK_DATA etc. are available
load_dotenv()


def _use_mock() -> bool:
    """Read USE_MOCK_DATA from env. Defaults to True for safety."""
    return os.environ.get("USE_MOCK_DATA", "true").lower() == "true"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage app-wide resources (created at startup, cleaned up at shutdown).

    Picks Mock or real Salesforce client based on USE_MOCK_DATA env var.
    Both clients have identical async interfaces (duck typing).
    """
    if _use_mock():
        print("Starting MOCK Salesforce client (USE_MOCK_DATA=true)...")
        client = MockSalesforceClient()
    else:
        print("Starting REAL Salesforce client (USE_MOCK_DATA=false)...")
        client = SalesforceClient()

    await client.__aenter__()
    await client.authenticate()
    app.state.sf_client = client
    print("Salesforce client ready.")

    yield

    print("Closing Salesforce client...")
    await client.__aexit__(None, None, None)


app = FastAPI(
    title="Salesforce AI Assistant API",
    description="Backend API for the Salesforce AI Assistant project.",
    version="0.1.0",
    lifespan=lifespan,
)

# ============================================================
# CORS middleware
# Allows browser-based frontends (like React) to call this API.
# For development we allow all origins (*).
# In production (Week 11+) we'll restrict to specific origins.
# ============================================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers for each logical group of endpoints
app.include_router(accounts.router)
app.include_router(auth.router)


@app.get("/health")
async def health_check() -> dict:
    """Simple endpoint to verify the server is running."""
    return {"status": "ok", "message": "Salesforce AI Assistant is alive"}


# No direct Apex equivalent — FastAPI entry point and middleware setup is
# framework-specific infrastructure; Apex equivalents would be platform-managed
# (no entry-point file, no middleware concept — request handling is built into
# the @RestResource framework).