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
  capability tools call ClaudeClient.ask_collected(), not ask().
- stdout is RESERVED for the MCP JSON-RPC protocol. Nothing in this process
  may print to stdout except the MCP framework itself. All diagnostics go to
  stderr (logging is configured to stderr below). A stray print() to stdout
  corrupts the protocol stream and breaks the client connection.

Tools: health + five capabilities (metadata_qa / explain_apex / generate_soql /
analyze_deployment_impact / diagnose_debug_log). The debug-log tool (Week 12)
takes a log REFERENCE rather than a question (ADR-017) and is named distinctly
from the internal analyze_debug_log graph tool the agentic loop calls.

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

from app.intelligence.graph.bootstrap import GraphLoadError, load_graph
from app.intelligence.graph.query import QueryEngine
from app.intelligence.graph.storage import MetadataCache
from app.intelligence.orchestration.capabilities import (
    build_capability_client,
    compose_debuglog_input,
)

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

# Cache-path resolution is delegated to bootstrap.load_graph (ADR-015): it
# applies the same cwd-independent rule the server used to compute inline —
# SF_CACHE_PATH env var if set, else <backend>/data/metadata_cache.db relative
# to the source file. The host launches us from an arbitrary cwd (observed:
# C:\Windows\System32), so this MUST stay cwd-independent — which load_graph is.

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


async def _get_engine() -> tuple[QueryEngine, object, MetadataCache, str]:
    """Return the cached (engine, graph, cache, org_key), building once via the
    shared loader (ADR-015).

    The module-level cache is this server's concern (a long-lived process must
    not rebuild per call); the LOAD itself — tokens, cache, empty-graph check,
    cwd-independent path — is delegated to bootstrap.load_graph, the single
    source the CLI and REST also use. load_graph raises GraphLoadError, which
    the tool handlers turn into a readable error string rather than letting it
    escape as an opaque protocol fault (a server must survive one bad call).
    """
    global _engine, _graph, _cache, _org_key
    if _engine is not None:
        return _engine, _graph, _cache, _org_key  # type: ignore[return-value]

    _engine, _graph, _cache, _org_key = await load_graph()
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
# Capability runner — the shared body of the question-shaped capability tools.
#
# Each MCP capability tool is a thin wrapper that calls this with a fixed mode.
# Flow:
#   1. Get the cached engine (readable error string if the graph isn't available).
#   2. Build a mode-configured client via the SHARED capabilities.py wiring
#      (same source of truth the CLI uses — no drift).
#   3. Run the agentic loop NON-STREAMING (ask_collected) — MCP tool responses
#      are single strings, not chunks.
#   4. Log per-call cost/usage to stderr ONLY (per-call cost reporting). NOT
#      appended to the response — see the note at the log line.
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


async def _run_debuglog(log_path: str, question: str = "") -> str:
    """Runner for the debug-log capability.

    debuglog's input is a log REFERENCE, not a question (ADR-017), so it can't
    use _run_capability directly. It composes the (path, question) into the
    capability message via the SHARED helper (same framing the CLI and REST use)
    and then routes through _run_capability with mode='debuglog'.
    """
    message = compose_debuglog_input(log_path, question or None)
    return await _run_capability("debuglog", message)


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


@mcp.tool()
async def diagnose_debug_log(log_path: str, question: str = "") -> str:
    """Diagnose a Salesforce Apex debug log: identify what failed (or what ran)
    and explain the likely root cause, grounded in the metadata graph.

    Reads the log SERVER-SIDE, correlates the Apex units that executed (and any
    exception) to the dependency graph, and returns a structured root-cause
    analysis — what failed, where it sits in the graph, the likely cause, and
    what to check. The raw log is never sent to the model; only the structured
    correlation is (so a large log doesn't blow the context window).

    Use when you have a debug log from a failed or suspicious transaction and
    want to know which class/trigger is implicated and why (e.g. a DML exception
    on insert, an unexpected trigger recursion). If the log shows only
    Flow/Workflow automation, it will say the failure isn't in the Apex graph
    rather than invent an Apex cause.

    Arguments:
        log_path: path to the debug log file, readable by the SERVER process
                  (absolute, or relative to the backend dir).
        question: optional specific question to focus the analysis.
    """
    return await _run_debuglog(log_path, question)


# ------------------------------------------------------------------
# Entry point — stdio transport.
# ------------------------------------------------------------------
def main() -> None:
    """Launch the MCP server over stdio. Blocks until the host disconnects."""
    logger.info("Starting salesforce-metadata-graph MCP server (stdio)...")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
