# ============================================================
# PYTHON CODE
# ============================================================
"""Graph data models — typed vocabulary for the metadata graph.

NodeType and EdgeType enumerate all *planned* node/edge kinds across
Phase 1. Only a subset are populated in any given week:
  Week 6: ApexClass, ApexTrigger nodes; REFERENCES edges.
  Week 7: Object nodes (derived); CALLS + USES_OBJECT edges live.
  Week 8+: Flow, ValidationRule, PermissionSet added as extraction broadens.

ADR-008: MetadataGraph wraps networkx rather than exposing it directly.
ADR-010: Object nodes are DERIVED from parser output (source="derived").
ADR-011: MetadataGraph uses MultiDiGraph (not DiGraph) so two nodes can
carry multiple distinct typed edges — e.g. Caller both REFERENCES and
CALLS Helper. DiGraph collapses these to one edge, silently losing data.
See bottom of file / NOTES.md.
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
    """Metadata kinds that can appear as graph nodes."""
    APEX_CLASS      = "ApexClass"
    APEX_TRIGGER    = "ApexTrigger"
    OBJECT          = "Object"          # Week 7 — derived from parser (ADR-010)
    FIELD           = "Field"           # Phase 2 — needs Object extraction first
    FLOW            = "Flow"            # Week 8 — FlowDefinition via Tooling API
    VALIDATION_RULE = "ValidationRule"  # Week 8
    PERMISSION_SET  = "PermissionSet"   # Phase 2


class EdgeType(str, Enum):
    """Relationship kinds that can appear as graph edges."""
    REFERENCES    = "REFERENCES"     # ApexClass/Trigger → anything it mentions (string-scan)
    CALLS         = "CALLS"          # ApexClass → ApexClass (method call, parser) — Week 7
    USES_OBJECT   = "USES_OBJECT"    # ApexClass → Object (SOQL/DML, parser) — Week 7
    EXTENDS       = "EXTENDS"        # ApexClass → ApexClass (inheritance) — stub
    MASTER_DETAIL = "MASTER_DETAIL"  # Field → Object — Phase 2
    LOOKUP        = "LOOKUP"         # Field → Object — Phase 2
    GRANTS_ACCESS = "GRANTS_ACCESS"  # PermissionSet → Object/Field — Phase 2


# ------------------------------------------------------------------
# Node and Edge models
# ------------------------------------------------------------------

class Node(BaseModel):
    """One metadata item in the graph."""
    id: str            # Salesforce record Id, or synthetic key (e.g. obj:account)
    name: str          # DeveloperName / API name
    node_type: NodeType
    org_key: str       # instance_url — matches MetadataCache partition key (ADR-005)
    attributes: dict = Field(default_factory=dict)


class Edge(BaseModel):
    """A directed relationship between two nodes."""
    source_id: str
    target_id: str
    edge_type: EdgeType
    attributes: dict = Field(default_factory=dict)


# ------------------------------------------------------------------
# Graph statistics snapshot
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


# ------------------------------------------------------------------
# MetadataGraph — typed wrapper around networkx.MultiDiGraph (ADR-008/011)
# ------------------------------------------------------------------

class MetadataGraph:
    """Typed wrapper around a networkx MultiDiGraph.

    Callers interact with Node/Edge Pydantic models; the underlying
    networkx representation is an implementation detail (ADR-008).

    MultiDiGraph (ADR-011) allows parallel edges between the same ordered
    node pair, so REFERENCES and CALLS edges from Caller→Helper coexist.
    DiGraph would collapse them to one, silently dropping the first.

    Because parallel edges exist, successors()/predecessors() dedupe by
    node id — a neighbor reached by two edge types is still one neighbor.
    """

    def __init__(self) -> None:
        self._g: nx.MultiDiGraph = nx.MultiDiGraph()

    # ------ mutation ------

    def add_node(self, node: Node) -> None:
        """Add or overwrite a node. Idempotent on node.id."""
        self._g.add_node(node.id, **node.model_dump())

    def add_edge(self, edge: Edge) -> None:
        """Add a directed edge. In a MultiDiGraph, repeated source/target
        pairs create parallel edges rather than overwriting (ADR-011).
        Caller must ensure both node ids exist."""
        self._g.add_edge(edge.source_id, edge.target_id, **edge.model_dump())

    # ------ read ------

    def get_node(self, node_id: str) -> Node | None:
        data = self._g.nodes.get(node_id)
        return Node(**data) if data else None

    def all_nodes(self) -> list[Node]:
        return [Node(**data) for _, data in self._g.nodes(data=True) if data]

    def all_edges(self) -> list[Edge]:
        """All edges including parallel ones. MultiDiGraph.edges(data=True)
        yields every parallel edge separately."""
        return [Edge(**data) for _, _, data in self._g.edges(data=True) if data]

    def successors(self, node_id: str) -> list[Node]:
        """Distinct nodes node_id has outgoing edges TO. Deduped: a neighbor
        reached by multiple parallel edges counts once (ADR-011)."""
        seen: set[str] = set()
        result: list[Node] = []
        for n in self._g.successors(node_id):
            if n in seen or not self._g.nodes.get(n):
                continue
            seen.add(n)
            result.append(Node(**self._g.nodes[n]))
        return result

    def predecessors(self, node_id: str) -> list[Node]:
        """Distinct nodes with edges TO node_id. Deduped (ADR-011)."""
        seen: set[str] = set()
        result: list[Node] = []
        for n in self._g.predecessors(node_id):
            if n in seen or not self._g.nodes.get(n):
                continue
            seen.add(n)
            result.append(Node(**self._g.nodes[n]))
        return result

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
            edge_count=self._g.number_of_edges(),  # counts parallel edges
            node_type_counts=node_type_counts,
            edge_type_counts=edge_type_counts,
        )

    # ------ internal (for query layer only) ------

    @property
    def _graph(self) -> nx.MultiDiGraph:
        """Escape hatch for the query layer (ADR-008)."""
        return self._g


# ============================================================
# APEX EQUIVALENT (for comparison)
# ============================================================
#
#    public interface NodeType {
#        String APEX_CLASS    = 'ApexClass';
#        String APEX_TRIGGER  = 'ApexTrigger';
#        String OBJECT        = 'Object';
#    }
#
#    public interface EdgeType {
#        String REFERENCES    = 'REFERENCES';
#        String CALLS         = 'CALLS';
#        String USES_OBJECT   = 'USES_OBJECT';
#    }
#
#    public class Node {
#        public String id;
#        public String name;
#        public String nodeType;
#        public String orgKey;
#        public Map<String, Object> attributes = new Map<String, Object>();
#    }
#
#    public class Edge {
#        public String sourceId;
#        public String targetId;
#        public String edgeType;
#        public Map<String, Object> attributes = new Map<String, Object>();
#    }
#
#    // MultiDiGraph parallel-edge equivalent: the adjacency value must be a
#    // List of edges per neighbor, not a single edge. In Apex:
#    //   Map<Id, Map<Id, List<Edge>>> adj;  // source -> target -> [edges]
#    // A plain Map<Id, Map<Id, Edge>> (DiGraph) would overwrite, dropping
#    // the REFERENCES edge when a CALLS edge is added between the same pair.
#
# Concept mapping:
# - nx.MultiDiGraph                  → Map<Id, Map<Id, List<Edge>>> (list per pair)
# - nx.DiGraph (rejected)            → Map<Id, Map<Id, Edge>> (overwrites — the bug)
# - successors() dedup               → Set<Id> guard while iterating parallel edges
# - Field(default_factory=dict)      → = new Map<String,Object>() in declaration
# ============================================================
