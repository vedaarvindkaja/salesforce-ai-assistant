"""Hermetic tests for the tool-pull system-prompt builder (Week 8 Day 5)."""
import pytest

from app.intelligence.graph.models import (
    Edge, EdgeType, MetadataGraph, Node, NodeType,
)
from app.intelligence.orchestration.system_prompt import build_system_prompt

ORG = "https://test.my.salesforce.com"


def _n(id, name, t=NodeType.APEX_CLASS):
    return Node(id=id, name=name, node_type=t, org_key=ORG, attributes={})


def _graph():
    g = MetadataGraph()
    g.add_node(_n("01p1", "OppSelector"))
    g.add_node(_n("01p2", "OppDomain"))
    g.add_node(_n("obj:opportunity", "Opportunity", NodeType.OBJECT))
    g.add_node(_n("flow:my_flow", "My_Flow", NodeType.FLOW))
    g.add_edge(Edge(source_id="01p1", target_id="obj:opportunity",
                    edge_type=EdgeType.USES_OBJECT, attributes={"via": "soql"}))
    g.add_edge(Edge(source_id="01p2", target_id="obj:opportunity",
                    edge_type=EdgeType.USES_OBJECT, attributes={"via": "soql"}))
    g.add_edge(Edge(source_id="flow:my_flow", target_id="01p1",
                    edge_type=EdgeType.CALLS, attributes={"via": "flow_action"}))
    return g


def test_includes_node_and_edge_counts():
    out = build_system_prompt(_graph())
    assert "4 components" in out
    assert "3 relationships" in out


def test_includes_type_breakdown():
    out = build_system_prompt(_graph())
    # 2 ApexClass dominates, then Object, Flow (count-desc, name-asc ordering)
    assert "2 ApexClass" in out
    assert "1 Object" in out
    assert "1 Flow" in out


def test_includes_edge_breakdown():
    out = build_system_prompt(_graph())
    assert "2 USES_OBJECT" in out
    assert "1 CALLS" in out


def test_explains_edge_semantics():
    out = build_system_prompt(_graph())
    assert "REFERENCES" in out and "CALLS" in out and "USES_OBJECT" in out
    assert "Flow action" in out and "subflow" in out


def test_states_direction_distinction():
    out = build_system_prompt(_graph())
    # The find_dependencies vs find_references_to direction guidance must be present
    assert "find_dependencies" in out and "find_references_to" in out
    assert "outward" in out.lower() and "inward" in out.lower()


def test_includes_known_limitations():
    out = build_system_prompt(_graph())
    assert "LIMITATIONS" in out
    # The Day-3 real-org finding: flow record operations are not captured
    assert "recordLookups" in out
    assert "field level" in out.lower()


def test_instructs_tool_use_over_guessing():
    out = build_system_prompt(_graph())
    assert "find_by_name" in out
    assert "get_source" in out
    lowered = out.lower()
    assert "never invent" in lowered or "do not invent" in lowered


def test_empty_graph_is_handled():
    out = build_system_prompt(MetadataGraph())
    assert "0 components" in out
    assert "empty" in out.lower()
    # Still includes guidance + limitations even with no data
    assert "LIMITATIONS" in out
