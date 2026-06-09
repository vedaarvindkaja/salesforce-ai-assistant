# No direct Apex equivalent — REST graph-introspection surface (read-only).
"""Read-only metadata-graph introspection (Week 12).

A single deterministic GET that returns the org's graph SHAPE — node/edge counts
and per-type breakdowns — straight from ``MetadataGraph.stats()``. No Claude, no
SSE, no cost: useful scaffolding for the Week-13 VS Code extension to show org
topology (and to sanity-check that the graph loaded) without spending a token.

Kept in its own router (tag ``graph``) rather than the capabilities router so the
OpenAPI surface separates "AI capabilities" from "graph introspection" cleanly.
Still gated by ``get_graph_engine`` — a missing graph is a 503, same as the
capability routes.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.dependencies import get_graph_engine

router = APIRouter(prefix="/api/v1", tags=["graph"])


class GraphSummary(BaseModel):
    """Graph shape snapshot — typed so the extension can generate a client."""

    org_key: str = Field(description="instance_url the graph was built for.")
    node_count: int
    edge_count: int = Field(
        description="Total edges, counting parallel edges (MultiDiGraph; ADR-011)."
    )
    node_type_counts: dict[str, int] = Field(
        description="Node count per NodeType (e.g. ApexClass, ApexTrigger, Object)."
    )
    edge_type_counts: dict[str, int] = Field(
        description="Edge count per EdgeType (e.g. REFERENCES, CALLS, USES_OBJECT)."
    )


@router.get("/graph", response_model=GraphSummary)
async def graph_summary(bundle=Depends(get_graph_engine)) -> GraphSummary:
    """Return node/edge counts and per-type breakdowns for the loaded graph."""
    _engine, graph, _cache, org_key = bundle
    s = graph.stats()
    return GraphSummary(
        org_key=org_key,
        node_count=s.node_count,
        edge_count=s.edge_count,
        node_type_counts=s.node_type_counts,
        edge_type_counts=s.edge_type_counts,
    )
