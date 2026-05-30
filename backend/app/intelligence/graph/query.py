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
        traversed (each carrying its line_numbers). Empty list if either node
        is missing, they're the same node, or no path exists."""
        if from_id not in self._nx or to_id not in self._nx:
            return []
        try:
            node_path = nx.shortest_path(self._nx, from_id, to_id)
        except nx.NetworkXNoPath:
            return []
        return [
            Edge(**self._nx.edges[a, b])
            for a, b in zip(node_path, node_path[1:])
        ]

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    def find_by_name(self, query: str, *, exact: bool = False) -> list[Node]:
        """Nodes whose name matches query, case-insensitively (Apex is
        case-insensitive — ADR-007). Substring match unless exact=True."""
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
        """No references in or out — dead code or UI-bound (Aura/LWC/VF refs
        the Apex scan can't see)."""
        return sorted(
            (
                n
                for n in self._graph.all_nodes()
                if self._nx.in_degree(n.id) == 0 and self._nx.out_degree(n.id) == 0
            ),
            key=lambda n: n.name,
        )

    def find_never_referenced(self) -> list[Node]:
        """Nothing references them, but they reference others. In a
        trigger-actions org these are typically action classes wired via
        Trigger_Action__mdt — invisible to an Apex string scan, so in==0."""
        return sorted(
            (
                n
                for n in self._graph.all_nodes()
                if self._nx.in_degree(n.id) == 0 and self._nx.out_degree(n.id) > 0
            ),
            key=lambda n: n.name,
        )

    # ------------------------------------------------------------------
    # internal
    # ------------------------------------------------------------------

    def _nodes_for(self, node_ids) -> list[Node]:
        """Resolve an iterable of ids to Nodes, sorted by name for
        deterministic output. (Ranking by blast radius is parked — ties to
        the production-vs-test ranking refinement.)"""
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
#
#        // what_depends_on(X), transitive=false -> direct dependents
#        public Set<Id> whatDependsOn(Id nodeId) {
#            return reverse.containsKey(nodeId) ? reverse.get(nodeId) : new Set<Id>();
#        }
#
#        // transitive=true -> BFS over the reverse map (= nx.ancestors)
#        public Set<Id> whatDependsOnTransitive(Id nodeId) {
#            Set<Id> seen = new Set<Id>();
#            List<Id> queue = new List<Id>(whatDependsOn(nodeId));
#            while (!queue.isEmpty()) {
#                Id cur = queue.remove(0);
#                if (seen.contains(cur)) continue;     // cycle guard
#                seen.add(cur);
#                if (reverse.containsKey(cur)) queue.addAll(reverse.get(cur));
#            }
#            return seen;                              // excludes nodeId itself
#        }
#
#        // find_orphaned -> in==0 AND out==0
#        public Boolean isOrphan(Id nodeId) {
#            return !reverse.containsKey(nodeId) && !forward.containsKey(nodeId);
#        }
#
#        // find_never_referenced -> in==0 AND out>0
#        public Boolean isNeverReferenced(Id nodeId) {
#            return !reverse.containsKey(nodeId) && forward.containsKey(nodeId);
#        }
#    }
#
# Concept mapping:
# - nx.ancestors(G, X)              -> manual BFS over the reverse adjacency map
# - nx.descendants(G, X)            -> manual BFS over the forward adjacency map
# - G.predecessors(X) / successors  -> reverse.get(X) / forward.get(X)  (1 hop)
# - nx.shortest_path(G, A, B)       -> BFS tracking parent pointers, then walk back
# - in_degree==0 / out_degree==0    -> !reverse.containsKey / !forward.containsKey
# - cycle handling (free in nx)     -> explicit `seen` set in the BFS (cycle guard)
# - synchronous (in-memory graph)   -> Apex is synchronous too; the parallel holds
# ============================================================
