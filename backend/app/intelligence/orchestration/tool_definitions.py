"""Tool definitions for the orchestration layer — the tools Claude can call to
answer questions about the Salesforce metadata graph.

Two families:
  GRAPH-QUERY tools (find_dependencies, find_references_to, analyze_impact,
    find_by_name, graph_health, analyze_debug_log) — thin async wrappers over
    QueryEngine (+ the debug-log parser/correlator). Need only an in-memory
    engine + graph.
  CONTENT-RETRIEVAL tool (get_source) — reads the raw Apex Body or Flow XML
    from the cache. Needs the MetadataCache + org_key.

Structure:
  TOOL_SCHEMAS   — the full catalogue of schemas Claude can see (7 tools).
  build_tools()  — binds async handlers to a live engine + graph, and (when a
                   cache + org_key are supplied) the get_source handler too.
                   Returns (schemas, handler_map). Without a cache it returns
                   the 6 graph-query tools only — the graph tools genuinely
                   don't need a cache, so the signature reflects that.

Handlers reuse intelligence/graph/naming.py for resolution + labels (ADR-013).
Returns are lightly-structured text, not JSON (tool-pull model — Claude reads
these to reason; prose preserves name/type/via-label for fewer tokens).
"""
from __future__ import annotations

from app.intelligence.debuglog.correlate import correlate_log_to_graph, resolve_log_path
from app.intelligence.debuglog.parser import parse_debug_log_file
from app.intelligence.graph.models import MetadataGraph, NodeType
from app.intelligence.graph.naming import (
    edge_method_detail,
    edge_relation_label,
    fmt_node,
    resolve_one,
)
from app.intelligence.graph.query import QueryEngine
from app.intelligence.graph.storage import MetadataCache

# Soft cap on returned source length. A guardrail against a pathological
# large Flow/class blowing the context window in one tool call — NOT a
# token-budget strategy (that's retrieval/compression, Day 5). Generous
# enough that ordinary classes and flows return whole.
_MAX_SOURCE_CHARS = 12_000


# ------------------------------------------------------------------
# Graph-query schemas (no cache needed)
# ------------------------------------------------------------------

_GRAPH_QUERY_SCHEMAS: list[dict] = [
    {
        "name": "find_dependencies",
        "description": (
            "List what a given metadata component DEPENDS ON — the things it "
            "uses or points at (the Apex classes it calls, the objects it "
            "queries, the flows it invokes). Direction: OUTWARD from the named "
            "component. Use this to answer 'what does X rely on?'. For the "
            "opposite direction ('what relies on X?'), use find_references_to. "
            "Set transitive=true for the full downstream chain, not just direct."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Metadata name (e.g. 'AccountService', "
                                   "'Opportunity'). Case-insensitive; a unique "
                                   "partial name resolves automatically.",
                },
                "transitive": {
                    "type": "boolean",
                    "description": "If true, return the full chain of "
                                   "dependencies, not just direct ones. "
                                   "Default false.",
                },
            },
            "required": ["name"],
        },
    },
    {
        "name": "find_references_to",
        "description": (
            "List what DEPENDS ON a given metadata component — the things that "
            "use or point at it. Direction: INWARD toward the named component. "
            "This answers 'what breaks if I change X?' and 'what relies on X?'. "
            "For the opposite direction ('what does X rely on?'), use "
            "find_dependencies. Set transitive=true for the full upstream blast "
            "radius (everything that reaches X through any chain)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Metadata name. Case-insensitive; a unique "
                                   "partial name resolves automatically.",
                },
                "transitive": {
                    "type": "boolean",
                    "description": "If true, return the full upstream blast "
                                   "radius, not just direct dependents. "
                                   "Default false.",
                },
            },
            "required": ["name"],
        },
    },
    {
        "name": "analyze_impact",
        "description": (
            "Show everything that touches a component AND HOW each relationship "
            "works — labeled by mechanism: SOQL/DML query, Apex method call, "
            "Flow trigger, Flow action, subflow, or name reference. This is the "
            "richest view: prefer it when the user wants to understand the "
            "nature of the dependencies, not just a list. Especially useful on "
            "Object nodes ('what touches Opportunity, and how?')."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Metadata name. Case-insensitive; a unique "
                                   "partial name resolves automatically.",
                },
            },
            "required": ["name"],
        },
    },
    {
        "name": "find_by_name",
        "description": (
            "Search the graph for components whose name matches a query "
            "(case-insensitive substring). Use this to discover exact names "
            "before calling another tool, or when the user's term is vague and "
            "you need to see what exists. Returns each match with its type "
            "(ApexClass, ApexTrigger, Object, Flow)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Substring to search for in component names.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "graph_health",
        "description": (
            "Surface structural health signals across the whole graph. Two "
            "checks: 'orphaned' (components with no references in or out — dead "
            "code or UI-bound), and 'never_referenced' (components nothing "
            "points at, but which point at others — often metadata-wired entry "
            "points like flow-invoked Apex). Use when the user asks about dead "
            "code, unused components, or org health."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "check": {
                    "type": "string",
                    "enum": ["orphaned", "never_referenced", "both"],
                    "description": "Which health check to run. Default 'both'.",
                },
                "exclude_tests": {
                    "type": "boolean",
                    "description": "For never_referenced: omit @isTest classes "
                                   "(they're structurally never-referenced). "
                                   "Default false.",
                },
            },
            "required": [],
        },
    },
    {
        "name": "analyze_debug_log",
        "description": (
            "Parse a Salesforce Apex debug log and correlate the Apex units that "
            "executed (and any exception) to the metadata graph. Returns the "
            "exception (type/message/line) if the run failed, the distinct Apex "
            "classes/triggers that ran and which are graph nodes, and — for each "
            "in-graph unit — its direct dependencies and dependents WITH "
            "mechanism labels. Call this FIRST when given a debug log; then use "
            "the graph tools (find_dependencies, analyze_impact) to drill into a "
            "suspect unit's wider blast radius. Input is a server-readable path."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "log_path": {
                    "type": "string",
                    "description": "Path to the debug log file on the server "
                                   "(absolute, or relative to the backend dir).",
                },
            },
            "required": ["log_path"],
        },
    },
]

# ------------------------------------------------------------------
# Content-retrieval schema (needs cache)
# ------------------------------------------------------------------

_CONTENT_SCHEMAS: list[dict] = [
    {
        "name": "get_source",
        "description": (
            "Retrieve the raw source of a component: the Apex body for a class "
            "or trigger, or the Flow XML for a flow. Use this AFTER locating a "
            "component (e.g. via analyze_impact or find_by_name) when you need "
            "to read or reason about the actual code/definition — not just its "
            "dependencies. Works for Apex classes, Apex triggers, and Flows. "
            "Objects have no source (they're derived from references), so this "
            "will say so for an Object name."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Component name. Case-insensitive; a unique "
                                   "partial name resolves automatically.",
                },
            },
            "required": ["name"],
        },
    },
]

# The full catalogue Claude could see. build_tools() returns the subset it can
# actually serve given the dependencies passed in.
TOOL_SCHEMAS: list[dict] = _GRAPH_QUERY_SCHEMAS + _CONTENT_SCHEMAS


# ------------------------------------------------------------------
# Handler factory
# ------------------------------------------------------------------

def build_tools(
    engine: QueryEngine,
    graph: MetadataGraph,
    cache: MetadataCache | None = None,
    org_key: str | None = None,
) -> tuple[list[dict], dict]:
    """Bind async handlers to a live engine + graph (+ optional cache).

    Returns (schemas, handler_map). Register each handler with
    ClaudeClient.register_tool(name, handler), and pass schemas to ask().

    The six graph-query tools are always built. get_source is added only when
    BOTH cache and org_key are supplied — it reads raw source from the cache,
    which the graph tools don't need. Handlers are async to satisfy the
    client's ToolHandler contract.
    """

    async def find_dependencies(inp: dict) -> str:
        node, err = resolve_one(engine, inp["name"])
        if err:
            return err
        transitive = bool(inp.get("transitive", False))
        kind = "transitive" if transitive else "direct"

        if transitive:
            # Transitive: node-list only (edge detail across multi-hop chains
            # is noise — the mechanism label belongs on the direct hop).
            deps = engine.what_does_it_depend_on(node.id, transitive=True)
            if not deps:
                return f"{fmt_node(node)} depends on nothing in the graph."
            head = f"{fmt_node(node)} has {len(deps)} {kind} dependenc(ies):"
            return "\n".join([head, *(f"- {fmt_node(n)}" for n in deps)])
        else:
            # Direct: use edge-level detail so Claude knows the mechanism,
            # not just the target. Fixes the over-narration root cause (Week 10
            # Refinement #10) — previously stripped via-label forced guessing.
            edges = engine.outgoing_edges(node.id)
            if not edges:
                return f"{fmt_node(node)} depends on nothing in the graph."
            head = f"{fmt_node(node)} has {len(edges)} {kind} dependenc(ies):"
            lines = [head]
            for e in edges:
                tgt = graph.get_node(e.target_id)
                tgt_label = fmt_node(tgt) if tgt else e.target_id
                relation = edge_relation_label(e)
                detail = edge_method_detail(e)
                lines.append(f"- {tgt_label} via {relation}{detail}")
            return "\n".join(lines)

    async def find_references_to(inp: dict) -> str:
        node, err = resolve_one(engine, inp["name"])
        if err:
            return err
        transitive = bool(inp.get("transitive", False))
        deps = engine.what_depends_on(node.id, transitive=transitive)
        kind = "transitive" if transitive else "direct"
        if not deps:
            return f"Nothing depends on {fmt_node(node)}."
        head = f"{len(deps)} {kind} dependent(s) of {fmt_node(node)}:"
        return "\n".join([head, *(f"- {fmt_node(n)}" for n in deps)])

    async def analyze_impact(inp: dict) -> str:
        node, err = resolve_one(engine, inp["name"])
        if err:
            return err
        edges = engine.incoming_edges(node.id)
        if not edges:
            return f"Nothing touches {fmt_node(node)}."
        head = f"{len(edges)} reference(s) touch {fmt_node(node)}:"
        lines = [head]
        for e in edges:
            src = graph.get_node(e.source_id)
            src_label = fmt_node(src) if src else e.source_id
            relation = edge_relation_label(e)
            detail = edge_method_detail(e)
            lines.append(f"- {src_label} via {relation}{detail}")
        return "\n".join(lines)

    async def find_by_name(inp: dict) -> str:
        matches = engine.find_by_name(inp["query"])
        if not matches:
            return f"No components match '{inp['query']}'."
        head = f"{len(matches)} match(es) for '{inp['query']}':"
        return "\n".join([head, *(f"- {fmt_node(n)}" for n in matches)])

    async def graph_health(inp: dict) -> str:
        check = inp.get("check", "both")
        exclude_tests = bool(inp.get("exclude_tests", False))
        sections: list[str] = []

        if check in ("orphaned", "both"):
            orphans = engine.find_orphaned()
            if orphans:
                sections.append(
                    f"{len(orphans)} orphaned (no references in or out):\n"
                    + "\n".join(f"- {fmt_node(n)}" for n in orphans)
                )
            else:
                sections.append("No orphaned components.")

        if check in ("never_referenced", "both"):
            never = engine.find_never_referenced(exclude_tests=exclude_tests)
            note = " (tests excluded)" if exclude_tests else ""
            if never:
                sections.append(
                    f"{len(never)} never-referenced{note} "
                    f"(nothing points at them, but they point at others):\n"
                    + "\n".join(f"- {fmt_node(n)}" for n in never)
                )
            else:
                sections.append(f"No never-referenced components{note}.")

        return "\n\n".join(sections)

    async def analyze_debug_log(inp: dict) -> str:
        # Read + parse the log (pure parser), then correlate to the graph.
        # Claude never sees the raw log — only the structured correlation.
        path = resolve_log_path(inp.get("log_path", ""))
        if not path.exists():
            return f"Debug log not found at {path}."
        result = parse_debug_log_file(path)
        return correlate_log_to_graph(result, engine, graph)

    handler_map = {
        "find_dependencies": find_dependencies,
        "find_references_to": find_references_to,
        "analyze_impact": analyze_impact,
        "find_by_name": find_by_name,
        "graph_health": graph_health,
        "analyze_debug_log": analyze_debug_log,
    }
    schemas = list(_GRAPH_QUERY_SCHEMAS)

    # get_source is only buildable with a cache to read from.
    if cache is not None and org_key is not None:

        def _truncate(text: str) -> str:
            if len(text) <= _MAX_SOURCE_CHARS:
                return text
            return (
                text[:_MAX_SOURCE_CHARS]
                + f"\n\n[truncated — source exceeds {_MAX_SOURCE_CHARS} chars; "
                  "use analyze_impact/find_dependencies for structure]"
            )

        async def get_source(inp: dict) -> str:
            node, err = resolve_one(engine, inp["name"])
            if err:
                return err

            # Apex class / trigger: node.id IS the cache record_id.
            if node.node_type in (NodeType.APEX_CLASS, NodeType.APEX_TRIGGER):
                rec = await cache.get_one(
                    org_key=org_key,
                    metadata_type=node.node_type.value,
                    record_id=node.id,
                )
                body = rec.get("Body") if rec else None
                if not body:
                    return f"No cached source for {fmt_node(node)}."
                return f"Source of {fmt_node(node)}:\n\n{_truncate(body)}"

            # Flow: node.id is synthetic (flow:<name>), so match by name.
            if node.node_type == NodeType.FLOW:
                flows = await cache.get(org_key=org_key, metadata_type="Flow")
                target = node.name.casefold()
                match = next(
                    (r for r in flows
                     if (r.get("DeveloperName") or "").casefold() == target),
                    None,
                )
                xml = match.get("xml") if match else None
                if not xml:
                    return f"No cached XML for {fmt_node(node)}."
                return f"Flow XML of {fmt_node(node)}:\n\n{_truncate(xml)}"

            # Object: derived node, no source artifact (ADR-010).
            if node.node_type == NodeType.OBJECT:
                return (
                    f"{fmt_node(node)} is a derived Object node — it has no "
                    "source to retrieve. Objects are tracked at the reference "
                    "level (what queries/uses them), not extracted as source. "
                    "Use analyze_impact to see what touches it."
                )

            return f"No source retrieval defined for {fmt_node(node)}."

        handler_map["get_source"] = get_source
        schemas = schemas + _CONTENT_SCHEMAS

    return schemas, handler_map
