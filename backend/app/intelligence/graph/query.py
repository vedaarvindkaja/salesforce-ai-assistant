# ============================================================
# PYTHON CODE
# ============================================================
"""Graph query engine — domain questions answered over the in-memory graph.

Synchronous by design: the graph lives in memory (the builder already paid
the async SQLite cost), so queries need no await and return instantly.

Vocabulary (edge semantics: source REFERENCES/CALLS/USES target, source --> target):
  what_depends_on(X)        -> who points at X         (predecessors / ancestors)
  what_does_it_depend_on(X) -> what X points at        (successors / descendants)
  incoming_edges(X, type?)  -> the Edge objects pointing at X (for impact view)
  find_path(A, B)           -> shortest A-->B route as edges
  find_by_name(q)           -> nodes whose name matches q (case-insensitive)
  find_orphaned()           -> in==0 AND out==0  (dead / UI-bound)
  find_never_referenced()   -> in==0 AND out>0   (metadata-wired)
                               exclude_tests=True filters @isTest classes

Transitive traversal uses raw networkx via the ADR-008 escape hatch.
ADR-011: the underlying graph is a MultiDiGraph, so find_path picks one
edge per hop (lowest key) when parallel edges exist between two nodes,
and incoming_edges returns every parallel edge separately.
"""
from __future__ import annotations

import networkx as nx

from app.intelligence.graph.models import Edge, EdgeType, MetadataGraph, Node


class QueryEngine:
    """Answers dependency questions over a built MetadataGraph."""

    def __init__(self, graph: MetadataGraph) -> None:
        self._graph = graph
        # Sanctioned escape hatch (ADR-008). MultiDiGraph since ADR-011.
        self._nx: nx.MultiDiGraph = graph._graph

    # ------------------------------------------------------------------
    # Dependency direction
    # ------------------------------------------------------------------

    def what_depends_on(self, node_id: str, *, transitive: bool = False) -> list[Node]:
        """Nodes that point at node_id. transitive=True returns the full
        blast radius (everything that reaches node_id through any chain)."""
        if node_id not in self._nx:
            return []
        ids = (
            nx.ancestors(self._nx, node_id)
            if transitive
            else self._nx.predecessors(node_id)
        )
        return self._nodes_for(ids)

    def what_does_it_depend_on(
        self, node_id: str, *, transitive: bool = False
    ) -> list[Node]:
        """Nodes node_id points at. transitive=True returns everything
        node_id reaches through any chain."""
        if node_id not in self._nx:
            return []
        ids = (
            nx.descendants(self._nx, node_id)
            if transitive
            else self._nx.successors(node_id)
        )
        return self._nodes_for(ids)

    # ------------------------------------------------------------------
    # Edge-level queries (for impact view — edge detail matters)
    # ------------------------------------------------------------------

    def incoming_edges(
        self, node_id: str, *, edge_type: EdgeType | None = None
    ) -> list[Edge]:
        """Return the Edge objects pointing AT node_id (in-edges).

        Unlike what_depends_on (which returns deduped Nodes), this keeps the
        edge metadata — edge_type and attributes like via="soql" or
        method="run" — so callers can show HOW the dependency exists.

        MultiDiGraph (ADR-011): every parallel in-edge is returned separately.
        A class that both CALLS and REFERENCES node_id yields two edges.

        Args:
            node_id: target node whose incoming edges we want.
            edge_type: if given, only edges of this type are returned.

        Returns:
            List of Edge objects, sorted by (source name, edge type) for
            deterministic output. Empty if node missing or no matching edges.
        """
        if node_id not in self._nx:
            return []

        edges: list[Edge] = []
        # in_edges with keys+data on a MultiDiGraph: (src, tgt, key, data)
        for src, _tgt, _key, data in self._nx.in_edges(node_id, keys=True, data=True):
            edge = Edge(**data)
            if edge_type is not None and edge.edge_type != edge_type:
                continue
            edges.append(edge)

        def _sort_key(e: Edge) -> tuple[str, str]:
            src_node = self._graph.get_node(e.source_id)
            src_name = src_node.name if src_node else e.source_id
            return (src_name.casefold(), e.edge_type.value)

        return sorted(edges, key=_sort_key)
    
    def outgoing_edges(
    self, node_id: str, *, edge_type: EdgeType | None = None
    ) -> list[Edge]:
        """Return the Edge objects pointing OUT FROM node_id (out-edges).

        The outward mirror of incoming_edges. Returns edge metadata — via,
        method, edge_type — so callers can show HOW node_id depends on each
        target, not just which targets exist.

        MultiDiGraph (ADR-011): every parallel out-edge is returned separately.

        Args:
            node_id: source node whose outgoing edges we want.
            edge_type: if given, only edges of this type are returned.

        Returns:
            List of Edge objects, sorted by (target name, edge type) for
            deterministic output. Empty if node missing or no matching edges.
        """
        if node_id not in self._nx:
            return []

        edges: list[Edge] = []
        # out_edges with keys+data on a MultiDiGraph: (src, tgt, key, data)
        for _src, tgt, _key, data in self._nx.out_edges(node_id, keys=True, data=True):
            edge = Edge(**data)
            if edge_type is not None and edge.edge_type != edge_type:
                continue
            edges.append(edge)

        def _sort_key(e: Edge) -> tuple[str, str]:
            tgt_node = self._graph.get_node(e.target_id)
            tgt_name = tgt_node.name if tgt_node else e.target_id
            return (tgt_name.casefold(), e.edge_type.value)

        return sorted(edges, key=_sort_key)

    # ------------------------------------------------------------------
    # Paths
    # ------------------------------------------------------------------

    def find_path(self, from_id: str, to_id: str) -> list[Edge]:
        """Shortest directed path from_id --> to_id, returned as the edges
        traversed. Empty list if either node is missing, same node, or no path.

        MultiDiGraph (ADR-011): picks the first edge key per hop as a
        representative edge; path structure is unaffected by parallel edges.
        """
        if from_id == to_id:
            return []
        if from_id not in self._nx or to_id not in self._nx:
            return []
        try:
            node_path = nx.shortest_path(self._nx, from_id, to_id)
        except nx.NetworkXNoPath:
            return []

        edges: list[Edge] = []
        for a, b in zip(node_path, node_path[1:]):
            edge_dict = self._nx.get_edge_data(a, b)
            first_key = sorted(edge_dict.keys())[0]
            edges.append(Edge(**edge_dict[first_key]))
        return edges

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    def find_by_name(self, query: str, *, exact: bool = False) -> list[Node]:
        """Case-insensitive name search. Substring match unless exact=True."""
        q = query.casefold()

        def matches(name: str) -> bool:
            name = name.casefold()
            return name == q if exact else q in name

        found = [n for n in self._graph.all_nodes() if matches(n.name)]
        return sorted(found, key=lambda n: n.name)

    # ------------------------------------------------------------------
    # Health checks
    # ------------------------------------------------------------------

    def find_orphaned(self) -> list[Node]:
        """No edges in or out — dead code or UI-bound (Aura/LWC/VF refs
        the Apex scan can't see)."""
        return sorted(
            (
                n
                for n in self._graph.all_nodes()
                if self._nx.in_degree(n.id) == 0
                and self._nx.out_degree(n.id) == 0
            ),
            key=lambda n: n.name,
        )

    def find_never_referenced(
        self, *, exclude_tests: bool = False
    ) -> list[Node]:
        """Nodes nothing points at, but which point at others — in==0, out>0.

        Args:
            exclude_tests: When True, omit nodes where attributes["is_test"]
                           is True (test classes are structurally never-
                           referenced; the @isTest runner invokes them by
                           annotation, not by code reference).
        """
        def _keep(n: Node) -> bool:
            if self._nx.in_degree(n.id) != 0:
                return False
            if self._nx.out_degree(n.id) == 0:
                return False
            if exclude_tests and n.attributes.get("is_test"):
                return False
            return True

        return sorted(
            (n for n in self._graph.all_nodes() if _keep(n)),
            key=lambda n: n.name,
        )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _nodes_for(self, node_ids) -> list[Node]:
        """Resolve an iterable of ids to Nodes, sorted by name. Dedupes —
        predecessors()/successors() on a MultiDiGraph may repeat a neighbor
        reached by parallel edges."""
        seen: set[str] = set()
        nodes: list[Node] = []
        for i in node_ids:
            if i in seen:
                continue
            seen.add(i)
            node = self._graph.get_node(i)
            if node is not None:
                nodes.append(node)
        return sorted(nodes, key=lambda n: n.name)


# ============================================================
# APEX EQUIVALENT (for comparison)
# ============================================================
# In-memory traversal over a Map<Id, Map<Id, List<Edge>>> adjacency
# (List per pair = MultiDiGraph parallel edges).
#
#    public class QueryEngine {
#        Map<Id, Map<Id, List<Edge>>> forward;
#        Map<Id, Map<Id, List<Edge>>> reverse;
#
#        // incoming_edges(X, edgeType): every in-edge, optionally filtered
#        public List<Edge> incomingEdges(Id nodeId, String edgeType) {
#            List<Edge> result = new List<Edge>();
#            Map<Id, List<Edge>> sources = reverse.get(nodeId);
#            if (sources == null) return result;
#            for (List<Edge> parallel : sources.values()) {
#                for (Edge e : parallel) {
#                    if (edgeType == null || e.edgeType == edgeType)
#                        result.add(e);
#                }
#            }
#            return result;   // caller sorts
#        }
#    }
#
# Concept mapping:
# - in_edges(node, keys=True, data=True)  → reverse.get(nodeId) -> Map<Id,List<Edge>>
# - edge_type: EdgeType | None = None     → String edgeType param, null = no filter
# - sorted(key=lambda) with name lookup   → List.sort() w/ Comparable wrapper
# - MultiDiGraph parallel in-edges         → List<Edge> per source in reverse map
# ============================================================
