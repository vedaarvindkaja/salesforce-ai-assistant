# ============================================================
# PYTHON CODE
# ============================================================
"""Graph query engine — domain questions answered over the in-memory graph.

Synchronous by design: the graph lives in memory (the builder already paid
the async SQLite cost), so queries need no await and return instantly.

Vocabulary (edge semantics: source REFERENCES target, source --> target):
  what_depends_on(X)        -> who references X        (predecessors / ancestors)
  what_does_it_depend_on(X) -> what X references       (successors / descendants)
  find_path(A, B)           -> shortest A-->B route as edges
  find_by_name(q)           -> nodes whose name matches q (case-insensitive)
  find_orphaned()           -> in==0 AND out==0  (dead / UI-bound)
  find_never_referenced()   -> in==0 AND out>0   (metadata-wired, e.g. trigger
                                                   actions invisible to Apex scan)
                               exclude_tests=True filters out @isTest classes
                               so the signal is production code only.

Transitive traversal uses raw networkx via the ADR-008 escape hatch
(MetadataGraph._graph); this module is its single sanctioned consumer.
"""
from __future__ import annotations

import networkx as nx

from app.intelligence.graph.models import Edge, MetadataGraph, Node


class QueryEngine:
    """Answers dependency questions over a built MetadataGraph."""

    def __init__(self, graph: MetadataGraph) -> None:
        self._graph = graph
        # Sanctioned escape hatch (ADR-008): the query layer is allowed raw
        # networkx access for traversal algorithms. Resolved once here.
        self._nx: nx.DiGraph = graph._graph

    # ------------------------------------------------------------------
    # Dependency direction
    # ------------------------------------------------------------------

    def what_depends_on(self, node_id: str, *, transitive: bool = False) -> list[Node]:
        """Nodes that reference node_id. transitive=True returns the full
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
        """Nodes that node_id references. transitive=True returns everything
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
        traversed (each carrying its line_numbers).

        Returns [] when no path exists or either node is missing.
        Same-node returns [] (no self-loops in a well-formed graph).
        """
        if from_id == to_id:
            return []
        if from_id not in self._nx or to_id not in self._nx:
            return []
        try:
            node_path: list[str] = nx.shortest_path(self._nx, from_id, to_id)
        except nx.NetworkXNoPath:
            return []
        edges: list[Edge] = []
        for src, tgt in zip(node_path, node_path[1:]):
            data = self._nx.edges[src, tgt]
            edges.append(
                Edge(
                    source_id=src,
                    target_id=tgt,
                    edge_type=data["edge_type"],
                    attributes=data.get("attributes", {}),
                )
            )
        return edges

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def find_by_name(self, query: str, *, exact: bool = False) -> list[Node]:
        """Case-insensitive name search. exact=True requires full match."""
        q = query.casefold()

        def matches(name: str) -> bool:
            return name.casefold() == q if exact else q in name.casefold()

        return sorted(
            (n for n in self._graph.all_nodes() if matches(n.name)),
            key=lambda n: n.name,
        )

    # ------------------------------------------------------------------
    # Health checks
    # ------------------------------------------------------------------

    def find_orphaned(self) -> list[Node]:
        """Nodes with no edges at all — in==0 AND out==0.
        Typically dead code or UI-bound controllers invisible to Apex scan."""
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
        """Nodes nothing references, but which reference others — in==0, out>0.

        In a trigger-actions org these include action classes wired via
        Trigger_Action__mdt, invisible to an Apex string scan.

        Args:
            exclude_tests: When True, omit nodes where attributes["is_test"]
                           is True. Use this to surface production-code signal
                           only — test classes are structurally never-referenced
                           (the @isTest runner invokes them by annotation, not
                           by code reference) and are noise for dead-code analysis.
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
        deterministic output."""
        nodes = [self._graph.get_node(i) for i in node_ids]
        return sorted((n for n in nodes if n is not None), key=lambda n: n.name)


# ============================================================
# APEX EQUIVALENT (for comparison)
# ============================================================
# An in-memory graph traversal in Apex over a Map<Id, Set<Id>> adjacency
# (forward = dependencies, reverse = dependents). No networkx, so transitive
# traversal is a manual BFS; in/out degree are map-size lookups.
#
#    public class QueryEngine {
#        Map<Id, Set<Id>> forward;   // sourceId -> targets it references
#        Map<Id, Set<Id>> reverse;   // targetId -> sources that reference it
#        Map<Id, Boolean> isTest;    // nodeId -> is_test attribute
#
#        // find_never_referenced(excludeTests=false)
#        public List<Id> findNeverReferenced(Boolean excludeTests) {
#            List<Id> result = new List<Id>();
#            for (Id nodeId : forward.keySet()) {
#                // in==0: nothing points to this node
#                if (reverse.containsKey(nodeId)) continue;
#                // out>0: it points to something (already guaranteed by forward.keySet())
#                if (excludeTests && isTest.get(nodeId) == true) continue;
#                result.add(nodeId);
#            }
#            return result;
#        }
#    }
#
# Concept mapping:
# - exclude_tests keyword-only arg         -> Boolean method parameter
# - n.attributes.get("is_test")            -> isTest.get(nodeId)
# - inner _keep() predicate function       -> inline if-chain (Apex has no nested fns)
# - nx.ancestors(G, X)                     -> manual BFS over reverse adjacency map
# - nx.descendants(G, X)                   -> manual BFS over forward adjacency map
# - nx.shortest_path(G, A, B)              -> BFS tracking parent pointers
# - keyword-only args (*, exclude_tests)   -> no Apex equivalent; use named param
# ============================================================
