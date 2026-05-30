"""Tests for CLI handlers (pure functions) and argparse wiring (Week 6 Day 6 + Week 7 Day 4)."""
import pytest

from app.intelligence.graph.models import (
    Edge, EdgeType, MetadataGraph, Node, NodeType,
)
from app.intelligence.graph.query import QueryEngine
from app.interfaces import cli

ORG = "https://test.my.salesforce.com"


def _n(id, name, t=NodeType.APEX_CLASS):
    return Node(id=id, name=name, node_type=t, org_key=ORG)

def _e(s, t, lines):
    return Edge(source_id=s, target_id=t, edge_type=EdgeType.REFERENCES,
               attributes={"line_numbers": lines, "match_count": len(lines)})

def _graph():
    g = MetadataGraph()
    g.add_node(_n("01p1", "MetadataTriggerHandler"))
    g.add_node(_n("01p2", "AccountDomain"))
    g.add_node(_n("01p3", "TA_SetOwner"))
    g.add_node(_n("01p4", "DeadController"))
    g.add_node(_n("01q1", "AccountTrigger", NodeType.APEX_TRIGGER))
    g.add_edge(_e("01p2", "01p1", [3]))
    g.add_edge(_e("01q1", "01p1", [2]))
    g.add_edge(_e("01p3", "01p2", [7, 8]))
    return g

def _engine():
    return QueryEngine(_graph())


def test_resolve_exact():
    node, err = cli._resolve_one(_engine(), "MetadataTriggerHandler")
    assert err is None and node.name == "MetadataTriggerHandler"

def test_resolve_case_insensitive():
    node, err = cli._resolve_one(_engine(), "metadatatriggerhandler")
    assert err is None and node.id == "01p1"

def test_resolve_single_substring_autoresolves():
    node, err = cli._resolve_one(_engine(), "SetOwner")
    assert err is None and node.name == "TA_SetOwner"

def test_resolve_missing():
    node, err = cli._resolve_one(_engine(), "Nonexistent")
    assert node is None and "No metadata named" in err

def test_resolve_ambiguous():
    node, err = cli._resolve_one(_engine(), "Account")
    assert node is None and "ambiguous" in err


def test_depends_on_direct():
    out = cli._cmd_depends_on(_engine(), "MetadataTriggerHandler", transitive=False)
    assert "2 direct dependent(s)" in out
    assert "AccountDomain" in out and "AccountTrigger" in out

def test_depends_on_transitive_wider():
    out = cli._cmd_depends_on(_engine(), "MetadataTriggerHandler", transitive=True)
    assert "3 transitive dependent(s)" in out
    assert "TA_SetOwner" in out

def test_depends_on_none():
    out = cli._cmd_depends_on(_engine(), "AccountTrigger", transitive=False)
    assert "Nothing depends on" in out

def test_depends_on_unknown_name():
    out = cli._cmd_depends_on(_engine(), "Ghost", transitive=False)
    assert "No metadata named" in out


def test_dependencies_direct():
    out = cli._cmd_dependencies(_engine(), "AccountDomain", transitive=False)
    assert "1 direct dependenc" in out and "MetadataTriggerHandler" in out

def test_dependencies_none():
    out = cli._cmd_dependencies(_engine(), "MetadataTriggerHandler", transitive=False)
    assert "depends on nothing" in out


def test_path_found_with_lines():
    g = _graph()
    out = cli._cmd_path(QueryEngine(g), g, "TA_SetOwner", "MetadataTriggerHandler")
    assert "Path from TA_SetOwner to MetadataTriggerHandler (2 hop(s))" in out
    assert "TA_SetOwner --references--> AccountDomain" in out
    assert "lines 7, 8" in out

def test_path_none():
    g = _graph()
    out = cli._cmd_path(QueryEngine(g), g, "MetadataTriggerHandler", "TA_SetOwner")
    assert "No dependency path" in out


def test_find():
    out = cli._cmd_find(_engine(), "Account")
    assert "AccountDomain" in out and "AccountTrigger" in out

def test_orphans():
    out = cli._cmd_orphans(_engine())
    assert "DeadController" in out and "1 orphan" in out

def test_never_referenced():
    out = cli._cmd_never_referenced(_engine())
    assert "TA_SetOwner" in out

def test_stats():
    out = cli._cmd_stats(_graph())
    assert "nodes: 5" in out and "edges: 3" in out


# ------------------------------------------------------------------
# Week 7 Day 4 — impact command
# ------------------------------------------------------------------

def _impact_graph():
    """Object node touched by classes via SOQL, plus a CALLS example."""
    g = MetadataGraph()
    g.add_node(_n("01p1", "OppSelector"))
    g.add_node(_n("01p2", "OppDomain"))
    g.add_node(_n("obj:opportunity", "Opportunity", NodeType.OBJECT))
    g.add_node(_n("01p3", "Caller"))
    g.add_node(_n("01p4", "Helper"))
    g.add_edge(Edge(source_id="01p1", target_id="obj:opportunity",
                    edge_type=EdgeType.USES_OBJECT, attributes={"via": "soql"}))
    g.add_edge(Edge(source_id="01p2", target_id="obj:opportunity",
                    edge_type=EdgeType.USES_OBJECT, attributes={"via": "soql"}))
    g.add_edge(Edge(source_id="01p3", target_id="01p4",
                    edge_type=EdgeType.CALLS, attributes={"method": "run"}))
    return g

def _impact_engine():
    return QueryEngine(_impact_graph())


def test_impact_object_shows_classes_and_relation():
    g = _impact_graph()
    out = cli._cmd_impact(QueryEngine(g), g, "Opportunity")
    assert "Impact of Opportunity (Object)" in out
    assert "2 reference(s)" in out
    assert "OppSelector" in out and "OppDomain" in out
    assert "SOQL/DML" in out
    assert "(SOQL)" in out  # the via attribute

def test_impact_calls_shows_method():
    g = _impact_graph()
    out = cli._cmd_impact(QueryEngine(g), g, "Helper")
    assert "method call" in out
    assert "run()" in out

def test_impact_nothing_touches():
    g = _impact_graph()
    # OppSelector has only out-edges
    out = cli._cmd_impact(QueryEngine(g), g, "OppSelector")
    assert "Nothing touches" in out

def test_impact_unknown_name():
    g = _impact_graph()
    out = cli._cmd_impact(QueryEngine(g), g, "Ghost")
    assert "No metadata named" in out


# ------------------------------------------------------------------
# argparse wiring
# ------------------------------------------------------------------

def test_parser_depends_on_with_flag():
    args = cli._build_parser().parse_args(["depends-on", "Foo", "--transitive"])
    assert args.command == "depends-on" and args.name == "Foo" and args.transitive is True

def test_parser_depends_on_short_flag():
    args = cli._build_parser().parse_args(["depends-on", "Foo", "-t"])
    assert args.transitive is True

def test_parser_depends_on_default_no_flag():
    args = cli._build_parser().parse_args(["depends-on", "Foo"])
    assert args.transitive is False

def test_parser_impact_one_arg():
    args = cli._build_parser().parse_args(["impact", "Opportunity"])
    assert args.command == "impact" and args.name == "Opportunity"

def test_parser_path_two_args():
    args = cli._build_parser().parse_args(["path", "A", "B"])
    assert args.from_name == "A" and args.to_name == "B"

def test_parser_never_referenced_no_tests_flag():
    args = cli._build_parser().parse_args(["never-referenced", "--no-tests"])
    assert args.no_tests is True

def test_parser_never_referenced_default_no_flag():
    args = cli._build_parser().parse_args(["never-referenced"])
    assert args.no_tests is False

def test_parser_no_command_exits():
    with pytest.raises(SystemExit):
        cli._build_parser().parse_args([])

def test_parser_unknown_command_exits():
    with pytest.raises(SystemExit):
        cli._build_parser().parse_args(["frobnicate", "X"])
