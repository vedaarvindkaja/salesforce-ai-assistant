# ============================================================
# PYTHON CODE
# ============================================================
"""Graph data models — typed vocabulary for the metadata graph.

NodeType and EdgeType enumerate all *planned* node/edge kinds across
Phase 1. Only a subset are populated in any given week:
  Week 6: ApexClass, ApexTrigger nodes; REFERENCES edges.
  Week 7: Object, Field nodes added as the Apex parser extracts field refs.
  Week 8+: Flow, ValidationRule, PermissionSet added as extraction broadens.

Stub enum values cost nothing and document intent without creating
untestable builder/query code. The builder skips types it has no data for.

ADR-008: MetadataGraph wraps networkx.DiGraph rather than exposing it
directly. See bottom of file.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

import networkx as nx
from pydantic import BaseModel, Field


# ------------------------------------------------------------------
# Enums
# ------------------------------------------------------------------

class NodeType(str, Enum):
    """Metadata kinds that can appear as graph nodes.

    All Phase 1 target types are listed. Only APEX_CLASS and APEX_TRIGGER
    are populated in Week 6; others are stubs for future weeks.
    """
    APEX_CLASS      = "ApexClass"
    APEX_TRIGGER    = "ApexTrigger"
    OBJECT          = "Object"          # Week 7 — EntityDefinition via Tooling API
    FIELD           = "Field"           # Week 7 — FieldDefinition via Tooling API
    FLOW            = "Flow"            # Week 8 — FlowDefinition via Tooling API
    VALIDATION_RULE = "ValidationRule"  # Week 8
    PERMISSION_SET  = "PermissionSet"   # Phase 2


class EdgeType(str, Enum):
    """Relationship kinds that can appear as graph edges.

    REFERENCES is the only edge type populated in Week 6 (string-scan
    hits from the reference analyzer). Others are stubs.
    """
    REFERENCES    = "REFERENCES"     # ApexClass/Trigger → anything it mentions
    EXTENDS       = "EXTENDS"        # ApexClass → ApexClass (inheritance) — Week 7
    USED_BY       = "USED_BY"        # inverse convenience edge — Week 7
    MASTER_DETAIL = "MASTER_DETAIL"  # Field → Object — Week 7
    LOOKUP        = "LOOKUP"         # Field → Object — Week 7
    GRANTS_ACCESS = "GRANTS_ACCESS"  # PermissionSet → Object/Field — Phase 2


# ------------------------------------------------------------------
# Node and Edge models
# ------------------------------------------------------------------

class Node(BaseModel):
    """One metadata item in the graph."""
    id: str            # Salesforce record Id (15 or 18 char) or synthetic key
    name: str          # DeveloperName / API name
    node_type: NodeType
    org_key: str       # instance_url — matches MetadataCache partition key (ADR-005)
    attributes: dict = Field(default_factory=dict)  # type-specific extras


class Edge(BaseModel):
    """A directed relationship between two nodes."""
    source_id: str     # Node.id of the source
    target_id: str     # Node.id of the target
    edge_type: EdgeType
    attributes: dict = Field(default_factory=dict)  # e.g. {"line_numbers": [12, 47]}


# ------------------------------------------------------------------
# MetadataGraph — thin wrapper around networkx.DiGraph  (ADR-008)
# ------------------------------------------------------------------

class GraphStats(BaseModel):
    """Snapshot statistics returned by MetadataGraph.stats()."""
    node_count: int
    edge_count: int
    node_type_counts: dict[str, int]
    edge_type_counts: dict[str, int]
    built_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class MetadataGraph:
    """Typed wrapper around a networkx DiGraph.

    Callers interact with Node/Edge Pydantic models; the underlying
    networkx representation is an implementation detail. This prevents
    untyped dict access from leaking into the query and REST layers.
    """

    def __init__(self) -> None:
        self._g: nx.DiGraph = nx.DiGraph()

    # ------ mutation ------

    def add_node(self, node: Node) -> None:
        """Add or overwrite a node. Idempotent on node.id."""
        self._g.add_node(node.id, **node.model_dump())

    def add_edge(self, edge: Edge) -> None:
        """Add a directed edge. Caller must ensure both node ids exist."""
        self._g.add_edge(edge.source_id, edge.target_id, **edge.model_dump())

    # ------ read ------

    def get_node(self, node_id: str) -> Node | None:
        """Return the Node for node_id, or None if absent."""
        data = self._g.nodes.get(node_id)
        return Node(**data) if data else None

    def all_nodes(self) -> list[Node]:
        return [Node(**data) for _, data in self._g.nodes(data=True)]

    def all_edges(self) -> list[Edge]:
        return [Edge(**data) for _, _, data in self._g.edges(data=True)]

    def successors(self, node_id: str) -> list[Node]:
        """Nodes that node_id has outgoing edges TO (things it references)."""
        return [
            Node(**self._g.nodes[n])
            for n in self._g.successors(node_id)
            if self._g.nodes.get(n)
        ]

    def predecessors(self, node_id: str) -> list[Node]:
        """Nodes that have edges TO node_id (things that reference it)."""
        return [
            Node(**self._g.nodes[n])
            for n in self._g.predecessors(node_id)
            if self._g.nodes.get(n)
        ]

    # ------ stats ------

    def stats(self) -> GraphStats:
        node_type_counts: dict[str, int] = {}
        for _, data in self._g.nodes(data=True):
            t = data.get("node_type", "unknown")
            node_type_counts[t] = node_type_counts.get(t, 0) + 1

        edge_type_counts: dict[str, int] = {}
        for _, _, data in self._g.edges(data=True):
            t = data.get("edge_type", "unknown")
            edge_type_counts[t] = edge_type_counts.get(t, 0) + 1

        return GraphStats(
            node_count=self._g.number_of_nodes(),
            edge_count=self._g.number_of_edges(),
            node_type_counts=node_type_counts,
            edge_type_counts=edge_type_counts,
        )

    # ------ internal (for query layer only) ------

    @property
    def _graph(self) -> nx.DiGraph:
        """Escape hatch for the query layer, which needs raw networkx
        algorithms (shortest_path, etc.). Prefix _ signals: not public API.
        """
        return self._g


# ============================================================
# APEX EQUIVALENT (for comparison)
# ============================================================
# Apex has no enum keyword; use static final String constants in
# an interface or class to achieve the same named-constant pattern.
#
#    public interface NodeType {
#        String APEX_CLASS    = 'ApexClass';
#        String APEX_TRIGGER  = 'ApexTrigger';
#        String OBJECT        = 'Object';
#        String FIELD         = 'Field';
#        String FLOW          = 'Flow';
#    }
#
#    public interface EdgeType {
#        String REFERENCES    = 'REFERENCES';
#        String EXTENDS       = 'EXTENDS';
#        String MASTER_DETAIL = 'MASTER_DETAIL';
#    }
#
#    public class Node {
#        public String id;
#        public String name;
#        public String nodeType;     // one of NodeType constants
#        public String orgKey;
#        public Map<String, Object> attributes = new Map<String, Object>();
#    }
#
#    public class Edge {
#        public String sourceId;
#        public String targetId;
#        public String edgeType;     // one of EdgeType constants
#        public Map<String, Object> attributes = new Map<String, Object>();
#    }
#
#    // MetadataGraph has no direct Apex equivalent for an in-memory directed
#    // graph. Closest approximation: Map<String, List<String>> adjacency map
#    // (nodeId → list of neighbor nodeIds), plus a Map<String, Node> for
#    // node lookup. No built-in graph traversal; you'd write BFS/DFS manually
#    // or query a junction object in SOQL.
#
#    public class MetadataGraph {
#        private Map<String, Node> nodes = new Map<String, Node>();
#        // adjacency: sourceId → list of targetIds
#        private Map<String, List<String>> adj = new Map<String, List<String>>();
#
#        public void addNode(Node n) { nodes.put(n.id, n); }
#
#        public void addEdge(Edge e) {
#            if (!adj.containsKey(e.sourceId))
#                adj.put(e.sourceId, new List<String>());
#            adj.get(e.sourceId).add(e.targetId);
#        }
#
#        public List<Node> successors(String nodeId) {
#            List<Node> result = new List<Node>();
#            for (String tid : adj.getOrDefault(nodeId, new List<String>()))
#                if (nodes.containsKey(tid)) result.add(nodes.get(tid));
#            return result;
#        }
#    }
#
# Concept mapping:
# - Python Enum(str, Enum)          → Apex interface with String constants
# - Pydantic BaseModel              → Apex inner class with public fields
# - Field(default_factory=dict)     → = new Map<String,Object>() in declaration
# - networkx.DiGraph                → manual Map<String,List<String>> adjacency
# - nx.DiGraph.successors()         → manual BFS loop over adjacency map
# - node.model_dump()               → no equivalent; manual field assignment
# ============================================================
