"""Hermetic tests for QueryEngine (Week 6 Day 5 + Week 7 Day 1/4 additions)."""
import pytest

from app.intelligence.graph.models import (
    Edge, EdgeType, MetadataGraph, Node, NodeType,
)
from app.intelligence.graph.query import QueryEngine

ORG = "https://test.my.salesforce.com"


def _node(id, name, ntype=NodeType.APEX_CLASS, *, is_test: bool = False):
    return Node(
        id=id, name=name, node_type=ntype, org_key=ORG,
        attributes={"is_test": is_test},
    )


def _edge(src, tgt, lines):
    return Edge(source_id=src, target_id=tgt, edge_type=EdgeType.REFERENCES,
                attributes={"line_numbers": lines, "match_count": len(lines)})

_ref_edge = _edge


def _graph():
    """  A --> B --> C ;  E --> B ;  D orphan """
    g = MetadataGraph()
    for nid, name in [("A","Alpha"),("B","Beta"),("C","Gamma"),
                      ("D","Delta"),("E","Epsilon")]:
        g.add_node(_node(nid, name))
    g.add_edge(_edge("A","B",[10]))
    g.add_edge(_edge("B","C",[20,21]))
    g.add_edge(_edge("E","B",[5]))
    return g


def _names(nodes):
    return [n.name for n in nodes]


# ---- what_depends_on ----

def test_depends_on_direct():
    q = QueryEngine(_graph())
    assert _names(q.what_depends_on("B")) == ["Alpha", "Epsilon"]

def test_depends_on_transitive():
    q = QueryEngine(_graph())
    assert _names(q.what_depends_on("C", transitive=True)) == ["Alpha","Beta","Epsilon"]

def test_depends_on_direct_vs_transitive_differ():
    q = QueryEngine(_graph())
    assert _names(q.what_depends_on("C")) == ["Beta"]
    assert _names(q.what_depends_on("C", transitive=True)) != ["Beta"]

def test_depends_on_missing_node():
    q = QueryEngine(_graph())
    assert q.what_depends_on("ZZZ") == []

def test_transitive_excludes_self():
    q = QueryEngine(_graph())
    assert "Gamma" not in _names(q.what_depends_on("C", transitive=True))


# ---- what_does_it_depend_on ----

def test_depends_what_direct():
    q = QueryEngine(_graph())
    assert _names(q.what_does_it_depend_on("A")) == ["Beta"]

def test_depends_what_transitive():
    q = QueryEngine(_graph())
    assert _names(q.what_does_it_depend_on("A", transitive=True)) == ["Beta","Gamma"]

def test_depends_what_leaf():
    q = QueryEngine(_graph())
    assert q.what_does_it_depend_on("C") == []


# ---- find_path ----

def test_find_path_returns_edges_in_order():
    q = QueryEngine(_graph())
    path = q.find_path("A", "C")
    assert [(e.source_id, e.target_id) for e in path] == [("A","B"),("B","C")]
    assert path[1].attributes["line_numbers"] == [20,21]

def test_find_path_no_path():
    q = QueryEngine(_graph())
    assert q.find_path("C", "A") == []

def test_find_path_missing_node():
    q = QueryEngine(_graph())
    assert q.find_path("A", "ZZZ") == []

def test_find_path_same_node():
    q = QueryEngine(_graph())
    assert q.find_path("A", "A") == []


# ---- find_by_name ----

def test_find_by_name_substring_ci():
    q = QueryEngine(_graph())
    assert _names(q.find_by_name("ALP")) == ["Alpha"]

def test_find_by_name_exact():
    q = QueryEngine(_graph())
    assert _names(q.find_by_name("alpha", exact=True)) == ["Alpha"]
    assert q.find_by_name("alph", exact=True) == []

def test_find_by_name_multiple_sorted():
    g = _graph()
    g.add_node(_node("F","AlphaTwo"))
    q = QueryEngine(g)
    assert _names(q.find_by_name("alpha")) == ["Alpha","AlphaTwo"]


# ---- health checks ----

def test_find_orphaned():
    q = QueryEngine(_graph())
    assert _names(q.find_orphaned()) == ["Delta"]

def test_find_never_referenced():
    q = QueryEngine(_graph())
    assert _names(q.find_never_referenced()) == ["Alpha","Epsilon"]

def test_orphan_and_never_referenced_are_disjoint():
    q = QueryEngine(_graph())
    orphans = {n.id for n in q.find_orphaned()}
    never = {n.id for n in q.find_never_referenced()}
    assert orphans.isdisjoint(never)


# ---- find_never_referenced with exclude_tests ----

def _graph_with_test_nodes():
    g = MetadataGraph()
    g.add_node(_node("A", "PricingFlowAction", is_test=False))
    g.add_node(_node("B", "AccountServiceTest", is_test=True))
    g.add_node(_node("C", "BaseService", is_test=False))
    g.add_edge(_edge("A", "C", [1]))
    g.add_edge(_edge("B", "C", [2]))
    return g


def test_never_referenced_includes_tests_by_default():
    q = QueryEngine(_graph_with_test_nodes())
    names = _names(q.find_never_referenced())
    assert "PricingFlowAction" in names
    assert "AccountServiceTest" in names


def test_never_referenced_exclude_tests_filters_test_nodes():
    q = QueryEngine(_graph_with_test_nodes())
    names = _names(q.find_never_referenced(exclude_tests=True))
    assert "PricingFlowAction" in names
    assert "AccountServiceTest" not in names


def test_never_referenced_exclude_tests_empty_when_all_tests():
    g = MetadataGraph()
    g.add_node(_node("A", "OnlyTestClass", is_test=True))
    g.add_node(_node("B", "Target", is_test=False))
    g.add_edge(_edge("A", "B", [1]))
    q = QueryEngine(g)
    assert q.find_never_referenced(exclude_tests=True) == []


def test_never_referenced_exclude_tests_false_is_same_as_default():
    q = QueryEngine(_graph_with_test_nodes())
    assert (q.find_never_referenced(exclude_tests=False) ==
            q.find_never_referenced())


# ---- incoming_edges (Week 7 Day 4 — impact view) ----

def _impact_graph():
    """Object node touched by two classes via different edge types.

    OppSelector --USES_OBJECT(soql)--> Opportunity
    OppDomain   --USES_OBJECT(soql)--> Opportunity
    Caller      --CALLS(run)+REFERENCES--> Helper  (parallel edges)
    """
    g = MetadataGraph()
    g.add_node(_node("01p1", "OppSelector"))
    g.add_node(_node("01p2", "OppDomain"))
    g.add_node(_node("obj:opportunity", "Opportunity", NodeType.OBJECT))
    g.add_node(_node("01p3", "Caller"))
    g.add_node(_node("01p4", "Helper"))

    g.add_edge(Edge(source_id="01p1", target_id="obj:opportunity",
                    edge_type=EdgeType.USES_OBJECT, attributes={"via": "soql"}))
    g.add_edge(Edge(source_id="01p2", target_id="obj:opportunity",
                    edge_type=EdgeType.USES_OBJECT, attributes={"via": "soql"}))
    # Parallel edges: Caller both REFERENCES and CALLS Helper
    g.add_edge(Edge(source_id="01p3", target_id="01p4",
                    edge_type=EdgeType.REFERENCES, attributes={"line_numbers": [1]}))
    g.add_edge(Edge(source_id="01p3", target_id="01p4",
                    edge_type=EdgeType.CALLS, attributes={"method": "run"}))
    return g


def test_incoming_edges_returns_all_in_edges():
    q = QueryEngine(_impact_graph())
    edges = q.incoming_edges("obj:opportunity")
    assert len(edges) == 2
    assert all(e.edge_type == EdgeType.USES_OBJECT for e in edges)


def test_incoming_edges_filtered_by_type():
    q = QueryEngine(_impact_graph())
    calls = q.incoming_edges("01p4", edge_type=EdgeType.CALLS)
    assert len(calls) == 1
    assert calls[0].attributes["method"] == "run"


def test_incoming_edges_returns_parallel_edges():
    # Helper has both a REFERENCES and a CALLS edge from Caller — both returned
    q = QueryEngine(_impact_graph())
    edges = q.incoming_edges("01p4")
    types = {e.edge_type for e in edges}
    assert types == {EdgeType.REFERENCES, EdgeType.CALLS}
    assert len(edges) == 2


def test_incoming_edges_missing_node():
    q = QueryEngine(_impact_graph())
    assert q.incoming_edges("nonexistent") == []


def test_incoming_edges_no_in_edges():
    # OppSelector has only out-edges, no in-edges
    q = QueryEngine(_impact_graph())
    assert q.incoming_edges("01p1") == []


def test_incoming_edges_preserves_attributes():
    q = QueryEngine(_impact_graph())
    edges = q.incoming_edges("obj:opportunity")
    assert all(e.attributes.get("via") == "soql" for e in edges)
