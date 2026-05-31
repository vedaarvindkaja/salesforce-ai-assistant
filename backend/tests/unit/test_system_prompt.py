"""Hermetic tests for the tool-pull system-prompt builders.

Week 8 Day 5: build_system_prompt (qa orientation).
Week 9 Day 1: capability builders (apex / soql / impact) — share the
orientation, add a capability-specific FOCUS block.
"""
import pytest

from app.intelligence.graph.models import (
    Edge, EdgeType, MetadataGraph, Node, NodeType,
)
from app.intelligence.orchestration.system_prompt import (
    build_apex_prompt,
    build_impact_prompt,
    build_soql_prompt,
    build_system_prompt,
)

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


# ==================================================================
# qa orientation (Week 8 — unchanged behaviour)
# ==================================================================

def test_includes_node_and_edge_counts():
    out = build_system_prompt(_graph())
    assert "4 components" in out
    assert "3 relationships" in out


def test_includes_type_breakdown():
    out = build_system_prompt(_graph())
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
    assert "Flow Action" in out and "subflow" in out


def test_states_direction_distinction():
    out = build_system_prompt(_graph())
    assert "find_dependencies" in out and "find_references_to" in out
    assert "outward" in out.lower() and "inward" in out.lower()


def test_includes_known_limitations():
    out = build_system_prompt(_graph())
    assert "LIMITATIONS" in out
    assert "recordLookups" in out
    assert "field" in out.lower()


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
    assert "LIMITATIONS" in out


def test_qa_prompt_has_no_capability_focus_block():
    # qa stays the generic orientation; FOCUS framing is for modes 2-5 only.
    out = build_system_prompt(_graph())
    assert "CAPABILITY FOCUS" not in out


# ==================================================================
# Capability builders share orientation (Week 9 Day 1)
# ==================================================================

def test_apex_prompt_includes_shared_orientation():
    out = build_apex_prompt(_graph())
    assert "THE GRAPH" in out
    assert "LIMITATIONS" in out
    assert "find_dependencies" in out and "find_references_to" in out


def test_soql_prompt_includes_shared_orientation():
    out = build_soql_prompt(_graph())
    assert "THE GRAPH" in out
    assert "LIMITATIONS" in out


def test_impact_prompt_includes_shared_orientation():
    out = build_impact_prompt(_graph())
    assert "THE GRAPH" in out
    assert "LIMITATIONS" in out


def test_all_capability_prompts_carry_counts():
    for builder in (build_apex_prompt, build_soql_prompt, build_impact_prompt):
        out = builder(_graph())
        assert "4 components" in out
        assert "3 relationships" in out


# ==================================================================
# Capability-specific focus blocks (Week 9 Day 1)
# ==================================================================

def test_apex_prompt_has_refactoring_focus():
    out = build_apex_prompt(_graph())
    assert "CAPABILITY FOCUS" in out
    lowered = out.lower()
    assert "refactor" in lowered
    assert "get_source" in out  # must read source before explaining


def test_soql_prompt_has_generation_focus_and_field_honesty():
    out = build_soql_prompt(_graph())
    assert "CAPABILITY FOCUS" in out
    assert "SOQL" in out
    lowered = out.lower()
    # The key self-honesty: no field-level knowledge.
    assert "not individual fields" in lowered or "not which" in lowered


def test_impact_prompt_has_risk_rating_structure():
    out = build_impact_prompt(_graph())
    assert "CAPABILITY FOCUS" in out
    assert "RISK RATING" in out
    assert "DIRECT IMPACT" in out
    assert "TRANSITIVE IMPACT" in out


def test_impact_prompt_explains_flow_vs_apex_risk():
    # The Week-8 PricingFlowAction insight baked into the prompt.
    out = build_impact_prompt(_graph())
    lowered = out.lower()
    assert "compile time" in lowered
    assert "runtime" in lowered
