"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.interfaces.rest_api.routes import accounts, auth
from app.salesforce.mocks.rest_mock import MockSalesforceClient


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage app-wide resources (created at startup, cleaned up at shutdown)."""
    print("Starting Salesforce client (mock for now — real client lands Day 4 end)...")
    client = MockSalesforceClient()
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