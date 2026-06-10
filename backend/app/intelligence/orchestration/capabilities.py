# No direct Apex equivalent — capability wiring (orchestration layer, ADR-001).
"""Capability definitions and per-mode client wiring.

This is the single source of truth for WHAT each capability is:
  - which system-prompt builder it uses, and
  - which subset of tools Claude may see in that mode.

Both AI interfaces consume this module:
  - ask_cli.py  (the CLI — streaming, prints to stdout)
  - mcp_server/server.py  (MCP transport — collected, returns one string)
  - rest_api  (the REST capability routes — streaming over SSE)

Extracting this here (rather than leaving it inlined in ask_cli) keeps the
capability definitions in ONE place, so a change to a mode's tool subset
propagates to every interface automatically. Same discipline as ADR-013's
naming.py: shared meaning lives in the layer below the interfaces, not in any
one interface. The ROADMAP's target structure anticipated this module
(orchestration/capabilities.py — "The 5 capabilities").

It does NOT load the graph — each interface bootstraps the graph its own way
(the CLI rebuilds per invocation; the long-lived MCP/REST servers cache it) and
passes the live (engine, graph, cache, org_key) in.
"""
from __future__ import annotations

from collections.abc import Callable

from app.intelligence.graph.models import MetadataGraph
from app.intelligence.graph.query import QueryEngine
from app.intelligence.graph.storage import MetadataCache
from app.intelligence.orchestration.claude_client import ClaudeClient, ToolHandler
from app.intelligence.orchestration.system_prompt import (
    build_apex_prompt,
    build_debuglog_prompt,
    build_impact_prompt,
    build_soql_prompt,
    build_system_prompt,
)
from app.intelligence.orchestration.tool_definitions import build_tools

# ------------------------------------------------------------------
# Tool subsets — what Claude can see per capability mode.
# impact excludes get_source: topology is sufficient; source reading
# adds cost with no benefit for blast-radius analysis.
# debuglog adds analyze_debug_log to the graph-only set; get_source is
# excluded for now (Week 12 Day 4 decision — log evidence + topology first,
# flip only if an eval fails specifically because root-cause needed source).
# ------------------------------------------------------------------
_ALL_TOOLS = {
    "find_dependencies", "find_references_to", "analyze_impact",
    "find_by_name", "graph_health", "get_source",
}
_GRAPH_ONLY = _ALL_TOOLS - {"get_source"}
_DEBUGLOG_TOOLS = _GRAPH_ONLY | {"analyze_debug_log"}

# Registry: mode -> (prompt_builder, allowed_tool_names)
# Adding a new capability = one new entry here + a new builder in system_prompt.py.
CAPABILITY_REGISTRY: dict[str, tuple] = {
    "qa":       (build_system_prompt,   _ALL_TOOLS),
    "apex":     (build_apex_prompt,     _ALL_TOOLS),
    "soql":     (build_soql_prompt,     _ALL_TOOLS),
    "impact":   (build_impact_prompt,   _GRAPH_ONLY),
    "debuglog": (build_debuglog_prompt, _DEBUGLOG_TOOLS),
}

VALID_MODES = list(CAPABILITY_REGISTRY.keys())

# A handler wrapper takes (tool_name, handler) and returns a (possibly wrapped)
# handler — the hook each interface uses to add its own observability
# (the CLI announces on stderr; the MCP server logs internal tool calls).
HandlerWrapper = Callable[[str, ToolHandler], ToolHandler]


def build_capability_client(
    mode: str,
    engine: QueryEngine,
    graph: MetadataGraph,
    cache: MetadataCache | None,
    org_key: str | None,
    *,
    handler_wrapper: HandlerWrapper | None = None,
) -> tuple[ClaudeClient, list[dict]]:
    """Build a ClaudeClient configured for `mode`, plus the tool schemas to pass
    to ask()/ask_collected().

    Steps (the shared core of the old ask_cli._ask flow):
      1. Look up the mode's (prompt_builder, allowed_tools).
      2. Build the system prompt from the live graph.
      3. Build all tool schemas + handlers, then subset to allowed_tools.
      4. Construct the client and register each (optionally wrapped) handler.

    Returns (client, schemas). The caller decides how to run it: ask() to
    stream, or ask_collected() for a single string. Cost is on client.session
    after the run.

    Raises ValueError on an unknown mode (callers translate as they see fit —
    the CLI's argparse already guards the modes; the MCP tools pass fixed modes).
    """
    if mode not in CAPABILITY_REGISTRY:
        raise ValueError(
            f"Unknown mode {mode!r}. Valid modes: {', '.join(VALID_MODES)}"
        )

    prompt_builder, allowed_tools = CAPABILITY_REGISTRY[mode]
    system_prompt = prompt_builder(graph)

    all_schemas, all_handlers = build_tools(engine, graph, cache, org_key)
    schemas = [s for s in all_schemas if s["name"] in allowed_tools]
    handlers = {n: h for n, h in all_handlers.items() if n in allowed_tools}

    client = ClaudeClient(system_prompt=system_prompt)
    for name, handler in handlers.items():
        client.register_tool(
            name,
            handler_wrapper(name, handler) if handler_wrapper else handler,
        )
    return client, schemas


def compose_debuglog_input(log_path: str, question: str | None = None) -> str:
    """Compose the user message for the debuglog capability from a log reference.

    The other four capabilities take a {question} straight through to ask();
    debuglog instead takes a log REFERENCE (ADR-017). This is the SINGLE place
    that turns a (log_path, optional question) into the message Claude sees, so
    the CLI, MCP server, and REST route don't each reinvent the framing —
    same single-source discipline as CAPABILITY_REGISTRY above.

    The debuglog system prompt instructs Claude to call analyze_debug_log with
    the provided path FIRST; this message is what hands it that path. The path
    is embedded verbatim — server-side resolution (cwd-independent) happens in
    the tool handler (resolve_log_path), not here.
    """
    base = f"Analyze the Salesforce debug log at this path: {log_path}"
    if question:
        return f"{base}\n\nSpecific question to focus on: {question}"
    return base
