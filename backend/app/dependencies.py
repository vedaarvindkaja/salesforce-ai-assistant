"""Shared dependencies for FastAPI endpoints."""

from typing import Any

from fastapi import HTTPException, Request, status


def get_sf_client(request: Request) -> Any:
    """Get the shared Salesforce client from app state.

    Returns whichever client (mock or real) was registered in main.py's
    lifespan. Endpoints type-hint the specific client they expect.

    Used as a FastAPI dependency:
        async def my_endpoint(client = Depends(get_sf_client)):
            ...
    """
    return request.app.state.sf_client


def get_graph_engine(request: Request) -> tuple:
    """Return the loaded metadata-graph bundle: (engine, graph, cache, org_key).

    The bundle is loaded once in the app lifespan (ADR-015, eager-but-tolerant)
    and stored on app.state. If it's None, the graph isn't available (no OAuth
    tokens / empty cache) — a SERVER-SIDE readiness failure, so we raise 503,
    NOT 401: the caller cannot fix this by re-authenticating. The Week-13
    extension branches on the status (503 -> "run setup", not "re-auth the user").

    Used as a FastAPI dependency on every capability route:
        async def metadata_qa(body, bundle = Depends(get_graph_engine)):
            ...
    """
    bundle = getattr(request.app.state, "graph_bundle", None)
    if bundle is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "metadata graph not loaded — run /auth/login then "
                "extract-to-cache (python -m scripts.extract_to_cache)"
            ),
        )
    return bundle
