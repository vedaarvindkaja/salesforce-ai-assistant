"""Graph builder — turns the flat metadata cache into a MetadataGraph.

Two passes over the org's cached metadata:
  1. NODES:  one Node per cached record (ApexClass, ApexTrigger).
  2. EDGES:  for each node, run the reference analyzer with the node's NAME
             as the identifier. Every record the analyzer returns references
             that node, so it becomes the SOURCE of a REFERENCES edge whose
             TARGET is the node.

Edge direction: source REFERENCES target  (source --REFERENCES--> target).
  what_does_X_depend_on  -> successors of X  (things X points to)
  what_depends_on_X      -> predecessors of X (things pointing to X)

ADR-009: edges are built by REUSING the ReferenceAnalyzer rather than
re-implementing matching in the builder. Keeps matching semantics
(word-boundary, case-insensitive — ADR-006/007) identical between the
graph and the standalone "what references X?" query. Cost is O(N^2) body
scans; fine at current scale (43 nodes), revisited with the Week 7
tokenizer. See NOTES.md.
"""
from __future__ import annotations

from app.intelligence.analyzer import ReferenceAnalyzer
from app.intelligence.graph.models import (
    Edge,
    EdgeType,
    MetadataGraph,
    Node,
    NodeType,
)
from app.intelligence.graph.storage import MetadataCache

# Metadata types the builder can turn into nodes today, mapped to their
# NodeType. Week 7 adds Object/Field here as extraction broadens; the rest of
# the builder is type-agnostic and won't need to change.
_METADATA_TYPE_TO_NODE_TYPE: dict[str, NodeType] = {
    "ApexClass": NodeType.APEX_CLASS,
    "ApexTrigger": NodeType.APEX_TRIGGER,
}

DEFAULT_NODE_TYPES: tuple[str, ...] = tuple(_METADATA_TYPE_TO_NODE_TYPE)

# Sentinel used when a record has no name-ish field. Such a node can't be used
# as a search identifier (matching "<unknown>" is meaningless), so it gets a
# node but is skipped during edge discovery.
_UNKNOWN_NAME = "<unknown>"


class GraphBuilder:
    """Builds a MetadataGraph from a MetadataCache for one org."""

    def __init__(
        self,
        cache: MetadataCache,
        analyzer: ReferenceAnalyzer | None = None,
    ) -> None:
        # Analyzer is injectable for testing; defaults to one over the same
        # cache for convenience (same DI pattern as the REST layer).
        self._cache = cache
        self._analyzer = analyzer or ReferenceAnalyzer(cache)

    async def build(
        self,
        *,
        org_key: str,
        node_types: tuple[str, ...] = DEFAULT_NODE_TYPES,
    ) -> MetadataGraph:
        graph = MetadataGraph()
        await self._add_nodes(graph, org_key=org_key, node_types=node_types)
        await self._add_reference_edges(graph, org_key=org_key, node_types=node_types)
        return graph

    async def _add_nodes(
        self, graph: MetadataGraph, *, org_key: str, node_types: tuple[str, ...]
    ) -> None:
        for metadata_type in node_types:
            node_type = _METADATA_TYPE_TO_NODE_TYPE.get(metadata_type)
            if node_type is None:
                # A type we can't model yet (e.g. a Week 8 type passed early).
                # Skip rather than guess — keeps the graph honest.
                continue
            records = await self._cache.get(org_key=org_key, metadata_type=metadata_type)
            for rec in records:
                graph.add_node(
                    Node(
                        id=rec["Id"],
                        name=rec.get("Name") or rec.get("DeveloperName") or _UNKNOWN_NAME,
                        node_type=node_type,
                        org_key=org_key,
                    )
                )

    async def _add_reference_edges(
        self, graph: MetadataGraph, *, org_key: str, node_types: tuple[str, ...]
    ) -> None:
        for node in graph.all_nodes():
            if node.name == _UNKNOWN_NAME:
                continue  # can't search for a sentinel; no edges discoverable
            report = await self._analyzer.find_references(
                org_key=org_key,
                identifier=node.name,
                metadata_types=node_types,  # scan scope == node scope
            )
            for ref in report.references:
                if ref.record_id == node.id:
                    continue  # self-reference (a class names itself in its decl)
                if graph.get_node(ref.record_id) is None:
                    continue  # defensive: source must be a tracked node
                graph.add_edge(
                    Edge(
                        source_id=ref.record_id,
                        target_id=node.id,
                        edge_type=EdgeType.REFERENCES,
                        attributes={
                            "line_numbers": ref.line_numbers,
                            "match_count": ref.match_count,
                        },
                    )
                )


# ============================================================
# APEX EQUIVALENT (for comparison)
# ============================================================
# Building a dependency map in Apex: query the cached rows, then for each
# pair decide whether one references the other. The self-edge guard and the
# "source must be a known node" check map directly.
#
#    public class GraphBuilder {
#
#        // Returns sourceId -> Set<targetId> ("source REFERENCES target")
#        public Map<Id, Set<Id>> build(List<String> nodeTypes) {
#            // 1. NODES: load every cached record of the wanted types.
#            List<Metadata_Cache__c> rows = [
#                SELECT Record_Id__c, Display_Name__c, Metadata_Type__c, Payload__c
#                FROM Metadata_Cache__c
#                WHERE Metadata_Type__c IN :nodeTypes
#            ];
#            Map<Id, Metadata_Cache__c> nodesById = new Map<Id, Metadata_Cache__c>();
#            for (Metadata_Cache__c r : rows) nodesById.put(r.Record_Id__c, r);
#
#            // 2. EDGES: for each target node, scan every body for its name.
#            Map<Id, Set<Id>> edges = new Map<Id, Set<Id>>();
#            for (Metadata_Cache__c target : rows) {
#                if (String.isBlank(target.Display_Name__c)) continue;  // sentinel skip
#                Pattern p = Pattern.compile(
#                    '\\b' + Pattern.quote(target.Display_Name__c) + '\\b',
#                    Pattern.CASE_INSENSITIVE);                          // ADR-007
#                for (Metadata_Cache__c source : rows) {
#                    if (source.Record_Id__c == target.Record_Id__c) continue; // self-edge
#                    if (p.matcher(source.Payload__c).find()) {
#                        if (!edges.containsKey(source.Record_Id__c))
#                            edges.put(source.Record_Id__c, new Set<Id>());
#                        edges.get(source.Record_Id__c).add(target.Record_Id__c);
#                    }
#                }
#            }
#            return edges;
#        }
#    }
#
# Concept mapping:
# - cache.get(metadata_type=...)         -> SOQL WHERE Metadata_Type__c IN :list
# - ReferenceAnalyzer reuse              -> inlined Pattern.matcher().find() loop
# - if ref.record_id == node.id: continue-> if source.Id == target.Id: continue
# - graph.get_node(id) is None guard     -> nodesById.containsKey(id) check
# - MetadataGraph (DiGraph)              -> Map<Id, Set<Id>> adjacency
# - async/await over aiosqlite           -> synchronous SOQL (no async in Apex)
#
# Note the O(N^2) double loop is identical in both — the Apex version makes the
# scaling cost visually obvious. ADR-009 accepts it at current scale.
# ============================================================
