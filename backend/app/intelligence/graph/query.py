# ============================================================
# PYTHON CODE
# ============================================================
"""Graph query engine — domain questions answered over the in-memory graph.

Synchronous by design: the graph lives in memory (the builder already paid
the async SQLite cost), so queries need no await and return instantly.

Vocabulary (edge semantics: source REFERENCES/CALLS/USES target, source --> target):
  what_depends_on(X)        -> who points at X         (predecessors / ancestors)
  what_does_it_depend_on(X) -> what X points at        (successors / descendants)
  find_path(A, B)           -> shortest A-->B route as edges
  find_by_name(q)           -> nodes whose name matches q (case-insensitive)
  find_orphaned()           -> in==0 AND out==0  (dead / UI-bound)
  find_never_referenced()   -> in==0 AND out>0   (metadata-wired)
                               exclude_tests=True filters @isTest classes

Transitive traversal uses raw networkx via the ADR-008 escape hatch.
ADR-011: the underlying graph is a MultiDiGraph, so find_path picks one
edge per hop (lowest key) when parallel edges exist between two nodes.
"""
from __future__ import annotations

import networkx as nx

from app.intelligence.graph.models import Edge, MetadataGraph, Node


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
    # Paths
    # ------------------------------------------------------------------

    def find_path(self, from_id: str, to_id: str) -> list[Edge]:
        """Shortest directed path from_id --> to_id, returned as the edges
        traversed. Empty list if either node is missing, same node, or no path.

        MultiDiGraph (ADR-011): between two adjacent nodes there may be
        several parallel edges (e.g. REFERENCES and CALLS). We pick the
        first edge key deterministically and surface its data; the path
        structure (which nodes) is unaffected by parallel edges.
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
            # MultiDiGraph: get_edge_data returns {key: data_dict, ...}.
            # Pick the first key deterministically for a representative edge.
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
        the Apex scan can't see). in_degree/out_degree on a MultiDiGraph
        count parallel edges, but ==0 is unaffected by multiplicity."""
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
        """Resolve an iterable of ids to Nodes, sorted by name for
        deterministic output. Dedupes — predecessors()/successors() on a
        MultiDiGraph may repeat a neighbor reached by parallel edges."""
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
# (List per pair = MultiDiGraph parallel edges). No networkx, so transitive
# traversal is a manual BFS; in/out degree are map-size lookups.
#
#    public class QueryEngine {
#        Map<Id, Map<Id, List<Edge>>> forward;   // source -> target -> [edges]
#        Map<Id, Map<Id, List<Edge>>> reverse;
#
#        // find_path: pick first edge per hop (parallel edges collapse to one)
#        public List<Edge> findPath(Id fromId, Id toId) {
#            List<Id> nodePath = bfsShortestPath(fromId, toId);
#            List<Edge> edges = new List<Edge>();
#            for (Integer i = 0; i < nodePath.size() - 1; i++) {
#                List<Edge> parallel = forward.get(nodePath[i]).get(nodePath[i+1]);
#                edges.add(parallel[0]);   // representative edge
#            }
#            return edges;
#        }
#    }
#
# Concept mapping:
# - get_edge_data(a, b) -> {key: data}   → forward.get(a).get(b) -> List<Edge>
# - sorted(keys)[0] (deterministic pick) → parallel[0] after sort
# - _nodes_for dedup via set             → Set<Id> seen guard
# - nx.ancestors / descendants           → manual BFS over reverse / forward
# - in_degree==0 (parallel-edge-safe)    → reverse.get(id) == null || empty
# ============================================================
