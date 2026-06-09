"""FastAPI application entry point."""

import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.interfaces.rest_api.routes import accounts, auth, capabilities
from app.interfaces.rest_api.routes import graph as graph_routes
from app.intelligence.graph.bootstrap import GraphLoadError, load_graph
from app.salesforce.mocks.rest_mock import MockSalesforceClient
from app.salesforce.rest_api import RestAPIClient

# Load .env at startup so USE_MOCK_DATA etc. are available
load_dotenv()


def _use_mock() -> bool:
    """Read USE_MOCK_DATA from env. Defaults to True for safety."""
    return os.environ.get("USE_MOCK_DATA", "true").lower() == "true"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage app-wide resources (created at startup, cleaned up at shutdown).

    Two resources are set up here:

      1. The Salesforce REST client (mock or real) for the account endpoints
         (unchanged from Week 4).
      2. The metadata graph for the capability + graph endpoints (ADR-015),
         loaded eagerly but TOLERANTLY: the load is attempted once at startup so
         request handlers don't pay for it, but a failure must NOT crash the app.
         In mock mode / a fresh checkout there are no tokens or cache, and the
         account endpoints plus the test suite must still come up. On failure we
         store None and let the capability/graph routes return a clean 503 at
         request time (via get_graph_engine).

    Note: the graph load is independent of USE_MOCK_DATA — it reads stored OAuth
    tokens + the local cache directly, so a real 57-node graph loads even when
    the account client is the mock.
    """
    # --- 1. Salesforce REST client (unchanged from Week 4) ---
    if _use_mock():
        print("Starting MOCK Salesforce client (USE_MOCK_DATA=true)...")
        client = MockSalesforceClient()
    else:
        print("Starting REAL Salesforce client (USE_MOCK_DATA=false)...")
        client = RestAPIClient()

    await client.__aenter__()
    await client.authenticate()
    app.state.sf_client = client
    print("Salesforce client ready.")

    # --- 2. Metadata graph (eager-but-tolerant; ADR-015) ---
    try:
        app.state.graph_bundle = await load_graph()
        _engine, graph, _cache, org_key = app.state.graph_bundle
        stats = graph.stats()
        print(
            f"Metadata graph ready: {stats.node_count} nodes / "
            f"{stats.edge_count} edges (org_key={org_key})."
        )
    except GraphLoadError as exc:
        app.state.graph_bundle = None
        print(
            f"Metadata graph NOT loaded ({exc}). Capability endpoints will "
            "return 503 until OAuth tokens and a populated cache exist."
        )

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
# Dev: allow all origins. Tighten to the extension's origin at launch
# (Week 13+) — tracked, not done here.
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
app.include_router(capabilities.router)
app.include_router(graph_routes.router)


@app.get("/health")
async def health_check() -> dict:
    """Simple endpoint to verify the server is running."""
    return {"status": "ok", "message": "Salesforce AI Assistant is alive"}
