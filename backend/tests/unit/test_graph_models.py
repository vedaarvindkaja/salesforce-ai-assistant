"""Unit tests for graph data models (Week 6, Day 1)."""
import pytest
from app.intelligence.graph.models import (
    Edge,
    EdgeType,
    GraphStats,
    MetadataGraph,
    Node,
    NodeType,
)

ORG = "https://myorg.salesforce.com"


def _apex_class(id: str, name: str) -> Node:
    return Node(id=id, name=name, node_type=NodeType.APEX_CLASS, org_key=ORG)


def _apex_trigger(id: str, name: str) -> Node:
    return Node(id=id, name=name, node_type=NodeType.APEX_TRIGGER, org_key=ORG)


def _ref_edge(source: str, target: str, lines: list[int]) -> Edge:
    return Edge(
        source_id=source,
        target_id=target,
        edge_type=EdgeType.REFERENCES,
        attributes={"line_numbers": lines},
    )


# ------------------------------------------------------------------
# Node tests
# ------------------------------------------------------------------

def test_node_roundtrip():
    n = _apex_class("001abc", "MyClass")
    assert n.id == "001abc"
    assert n.node_type == NodeType.APEX_CLASS
    assert n.node_type.value == "ApexClass"


def test_node_attributes_default_empty():
    n = _apex_class("001abc", "MyClass")
    assert n.attributes == {}


def test_node_custom_attributes():
    n = Node(
        id="001abc",
        name="MyClass",
        node_type=NodeType.APEX_CLASS,
        org_key=ORG,
        attributes={"is_test_class": True},
    )
    assert n.attributes["is_test_class"] is True


# ------------------------------------------------------------------
# Edge tests
# ------------------------------------------------------------------

def test_edge_roundtrip():
    e = _ref_edge("001abc", "002def", [12, 47])
    assert e.source_id == "001abc"
    assert e.edge_type == EdgeType.REFERENCES
    assert e.attributes["line_numbers"] == [12, 47]


def test_edge_attributes_default_empty():
    e = Edge(source_id="a", target_id="b", edge_type=EdgeType.REFERENCES)
    assert e.attributes == {}


# ------------------------------------------------------------------
# MetadataGraph tests
# ------------------------------------------------------------------

def test_add_and_retrieve_node():
    g = MetadataGraph()
    n = _apex_class("001abc", "MyClass")
    g.add_node(n)
    retrieved = g.get_node("001abc")
    assert retrieved is not None
    assert retrieved.name == "MyClass"
    assert retrieved.node_type == NodeType.APEX_CLASS


def test_get_node_missing_returns_none():
    g = MetadataGraph()
    assert g.get_node("nonexistent") is None


def test_add_node_is_idempotent():
    g = MetadataGraph()
    g.add_node(_apex_class("001abc", "MyClass"))
    g.add_node(_apex_class("001abc", "MyClassRenamed"))  # overwrite
    assert g.get_node("001abc").name == "MyClassRenamed"
    assert len(g.all_nodes()) == 1


def test_successors_and_predecessors():
    g = MetadataGraph()
    g.add_node(_apex_class("001", "A"))
    g.add_node(_apex_class("002", "B"))
    g.add_edge(_ref_edge("001", "002", [5]))

    succ = g.successors("001")
    assert len(succ) == 1
    assert succ[0].id == "002"

    pred = g.predecessors("002")
    assert len(pred) == 1
    assert pred[0].id == "001"


def test_no_successors_for_isolated_node():
    g = MetadataGraph()
    g.add_node(_apex_class("001", "Lonely"))
    assert g.successors("001") == []
    assert g.predecessors("001") == []


def test_multiple_edges_from_one_node():
    g = MetadataGraph()
    g.add_node(_apex_class("001", "A"))
    g.add_node(_apex_class("002", "B"))
    g.add_node(_apex_trigger("003", "T"))
    g.add_edge(_ref_edge("001", "002", [1]))
    g.add_edge(_ref_edge("001", "003", [2]))

    succ_ids = {n.id for n in g.successors("001")}
    assert succ_ids == {"002", "003"}


# ------------------------------------------------------------------
# GraphStats tests
# ------------------------------------------------------------------

def test_stats_empty_graph():
    g = MetadataGraph()
    s = g.stats()
    assert s.node_count == 0
    assert s.edge_count == 0
    assert s.node_type_counts == {}
    assert s.edge_type_counts == {}


def test_stats_mixed_graph():
    g = MetadataGraph()
    g.add_node(_apex_class("001", "A"))
    g.add_node(_apex_class("002", "B"))
    g.add_node(_apex_trigger("003", "T"))
    g.add_edge(_ref_edge("001", "002", [1]))
    g.add_edge(_ref_edge("003", "002", [4]))

    s = g.stats()
    assert s.node_count == 3
    assert s.edge_count == 2
    assert s.node_type_counts == {"ApexClass": 2, "ApexTrigger": 1}
    assert s.edge_type_counts == {"REFERENCES": 2}


def test_stats_built_at_is_utc():
    from datetime import timezone
    s = MetadataGraph().stats()
    assert s.built_at.tzinfo == timezone.utc


# ------------------------------------------------------------------
# Enum value tests — guard against typos in enum string values
# ------------------------------------------------------------------

def test_node_type_values():
    assert NodeType.APEX_CLASS.value == "ApexClass"
    assert NodeType.APEX_TRIGGER.value == "ApexTrigger"
    assert NodeType.OBJECT.value == "Object"
    assert NodeType.FIELD.value == "Field"


def test_edge_type_values():
    assert EdgeType.REFERENCES.value == "REFERENCES"
    assert EdgeType.EXTENDS.value == "EXTENDS"
    assert EdgeType.MASTER_DETAIL.value == "MASTER_DETAIL"