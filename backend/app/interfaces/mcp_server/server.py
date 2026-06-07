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
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from app.intelligence.graph.builder import GraphBuilder
from app.intelligence.graph.query import QueryEngine
from app.intelligence.graph.storage import MetadataCache
from app.intelligence.orchestration.capabilities import build_capability_client
from app.salesforce.token_storage import load_tokens

# Force UTF-8 on stdio. On Windows, Python may default stdout/stderr to a legacy
# code page (cp1252), which mangles non-ASCII characters (· → Â·, — → â€") seen
# in the Day-3 logs. stdout carries the MCP JSON-RPC stream and stderr carries
# logs; both must be UTF-8 so tool answers (Apex, SOQL, punctuation) and log
# lines survive intact. reconfigure() exists on the standard TextIO streams
# (Python 3.7+); guard in case a host swapped them for something without it.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

# Load .env (ANTHROPIC_API_KEY etc.). Resolve it relative to THIS file rather
# than the cwd, because an MCP host (e.g. Claude Desktop) may launch us from an
# arbitrary working directory (observed: C:\Windows\System32). find_dotenv-style
# cwd search would miss backend/.env in that case.
_BACKEND_DIR = Path(__file__).resolve().parents[3]  # .../backend
load_dotenv(_BACKEND_DIR / ".env")

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

# Cache path resolution — MUST NOT depend on the process working directory.
# An MCP host launches this server from its own cwd (Claude Desktop was observed
# launching from C:\Windows\System32), and the `cwd` config field is not reliably
# honoured. So we resolve the cache path in this order:
#   1. SF_CACHE_PATH env var, if set (the host CAN set env reliably — that's how
#      PYTHONPATH reaches us), else
#   2. <backend>/data/metadata_cache.db, computed relative to THIS source file.
# Both are cwd-independent. ask_cli.py keeps its cwd-relative Path("data")/... —
# it's a short-lived process the user launches from backend/, so cwd is correct
# there; only the host-launched server needs this hardening.
_CACHE_PATH = (
    Path(os.environ["SF_CACHE_PATH"])
    if os.environ.get("SF_CACHE_PATH")
    else _BACKEND_DIR / "data" / "metadata_cache.db"
)

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
# Internal tool-call logging (server-side observability).
#
# These are the ORCHESTRATION tools (find_dependencies, get_source, ...) that
# Claude calls INSIDE the agentic loop — invisible to the MCP host, which only
# sees the capability tool it called. Logging them to stderr surfaces the
# loop's behaviour in the host's server log, which is how we debug Days 3-4
# when we can't watch the loop directly. Mirrors ask_cli's _announce, but to
# the logger (stderr) instead of a bare print.
# ------------------------------------------------------------------
def _log_tool(name: str, handler):
    async def wrapped(inp: dict) -> str:
        logger.info("  [tool] %s(%s)", name, inp)
        return await handler(inp)
    return wrapped


# ------------------------------------------------------------------
# Capability runner — the shared body of all four capability tools.
#
# Each MCP capability tool is a thin wrapper that calls this with a fixed mode.
# Flow:
#   1. Get the cached engine (readable error string if the graph isn't available).
#   2. Build a mode-configured client via the SHARED capabilities.py wiring
#      (same source of truth the CLI uses — no drift).
#   3. Run the agentic loop NON-STREAMING (ask_collected) — MCP tool responses
#      are single strings, not chunks.
#   4. Log per-call cost/usage to stderr ONLY (Day 2 deliverable: per-call cost
#      reporting). NOT appended to the response — see the note at the log line.
# Any unexpected error becomes a readable string rather than an opaque protocol
# fault — a long-lived server must survive one bad call.
# ------------------------------------------------------------------
async def _run_capability(mode: str, question: str) -> str:
    try:
        engine, graph, cache, org_key = await _get_engine()
    except GraphLoadError as exc:
        return f"Graph not available: {exc}"

    try:
        client, schemas = build_capability_client(
            mode, engine, graph, cache, org_key,
            handler_wrapper=_log_tool,
        )
        answer = await client.ask_collected(question, tools=schemas)
    except Exception as exc:  # noqa: BLE001 — surface any failure as readable text
        logger.exception("Capability %r failed", mode)
        return f"Error running {mode}: {exc}"

    # Cost reporting is stderr-ONLY (the log line below). We deliberately do NOT
    # append a footer to the returned string: an MCP host's model reads the tool
    # result as content to interpret, not text to echo, so a footer is absorbed
    # and rewritten away — invisible to the user, while still cluttering the
    # model's context. Verified Day 3: the server sent the footer; Claude Desktop
    # dropped it. stderr is the one channel cost survives, and the one we control.
    s = client.session
    logger.info(
        "capability=%s turns=%d in=%d out=%d cost=$%.4f",
        mode, len(s.turns), s.total_input_tokens, s.total_output_tokens,
        s.total_cost_usd,
    )
    return answer


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


@mcp.tool()
async def metadata_qa(question: str) -> str:
    """Answer a natural-language question about the Salesforce org's metadata
    graph — objects, Apex classes, triggers, flows, and how they depend on
    each other.

    Use for general "what / which / how" questions about org structure and
    dependencies (e.g. "What does the AccountTrigger depend on?", "How is
    PricingFlowAction invoked?"). The answer is grounded in the real graph and
    names the actual components involved.

    Argument:
        question: the natural-language question.
    """
    return await _run_capability("qa", question)


@mcp.tool()
async def explain_apex(question: str) -> str:
    """Explain Apex code, or suggest refactors, in the context of the org's
    metadata graph.

    Use when the user wants to understand what an Apex class or trigger does,
    what it depends on, or how to improve it (e.g. "Explain TriggerDispatcher",
    "How should I refactor AccountService for bulk safety?"). The explanation is
    anchored to the dependency graph, not guessed from the name.

    Argument:
        question: what to explain or refactor (name the class/trigger).
    """
    return await _run_capability("apex", question)


@mcp.tool()
async def generate_soql(question: str) -> str:
    """Generate SOQL using the org's ACTUAL schema (real object and component
    names from the metadata graph).

    Use when the user describes, in natural language, the data they want to
    query (e.g. "Opportunities created last quarter for accounts with no
    contacts"). Returns SOQL plus a short rationale.

    Scope note: object/class awareness only — this does NOT validate individual
    field names (the graph tracks components at object grain, not field grain).

    Argument:
        question: a natural-language description of the data to query.
    """
    return await _run_capability("soql", question)


@mcp.tool()
async def analyze_deployment_impact(question: str) -> str:
    """Trace the blast radius of changing or deploying a component: what depends
    on it and could break.

    Topology-only — it analyses the dependency graph and does NOT read source.
    Use for "what breaks if I change X?" questions (e.g. "What is the deployment
    impact of changing the Opportunity object?"). Returns the affected
    components and how each is wired to the target (SOQL/DML, method call, Flow
    action, reference).

    Argument:
        question: the change to analyse (name the component).
    """
    return await _run_capability("impact", question)


# ------------------------------------------------------------------
# Entry point — stdio transport.
# ------------------------------------------------------------------
def main() -> None:
    """Launch the MCP server over stdio. Blocks until the host disconnects."""
    logger.info("Starting salesforce-metadata-graph MCP server (stdio)...")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
