"""Hermetic tests for debug-log correlation + capability wiring (Week 12, Day 4).

Uses the REAL graph model + QueryEngine + parser (no network, no Claude). A tiny
synthetic graph stands in for the org; a synthetic Case-shaped log drives the
correlation across all branches: in-graph units with labelled edges, a
managed/not-in-graph unit, the no-Apex-units (Flow-only) path, and the exception
path. Wiring tests confirm the registry entry and tool subset.
"""
from app.intelligence.debuglog.correlate import correlate_log_to_graph
from app.intelligence.debuglog.parser import parse_debug_log
from app.intelligence.graph.models import Edge, EdgeType, MetadataGraph, Node, NodeType
from app.intelligence.graph.query import QueryEngine

ORG = "https://test.my.salesforce.com"


def _n(id, name, t):
    return Node(id=id, name=name, node_type=t, org_key=ORG, attributes={})


def _graph():
    g = MetadataGraph()
    g.add_node(_n("01q1", "CaseObjectTrigger", NodeType.APEX_TRIGGER))
    g.add_node(_n("01p1", "Case_Trigger_Handler", NodeType.APEX_CLASS))
    g.add_node(_n("01p2", "TriggerHandler", NodeType.APEX_CLASS))
    g.add_node(_n("01p3", "CaseService", NodeType.APEX_CLASS))
    g.add_edge(Edge(source_id="01q1", target_id="01p1",
                    edge_type=EdgeType.REFERENCES, attributes={"via": "name reference"}))
    g.add_edge(Edge(source_id="01p1", target_id="01p2",
                    edge_type=EdgeType.CALLS, attributes={"via": "method"}))
    g.add_edge(Edge(source_id="01p1", target_id="01p3",
                    edge_type=EdgeType.CALLS, attributes={"via": "method"}))
    return g


CASE_SHAPED = """64.0 APEX_CODE,FINEST;DB,INFO
07:14:16.1 (1)|EXECUTION_STARTED
07:14:16.1 (2)|CODE_UNIT_STARTED|[EXTERNAL]|01qdM000007U6tZ|CaseObjectTrigger on Case trigger event BeforeInsert|__sfdc_trigger/CaseObjectTrigger
07:14:16.1 (3)|METHOD_ENTRY|[44]|01pdM00000M6vwb|Case_Trigger_Handler.beforeInsert()
07:14:16.1 (4)|METHOD_ENTRY|[2]|01pdM00000M6vYP|TriggerHandler.run()
07:14:16.1 (5)|METHOD_ENTRY|[9]|01pXYZ000000ABCD|fflib_SObjectDomain.handle()
07:14:16.1 (6)|EXECUTION_FINISHED
"""


def test_in_graph_units_resolved_with_labels():
    g = _graph()
    out = correlate_log_to_graph(parse_debug_log(CASE_SHAPED), QueryEngine(g), g)
    assert "Case_Trigger_Handler" in out
    assert "[in graph]" in out
    assert "TriggerHandler" in out
    assert "via" in out  # labelled edges, not bare node names


def test_managed_unit_flagged_not_in_graph():
    g = _graph()
    out = correlate_log_to_graph(parse_debug_log(CASE_SHAPED), QueryEngine(g), g)
    assert "fflib_SObjectDomain" in out
    assert "not in graph" in out


def test_no_apex_units_message():
    g = _graph()
    flow_only = (
        "64.0 APEX_CODE,FINEST\n"
        "07:14:16.1 (1)|CODE_UNIT_STARTED|[EXTERNAL]|Flow:Opportunity\n"
        "07:14:16.1 (2)|CODE_UNIT_FINISHED|Flow:Opportunity\n"
    )
    out = correlate_log_to_graph(parse_debug_log(flow_only), QueryEngine(g), g)
    assert "none executed" in out.lower()


def test_exception_reported():
    g = _graph()
    exc = (
        "64.0 APEX_CODE,FINEST\n"
        "07:14:16.1 (1)|EXCEPTION_THROWN|[20]|System.DmlException: boom REQUIRED_FIELD_MISSING\n"
    )
    out = correlate_log_to_graph(parse_debug_log(exc), QueryEngine(g), g)
    assert "EXCEPTION" in out
    assert "DmlException" in out
    assert "line 20" in out


# ------------------------------------------------------------------
# Wiring
# ------------------------------------------------------------------

def test_debuglog_registered_with_right_subset():
    from app.intelligence.orchestration.capabilities import (
        CAPABILITY_REGISTRY,
        VALID_MODES,
    )
    assert "debuglog" in VALID_MODES
    _builder, tools = CAPABILITY_REGISTRY["debuglog"]
    assert "analyze_debug_log" in tools
    assert "get_source" not in tools  # Decision 4 — excluded initially


def test_build_capability_client_debuglog_exposes_tool():
    from app.intelligence.orchestration.capabilities import build_capability_client
    g = _graph()
    client, schemas = build_capability_client(
        "debuglog", QueryEngine(g), g, None, None
    )
    names = {s["name"] for s in schemas}
    assert "analyze_debug_log" in names
    assert "get_source" not in names


# ------------------------------------------------------------------
# compose_debuglog_input — the shared (path, question) -> message framing
# (Week 12 Day 5). One source for how a log reference becomes a capability
# message, used by the CLI, MCP server, and REST route.
# ------------------------------------------------------------------

def test_compose_debuglog_input_includes_path():
    from app.intelligence.orchestration.capabilities import compose_debuglog_input
    msg = compose_debuglog_input("/tmp/run.log")
    assert "/tmp/run.log" in msg
    assert "Specific question" not in msg


def test_compose_debuglog_input_includes_question():
    from app.intelligence.orchestration.capabilities import compose_debuglog_input
    msg = compose_debuglog_input("/tmp/run.log", "why did the insert fail?")
    assert "/tmp/run.log" in msg
    assert "why did the insert fail?" in msg
