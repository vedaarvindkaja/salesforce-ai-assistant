# No direct Apex equivalent — debug-log <-> metadata-graph correlation.
"""Correlate parsed debug-log events to the metadata graph (Week 12, Day 4).

This is the debug-log capability's differentiator: it takes the structured
events from the pure parser and joins the Apex units that executed (and any
exception) to the dependency graph, producing the evidence Claude reasons over.

Deliberately NOT pure-text and NOT graph-mutating: text->events is the parser's
job; reasoning is Claude's job. This module is the deterministic JOIN in the
middle — log facts + graph topology -> a structured, label-bearing summary.

Correlation key (ADR-013 consistency): resolve each apex_unit by NAME via the
shared resolve_one, exactly as every other tool does; fall back to the
ApexClass/Trigger Id the parser also captured (15-char normalized) only when the
name doesn't resolve. No new matching layer.

Output is lightly-structured prose in the same idiom as analyze_impact's handler
(edge labels via naming.py), so it drops straight into the tool-pull model.
"""
from __future__ import annotations

from pathlib import Path

from app.intelligence.graph.naming import (
    edge_method_detail,
    edge_relation_label,
    fmt_node,
    resolve_one,
)


def resolve_log_path(raw: str) -> Path:
    """Resolve a debug-log path cwd-independently.

    Absolute paths are used as-is. Relative paths are tried against the current
    working dir first, then against the backend root (resolved from this file),
    so an MCP host launching from System32 still finds a backend-relative path
    (the Week-11 cwd lesson). Returns the first existing candidate, else the
    cwd-joined path so a 'not found' message shows a sensible location.
    """
    p = Path(raw)
    if p.is_absolute():
        return p
    cwd_candidate = Path.cwd() / p
    backend_root = Path(__file__).resolve().parents[3]  # debuglog->intelligence->app->backend
    for candidate in (cwd_candidate, backend_root / p):
        if candidate.exists():
            return candidate
    return cwd_candidate


def correlate_log_to_graph(result, engine, graph) -> str:
    """Join parsed log events to the graph and return a structured summary.

    Args:
        result: a DebugLogParseResult from the parser.
        engine:  QueryEngine (for resolve_one + edge queries).
        graph:   MetadataGraph (for node lookup + the id index).

    Returns lightly-structured prose: the exception (if any), the Apex units that
    executed and whether each is a graph node, and — for each in-graph unit — its
    direct dependencies and dependents WITH mechanism labels. Claude reasons over
    this; it never sees the raw log.
    """
    lines: list[str] = []

    # Id tie-breaker index (name-first, id-fallback per Decision 2). 15-char
    # normalized because logs carry 15-char ids and the cache stores 18.
    id_index = {n.id[:15]: n for n in graph.all_nodes()}
    unit_ids: dict[str, str] = {}
    for e in result.events:
        if e.apex_unit and e.apex_class_id:
            unit_ids.setdefault(e.apex_unit, e.apex_class_id)

    # --- 1. Exception / outcome ---
    excs = result.by_type("EXCEPTION_THROWN")
    fatals = result.by_type("FATAL_ERROR")
    if excs or fatals:
        lines.append("EXCEPTION")
        for e in excs:
            msg = e.fields[-1] if e.fields else "(no detail)"
            loc = f" [line {e.code_line}]" if e.code_line else ""
            lines.append(f"- thrown{loc}: {msg}")
        for f in fatals:
            msg = f.fields[-1] if f.fields else "(no detail)"
            lines.append(f"- fatal: {msg}")
            if f.detail:
                lines.append(f"  origin: {f.detail.splitlines()[0]}")
    else:
        lines.append("OUTCOME: completed without an unhandled exception.")

    # --- 2. Apex units executed, correlated to graph nodes ---
    units = sorted(result.apex_units())
    lines.append("")
    if not units:
        lines.append(
            "APEX UNITS: none executed (no METHOD_ENTRY or Apex-trigger CODE_UNIT). "
            "Automation in this log was Flow/Workflow only — nothing to correlate "
            "to the Apex graph."
        )
        return "\n".join(lines)

    resolved: list[tuple[str, object]] = []
    lines.append(f"APEX UNITS EXECUTED ({len(units)}):")
    for u in units:
        node, _err = resolve_one(engine, u)
        if node is None:
            cid = unit_ids.get(u)
            if cid:
                node = id_index.get(cid[:15])
        if node is not None:
            resolved.append((u, node))
            lines.append(f"- {u} -> {fmt_node(node)} [in graph]")
        else:
            lines.append(
                f"- {u} [not in graph: managed package, System, or out of scope]"
            )

    # --- 3. Direct graph context for each in-graph unit (labelled edges) ---
    for u, node in resolved:
        lines.append("")
        lines.append(f"GRAPH CONTEXT — {fmt_node(node)}")
        out_edges = engine.outgoing_edges(node.id)
        if out_edges:
            lines.append("  depends on:")
            for e in out_edges:
                tgt = graph.get_node(e.target_id)
                label = fmt_node(tgt) if tgt else e.target_id
                lines.append(
                    f"  - {label} via {edge_relation_label(e)}{edge_method_detail(e)}"
                )
        in_edges = engine.incoming_edges(node.id)
        if in_edges:
            lines.append("  depended on by:")
            for e in in_edges:
                src = graph.get_node(e.source_id)
                label = fmt_node(src) if src else e.source_id
                lines.append(
                    f"  - {label} via {edge_relation_label(e)}{edge_method_detail(e)}"
                )
        if not out_edges and not in_edges:
            lines.append("  (no graph edges — isolated node)")

    return "\n".join(lines)
