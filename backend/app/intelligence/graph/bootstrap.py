# No direct Apex equivalent — graph bootstrap: assembles the metadata graph from
# the local cache + stored OAuth tokens into a query-ready engine bundle.
"""Shared metadata-graph loader (ADR-015).

The single place that turns "stored OAuth tokens + a populated SQLite cache"
into a query-ready ``(engine, graph, cache, org_key)`` bundle.

Before this module the same load dance lived in THREE hand-copied variants:
``ask_cli._load()``, ``cli._load_graph()`` and the MCP server's
``_get_engine()``. That is exactly the drift the single-source discipline
(ADR-013) exists to prevent, and with the REST API becoming the third consumer
it crossed the threshold for extraction.

This function is deliberately TIMING-AGNOSTIC: it does not cache and it does not
decide when to run. Each interface keeps its own lifecycle at the edge:

  - CLI  : calls it per-invocation; translates failure to ``SystemExit``.
  - MCP  : calls it lazily on first tool use, caches the result module-level,
           translates failure to a readable error STRING (preserving the
           deliberate laziness that stops a host from showing only
           "failed to connect" with no readable reason).
  - REST : calls it once, eagerly, in the app lifespan and stores the bundle in
           ``app.state``; a missing graph becomes a 503 at request time.

Keeping the function pure is precisely what lets MCP stay lazy and REST be eager
off the very same code — neither lifecycle is baked in here.

Cache-path resolution is cwd-INDEPENDENT (lifted from the MCP server's Week-11
hardening): an MCP host or a service manager may launch the process from an
arbitrary working directory, so the cache is resolved from ``SF_CACHE_PATH`` or
relative to THIS file's location under ``backend/`` — never relative to
``os.getcwd()``.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

from app.intelligence.graph.builder import GraphBuilder
from app.intelligence.graph.query import QueryEngine
from app.intelligence.graph.storage import MetadataCache
from app.salesforce.token_storage import load_tokens

logger = logging.getLogger(__name__)


class GraphLoadError(Exception):
    """Raised when the metadata graph can't be bootstrapped (missing tokens,
    missing cache, or an empty graph).

    Carries a user-facing message that each interface renders in its own idiom:
    the CLI prints it as exit text, the MCP server returns it as a tool error
    string, and the REST API surfaces it as a 503 body. It is intentionally a
    plain ``Exception`` (never ``SystemExit``) so a long-lived server can catch
    it and survive a single bad call.
    """


def _default_cache_path() -> Path:
    """Resolve the cache path without depending on the current working dir.

    Priority:
      1. ``SF_CACHE_PATH`` env override (set by long-lived hosts/services).
      2. ``backend/data/metadata_cache.db`` resolved relative to THIS file
         (``backend/app/intelligence/graph/bootstrap.py`` → ``parents[3]`` is
         ``backend/``).

    Mirrors the MCP server's cwd-independence so REST inherits that hardening
    instead of re-paying for the cwd bug discovered in Week 11 Day 3.
    """
    override = os.environ.get("SF_CACHE_PATH")
    if override:
        return Path(override)
    backend_root = Path(__file__).resolve().parents[3]  # graph→intelligence→app→backend
    return backend_root / "data" / "metadata_cache.db"


async def load_graph(
    cache_path: Path | None = None,
) -> tuple[QueryEngine, object, MetadataCache, str]:
    """Build the metadata graph from the local cache and return a query-ready
    bundle ``(engine, graph, cache, org_key)``.

    The graph slot is annotated ``object`` (rather than importing the concrete
    ``MetadataGraph`` type) to keep this low-level module import-light — the
    same choice the MCP server's ``_get_engine`` made.

    Args:
        cache_path: explicit cache location; defaults to the cwd-independent
            resolution above. Tests pass a tmp path to stay hermetic.

    Raises:
        GraphLoadError: if OAuth tokens are missing, the cache file is absent,
            or the built graph has zero nodes. Always catchable — never
            ``SystemExit``.
    """
    path = cache_path or _default_cache_path()

    tokens = load_tokens()
    if tokens is None:
        raise GraphLoadError(
            "No OAuth tokens found. Visit http://localhost:8000/auth/login, "
            "then run: python -m scripts.extract_to_cache"
        )
    org_key = tokens.instance_url

    if not path.exists():
        raise GraphLoadError(
            f"Cache not found at {path.resolve()}. "
            "Run: python -m scripts.extract_to_cache"
        )

    cache = MetadataCache(path)
    graph = await GraphBuilder(cache).build(org_key=org_key)
    if graph.stats().node_count == 0:
        raise GraphLoadError(
            f"Graph is empty for org_key={org_key!r}. "
            "Re-run: python -m scripts.extract_to_cache"
        )

    logger.info(
        "Graph loaded: %d nodes / %d edges (org_key=%s)",
        graph.stats().node_count,
        graph.stats().edge_count,
        org_key,
    )
    return QueryEngine(graph), graph, cache, org_key
