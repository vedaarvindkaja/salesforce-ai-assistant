# No direct Apex equivalent — MCP stdio server entry point (interfaces/ layer, ADR-001).
"""MCP server — exposes the metadata-graph capabilities over the Model Context
Protocol (stdio transport).

This is a NEW TRANSPORT over the existing orchestration stack, not a
reimplementation. The capability logic (graph + tools + Claude agentic loop)
is unchanged; this module only adapts it to MCP's request/response shape.

Key differences from ask_cli.py (the other AI surface):
- ask_cli is a SHORT-LIVED process: one question, one _load(), then exit.
  This server is LONG-LIVED: a host (Claude Desktop / Claude Code / Augment)
  launches it once and sends many tool calls over its lifetime. So the graph
  is loaded ONCE and cached (see _get_engine), not rebuilt per call.
- ask_cli STREAMS to stdout. MCP tool responses are SINGLE STRINGS, so the
  capability tools (Day 2) will call ClaudeClient.ask_collected(), not ask().
- stdout is RESERVED for the MCP JSON-RPC protocol. Nothing in this process
  may print to stdout except the MCP framework itself. All diagnostics go to
  stderr (logging is configured to stderr below). A stray print() to stdout
  corrupts the protocol stream and breaks the client connection.

Day 1 scope: scaffold only — lazy graph bootstrap + a single `health` tool
that proves the transport end-to-end. The four capability tools (qa/apex/
soql/impact) are wired on Day 2.

Run directly for a local smoke test:
    python -m app.interfaces.mcp_server.server
(It will block waiting for an MCP client on stdin — Ctrl+C to exit.)
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from app.intelligence.graph.builder import GraphBuilder
from app.intelligence.graph.query import QueryEngine
from app.intelligence.graph.storage import MetadataCache
from app.salesforce.token_storage import load_tokens

# Load .env (ANTHROPIC_API_KEY etc.) at import, same as ask_cli.py.
load_dotenv()

# ------------------------------------------------------------------
# Logging — STDERR ONLY.
# stdout belongs to the MCP JSON-RPC stream; logging there would corrupt it.
# ------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    stream=sys.stderr,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("mcp_server")

# Mirror ask_cli.py / cli.py exactly — the cache path is relative to backend/,
# so the server MUST be launched with backend/ as the working directory.
# (Client configs in Day 3-4 set this explicitly.)
_CACHE_PATH = Path("data") / "metadata_cache.db"

# ------------------------------------------------------------------
# The MCP server instance.
# The name is what shows up in the host's tool/connection list.
# ------------------------------------------------------------------
mcp = FastMCP("salesforce-metadata-graph")

# ------------------------------------------------------------------
# Lazy graph bootstrap (cached for the life of the process).
#
# We DON'T load at import/startup (eager) on purpose: inside a host like
# Claude Desktop, a process that exits during startup shows only as
# "failed to connect" with no readable reason. Lazy-loading lets the server
# start cleanly and return a clear error STRING on first tool call if the
# cache/tokens are missing — a message the user can actually read in-client.
#
# Module-level cache: the first tool call builds the engine; every call after
# reuses it. The 57-node graph builds in ~0.3s, but rebuilding it on every
# tool call in a long-lived process would be wasteful and pointless.
# ------------------------------------------------------------------
_engine: QueryEngine | None = None
_graph = None
_cache: MetadataCache | None = None
_org_key: str | None = None


class GraphLoadError(Exception):
    """Raised when the graph can't be bootstrapped. Carries a user-facing
    message that tool handlers turn into a returned error string (rather than
    letting the exception escape and surface as an opaque protocol error)."""


async def _get_engine() -> tuple[QueryEngine, object, MetadataCache, str]:
    """Return the cached (engine, graph, cache, org_key), building once.

    Raises GraphLoadError with a readable message if prerequisites are missing.
    Mirrors ask_cli._load(), but raises a catchable error instead of SystemExit
    (a long-lived server must not exit the process on a single bad call).
    """
    global _engine, _graph, _cache, _org_key
    if _engine is not None:
        return _engine, _graph, _cache, _org_key  # type: ignore[return-value]

    tokens = load_tokens()
    if tokens is None:
        raise GraphLoadError(
            "No OAuth tokens found. Visit http://localhost:8000/auth/login, "
            "then run: python -m scripts.extract_to_cache"
        )
    org_key = tokens.instance_url
    if not _CACHE_PATH.exists():
        raise GraphLoadError(
            f"Cache not found at {_CACHE_PATH.resolve()}. "
            "Run: python -m scripts.extract_to_cache "
            "(and launch the server with backend/ as the working directory)."
        )
    cache = MetadataCache(_CACHE_PATH)
    graph = await GraphBuilder(cache).build(org_key=org_key)
    if graph.stats().node_count == 0:
        raise GraphLoadError(
            f"Graph is empty for org_key={org_key!r}. "
            "Re-run: python -m scripts.extract_to_cache"
        )

    _engine, _graph, _cache, _org_key = QueryEngine(graph), graph, cache, org_key
    logger.info(
        "Graph loaded: %d nodes / %d edges (org_key=%s)",
        graph.stats().node_count,
        graph.stats().edge_count,
        org_key,
    )
    return _engine, _graph, _cache, _org_key


# ------------------------------------------------------------------
# Tools
# ------------------------------------------------------------------
@mcp.tool()
async def health() -> str:
    """Report metadata-graph server health and basic stats.

    Use this to confirm the server is running and the graph is loaded.
    Returns node/edge counts and per-type breakdowns. Takes no arguments.
    """
    try:
        _engine_, graph, _cache_, org_key = await _get_engine()
    except GraphLoadError as exc:
        return f"Graph not available: {exc}"

    s = graph.stats()
    return (
        "Salesforce metadata-graph MCP server: OK\n"
        f"  org_key: {org_key}\n"
        f"  nodes:   {s.node_count}  {s.node_type_counts}\n"
        f"  edges:   {s.edge_count}  {s.edge_type_counts}"
    )


# ------------------------------------------------------------------
# Entry point — stdio transport.
# ------------------------------------------------------------------
def main() -> None:
    """Launch the MCP server over stdio. Blocks until the host disconnects."""
    logger.info("Starting salesforce-metadata-graph MCP server (stdio)...")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
