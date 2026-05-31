"""Shared name resolution and display formatting for the metadata graph.

Extracted from cli.py (ADR-013) so both the CLI and the orchestration tool
layer resolve human-typed names and format nodes/edges identically. The label
maps in particular MUST be single-sourced: the CLI demo and Claude's tool
output have to describe the same edge the same way, or the product looks
inconsistent.

Dependency direction: this module lives in the graph layer and depends only on
graph models. Both interfaces/cli.py and intelligence/orchestration/ import
DOWN into it. Orchestration must never import from interfaces/ (a UI layer).
"""
from __future__ import annotations

from app.intelligence.graph.models import Edge, EdgeType, MetadataGraph, Node
from app.intelligence.graph.query import QueryEngine

# Human-readable labels keyed by the edge's `via` attribute. The `via` is more
# specific than the edge type — a CALLS edge can be an Apex method call, a Flow
# invoking Apex, or a Flow calling a subflow. When an edge carries a `via`, it
# drives the label; otherwise fall back to EDGE_LABEL by type.
VIA_LABEL: dict[str, str] = {
    "soql": "SOQL/DML query",
    "flow_trigger": "Flow trigger",
    "flow_action": "Flow action",
    "subflow": "subflow",
}

# Fallback labels keyed by edge type, for edges with no `via` attribute
# (Apex→Apex method calls and string-scan REFERENCES).
EDGE_LABEL: dict[str, str] = {
    "USES_OBJECT": "SOQL/DML",
    "CALLS": "method call",
    "REFERENCES": "name reference",
}


def resolve_one(engine: QueryEngine, name: str) -> tuple[Node | None, str | None]:
    """Resolve a name to exactly one Node. Returns (node, None) on success or
    (None, error_message) when the name is missing or ambiguous.

    Strategy: exact (case-insensitive) match wins; otherwise a single substring
    match auto-resolves; otherwise report the ambiguity.
    """
    exact = engine.find_by_name(name, exact=True)
    if len(exact) == 1:
        return exact[0], None
    if len(exact) > 1:  # rare for class names, but be explicit
        names = ", ".join(n.name for n in exact)
        return None, f"'{name}' matches several nodes exactly: {names}"

    partial = engine.find_by_name(name)
    if len(partial) == 1:
        return partial[0], None
    if not partial:
        return None, f"No metadata named '{name}'. Try a partial-name search."
    shown = ", ".join(n.name for n in partial[:10])
    more = "" if len(partial) <= 10 else f" (+{len(partial) - 10} more)"
    return None, (
        f"'{name}' is ambiguous — matches {len(partial)}: {shown}{more}. "
        f"Use the exact name."
    )


def fmt_node(n: Node) -> str:
    """One-line display form: 'Name (NodeType)'."""
    return f"{n.name} ({n.node_type.value})"


def edge_relation_label(edge: Edge) -> str:
    """Human label for an edge, preferring the `via` attribute over edge type.

    This is the single source of truth for how a relationship is described,
    shared by the CLI impact command and the analyze_impact tool.
    """
    via = edge.attributes.get("via")
    if via and via in VIA_LABEL:
        return VIA_LABEL[via]
    return EDGE_LABEL.get(edge.edge_type.value, edge.edge_type.value)


def edge_method_detail(edge: Edge) -> str:
    """Method-name suffix for Apex→Apex method calls, e.g. ' (run())'.

    Only applies to CALLS edges with no `via` and a `method` attribute — that
    combination uniquely identifies a direct Apex method call (Flow-sourced
    CALLS edges carry a `via` and are excluded).
    """
    via = edge.attributes.get("via")
    if edge.edge_type == EdgeType.CALLS and not via and edge.attributes.get("method"):
        return f" ({edge.attributes['method']}())"
    return ""


# ============================================================
# APEX EQUIVALENT (for comparison)
# ============================================================
# Name resolution is the same problem as resolving a user-typed object/field
# name to its API name or Id — exact match first, then a unique partial, else
# ambiguity. The Apex analog is querying by DeveloperName with a fallback LIKE.
#
#    public class GraphNaming {
#        // resolve_one: exact DeveloperName, else unique LIKE, else ambiguous
#        public static ResolveResult resolveOne(String name) {
#            List<SObject> exact = [
#                SELECT Id, DeveloperName FROM Node__c
#                WHERE DeveloperName = :name        // case-insensitive in SOQL
#            ];
#            if (exact.size() == 1) return ResolveResult.ok(exact[0]);
#            if (exact.size() > 1)  return ResolveResult.err('matches several');
#
#            List<SObject> partial = [
#                SELECT Id, DeveloperName FROM Node__c
#                WHERE DeveloperName LIKE :('%' + name + '%')
#            ];
#            if (partial.size() == 1) return ResolveResult.ok(partial[0]);
#            if (partial.isEmpty())   return ResolveResult.err('no metadata named');
#            return ResolveResult.err('ambiguous');
#        }
#    }
#
# Concept mapping:
# - find_by_name(name, exact=True)        → SOQL WHERE DeveloperName = :name
# - find_by_name(name)  (substring)       → SOQL WHERE DeveloperName LIKE :('%'+name+'%')
# - tuple (Node | None, str | None)       → a ResolveResult wrapper (Apex has no tuples)
# - VIA_LABEL / EDGE_LABEL dicts          → Map<String,String> constants or Custom Metadata
# - edge_relation_label(edge)             → a switch on via, falling back to edgeType
# ============================================================
