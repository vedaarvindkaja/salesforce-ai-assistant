# No direct Apex equivalent — LLM system-prompt/orientation builder (orchestration plumbing)
"""System-prompt builder for the tool-pull orchestration model (ADR-014).

Under tool-pull (Option A), Claude is given a THIN standing context — its role,
how the graph is shaped, how to reason, and the graph's known blind spots — and
then pulls specifics through tools. This module builds exactly that standing
context. It does NOT retrieve or pre-load metadata contents; that would be the
pre-loaded model (Option B), deliberately deferred.

Orientation, not data: the prompt tells Claude the SHAPE of the org (counts by
type, what edge kinds mean, what the graph does and does NOT capture) so it
knows what it's querying — but every specific component name, dependency, and
source line comes through a tool call, never the system prompt.

If Option B is ever revived, the retrieval/compression machinery lands in a new
intelligence/context/ package; this builder stays as the orientation half.
"""
from __future__ import annotations

from app.intelligence.graph.models import GraphStats, MetadataGraph


def _format_inventory(stats: GraphStats) -> str:
    """'43 ApexClass, 8 Object, 6 Flow, 1 ApexTrigger' — type counts, no names."""
    if not stats.node_type_counts:
        return "no components (the graph is empty)"
    parts = [
        f"{count} {ntype}"
        for ntype, count in sorted(
            stats.node_type_counts.items(), key=lambda kv: (-kv[1], kv[0])
        )
    ]
    return ", ".join(parts)


def _format_edge_summary(stats: GraphStats) -> str:
    """'87 REFERENCES, 74 CALLS, 11 USES_OBJECT' — edge counts by type."""
    if not stats.edge_type_counts:
        return "no relationships"
    parts = [
        f"{count} {etype}"
        for etype, count in sorted(
            stats.edge_type_counts.items(), key=lambda kv: (-kv[1], kv[0])
        )
    ]
    return ", ".join(parts)


def build_system_prompt(graph: MetadataGraph) -> str:
    """Assemble the standing system prompt from a built graph.

    Includes live orientation (counts by node/edge type), edge semantics, how
    to reason with the tools, and the graph's known limitations — so Claude
    neither guesses nor overclaims completeness it doesn't have.
    """
    stats = graph.stats()
    inventory = _format_inventory(stats)
    edges = _format_edge_summary(stats)

    return f"""You are an AI assistant embedded in a Salesforce developer \
intelligence platform. You answer questions about a real Salesforce org by \
querying a metadata dependency graph through the tools provided.

THE GRAPH (current org snapshot)
The graph holds {stats.node_count} components and {stats.edge_count} \
relationships, built from this org's actual metadata.
- Components by type: {inventory}
- Relationships by type: {edges}

WHAT THE EDGES MEAN
- REFERENCES: one component names another (string-level reference).
- CALLS: an Apex method call, OR a Flow invoking Apex, OR a Flow calling a \
subflow. The specific mechanism is reported as a label (method call / Flow \
action / subflow).
- USES_OBJECT: an Apex class queries/DMLs an Object (SOQL/DML), OR a Flow is \
triggered by an Object. Reported as 'SOQL/DML query' or 'Flow trigger'.

HOW TO REASON
- Use the tools to look up real metadata. Never invent component names, \
dependencies, or source — if you are unsure a component exists, call \
find_by_name first.
- When you describe a dependency, say HOW it works (the mechanism label), not \
just that it exists. That distinction is the product's whole value.
- find_dependencies = what a component USES (outward). find_references_to = \
what USES a component (inward, 'what breaks if I change this'). Do not confuse \
the two directions.
- Use get_source when you need to read the actual Apex body or Flow XML, not \
just its relationships.
- Be specific and developer-focused. Name the actual classes, objects, and \
flows involved.

KNOWN LIMITATIONS — do not overclaim
- The graph captures Apex (classes, triggers), derived Objects, and Flows. It \
does NOT yet model fields, validation rules, permission sets, or layouts.
- Object dependencies are tracked at the OBJECT level, not the field level.
- For Flows, only the TRIGGERING object is edged; record operations inside a \
flow (recordLookups / recordCreates / recordUpdates) are NOT yet captured, so a \
flow may depend on objects the graph does not show.
- Treat dependency lists as complete only within these bounds. If a question \
reaches beyond them, say so rather than guessing."""
