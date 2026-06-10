"""Hermetic tests for the orchestration tool handlers (Week 8 Day 2-3).

Reuses an _impact_graph shape carrying every edge flavour (SOQL, method call,
Flow action, Flow trigger, subflow) plus an orphan and a never-referenced node,
so each handler can be exercised against realistic structure without the
network. Day 3 adds get_source tests, which need a real (throwaway) cache whose
record ids line up with the graph node ids.

Handlers are async (ClaudeClient's ToolHandler contract), so every handler test
is marked asyncio even though the underlying QueryEngine is synchronous.

Week 12 Day 4: analyze_debug_log joins the always-built graph family, so the
catalogue is 7 and the no-cache set is 6.
"""
import pytest
from pydantic import BaseModel

from app.intelligence.graph.models import (
    Edge, EdgeType, MetadataGraph, Node, NodeType,
)
from app.intelligence.graph.query import QueryEngine
from app.intelligence.graph.storage import MetadataCache
from app.intelligence.orchestration.tool_definitions import (
    TOOL_SCHEMAS,
    build_tools,
)

ORG = "https://test.my.salesforce.com"


def _n(id, name, t=NodeType.APEX_CLASS, *, is_test=False):
    return Node(id=id, name=name, node_type=t, org_key=ORG,
                attributes={"is_test": is_test})


def _graph():
    """Covers every edge flavour, plus an orphan and a never-referenced node.

      OppSelector --USES_OBJECT(soql)--> Opportunity
      OppDomain   --USES_OBJECT(soql)--> Opportunity
      Caller      --CALLS(run)-------->  Helper
      My_Flow     --CALLS(flow_action)-> PricingFlowAction
      My_Flow     --USES_OBJECT(flow_trigger)-> Opportunity
      My_Flow     --CALLS(subflow)-----> Child_Flow
      OppSelectorTest --REFERENCES----> Helper
      DeadController : orphan (no edges in or out)
    """
    g = MetadataGraph()
    g.add_node(_n("01p1", "OppSelector"))
    g.add_node(_n("01p2", "OppDomain"))
    g.add_node(_n("obj:opportunity", "Opportunity", NodeType.OBJECT))
    g.add_node(_n("01p3", "Caller"))
    g.add_node(_n("01p4", "Helper"))
    g.add_node(_n("01p5", "PricingFlowAction"))
    g.add_node(_n("01p6", "DeadController"))
    g.add_node(_n("01t1", "OppSelectorTest", is_test=True))
    g.add_node(_n("01q1", "AccountTrigger", NodeType.APEX_TRIGGER))
    g.add_node(_n("flow:my_flow", "My_Flow", NodeType.FLOW))
    g.add_node(_n("flow:child_flow", "Child_Flow", NodeType.FLOW))

    g.add_edge(Edge(source_id="01p1", target_id="obj:opportunity",
                    edge_type=EdgeType.USES_OBJECT, attributes={"via": "soql"}))
    g.add_edge(Edge(source_id="01p2", target_id="obj:opportunity",
                    edge_type=EdgeType.USES_OBJECT, attributes={"via": "soql"}))
    g.add_edge(Edge(source_id="01p3", target_id="01p4",
                    edge_type=EdgeType.CALLS, attributes={"method": "run"}))
    g.add_edge(Edge(source_id="flow:my_flow", target_id="01p5",
                    edge_type=EdgeType.CALLS, attributes={"via": "flow_action"}))
    g.add_edge(Edge(source_id="flow:my_flow", target_id="obj:opportunity",
                    edge_type=EdgeType.USES_OBJECT, attributes={"via": "flow_trigger"}))
    g.add_edge(Edge(source_id="flow:my_flow", target_id="flow:child_flow",
                    edge_type=EdgeType.CALLS, attributes={"via": "subflow"}))
    g.add_edge(Edge(source_id="01t1", target_id="01p4",
                    edge_type=EdgeType.REFERENCES, attributes={"line_numbers": [1]}))
    return g


def _tools():
    """Graph-query tools only (no cache) — for the Day 2 handler tests."""
    g = _graph()
    _, handlers = build_tools(QueryEngine(g), g)
    return handlers


# --- cache-backed setup for get_source (Day 3) ---

class _Rec(BaseModel):
    Id: str
    Name: str
    Body: str | None = None


class _FlowRec(BaseModel):
    Id: str
    DeveloperName: str
    xml: str


async def _tools_with_cache(tmp_path):
    """Full tool set incl. get_source. Cache record ids/names line up with the
    graph nodes: Apex by id (01p4 = Helper), Flow by DeveloperName (My_Flow)."""
    g = _graph()
    cache = MetadataCache(tmp_path / "src.db")
    await cache.init_schema()
    await cache.put(org_key=ORG, metadata_type="ApexClass", records=[
        _Rec(Id="01p4", Name="Helper",
             Body="public class Helper { public static void run() {} }"),
    ])
    await cache.put(org_key=ORG, metadata_type="ApexTrigger", records=[
        _Rec(Id="01q1", Name="AccountTrigger",
             Body="trigger AccountTrigger on Account (before insert) {}"),
    ])
    await cache.put(org_key=ORG, metadata_type="Flow", records=[
        _FlowRec(Id="300x", DeveloperName="My_Flow",
                 xml="<Flow><start><object>Opportunity</object></start></Flow>"),
    ])
    _, handlers = build_tools(QueryEngine(g), g, cache, ORG)
    return handlers


# ------------------------------------------------------------------
# Schema sanity
# ------------------------------------------------------------------

def test_catalogue_count_and_names():
    names = {t["name"] for t in TOOL_SCHEMAS}
    assert names == {
        "find_dependencies", "find_references_to", "analyze_impact",
        "find_by_name", "graph_health", "analyze_debug_log", "get_source",
    }

def test_every_schema_has_required_keys():
    for t in TOOL_SCHEMAS:
        assert t["name"] and t["description"]
        assert t["input_schema"]["type"] == "object"
        assert "properties" in t["input_schema"]

def test_build_without_cache_excludes_get_source():
    g = _graph()
    schemas, handlers = build_tools(QueryEngine(g), g)
    names = {t["name"] for t in schemas}
    assert "get_source" not in names
    assert "get_source" not in handlers
    # analyze_debug_log is graph-family (no cache needed), so it is built here.
    assert "analyze_debug_log" in names
    assert len(names) == 6

@pytest.mark.asyncio
async def test_build_with_cache_includes_get_source(tmp_path):
    handlers = await _tools_with_cache(tmp_path)
    assert "get_source" in handlers


# ------------------------------------------------------------------
# find_dependencies — OUTWARD (what X uses)
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_find_dependencies_direct():
    out = await _tools()["find_dependencies"]({"name": "Caller"})
    assert "Helper" in out
    assert "1 direct" in out
    assert "via" in out  # Refinement #10: mechanism label now present

@pytest.mark.asyncio
async def test_find_dependencies_direct_includes_relation_label():
    # Caller → Helper via CALLS edge — label must be present, not just node name.
    out = await _tools()["find_dependencies"]({"name": "Caller"})
    # The fixture edge is a CALLS edge, so the label is "method call"
    assert "method call" in out

@pytest.mark.asyncio
async def test_find_dependencies_transitive_node_list_only():
    # Transitive output stays as node-list (no per-hop edge labels — noise at multi-hop).
    out = await _tools()["find_dependencies"]({"name": "Caller", "transitive": True})
    assert "Helper" in out
    assert "transitive" in out
    # Should NOT have via-labels in transitive mode
    assert "via" not in out

@pytest.mark.asyncio
async def test_find_dependencies_none():
    out = await _tools()["find_dependencies"]({"name": "Helper"})
    assert "depends on nothing" in out

@pytest.mark.asyncio
async def test_find_dependencies_unknown_name():
    out = await _tools()["find_dependencies"]({"name": "Ghost"})
    assert "No metadata named" in out


# ------------------------------------------------------------------
# find_references_to — INWARD (what uses X)
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_find_references_to_direct():
    # Helper is referenced by BOTH Caller (CALLS) and OppSelectorTest (REFERENCES)
    out = await _tools()["find_references_to"]({"name": "Helper"})
    assert "Caller" in out
    assert "OppSelectorTest" in out
    assert "2 direct dependent" in out

@pytest.mark.asyncio
async def test_find_references_to_none():
    out = await _tools()["find_references_to"]({"name": "OppSelector"})
    assert "Nothing depends on" in out

@pytest.mark.asyncio
async def test_find_references_to_transitive():
    out = await _tools()["find_references_to"]({"name": "Helper", "transitive": True})
    assert "Caller" in out


# ------------------------------------------------------------------
# Direction guard — the two must NOT be inverted
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dependencies_and_references_are_opposite_directions():
    tools = _tools()
    deps = await tools["find_dependencies"]({"name": "Caller"})
    refs = await tools["find_references_to"]({"name": "Helper"})
    assert "Helper" in deps
    assert "Caller" in refs
    assert "depends on nothing" in await tools["find_dependencies"]({"name": "Helper"})
    assert "Nothing depends on" in await tools["find_references_to"]({"name": "Caller"})


# ------------------------------------------------------------------
# analyze_impact — via-labels must match the CLI vocabulary
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_impact_soql_label():
    out = await _tools()["analyze_impact"]({"name": "Opportunity"})
    assert "OppSelector" in out and "OppDomain" in out
    assert "SOQL/DML query" in out
    assert "Flow trigger" in out

@pytest.mark.asyncio
async def test_impact_flow_action_label():
    out = await _tools()["analyze_impact"]({"name": "PricingFlowAction"})
    assert "My_Flow" in out
    assert "Flow action" in out
    assert "method call" not in out

@pytest.mark.asyncio
async def test_impact_method_call_detail():
    out = await _tools()["analyze_impact"]({"name": "Helper"})
    assert "Caller" in out
    assert "method call" in out
    assert "run()" in out

@pytest.mark.asyncio
async def test_impact_subflow_label():
    out = await _tools()["analyze_impact"]({"name": "Child_Flow"})
    assert "My_Flow" in out and "subflow" in out

@pytest.mark.asyncio
async def test_impact_nothing_touches():
    out = await _tools()["analyze_impact"]({"name": "OppSelector"})
    assert "Nothing touches" in out

@pytest.mark.asyncio
async def test_impact_unknown_name():
    out = await _tools()["analyze_impact"]({"name": "Ghost"})
    assert "No metadata named" in out


# ------------------------------------------------------------------
# find_by_name
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_find_by_name_substring():
    out = await _tools()["find_by_name"]({"query": "Opp"})
    assert "OppSelector" in out and "OppDomain" in out and "Opportunity" in out

@pytest.mark.asyncio
async def test_find_by_name_no_match():
    out = await _tools()["find_by_name"]({"query": "Nonexistent"})
    assert "No components match" in out


# ------------------------------------------------------------------
# graph_health
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_health_orphaned():
    out = await _tools()["graph_health"]({"check": "orphaned"})
    assert "DeadController" in out

@pytest.mark.asyncio
async def test_health_never_referenced_includes_tests_by_default():
    out = await _tools()["graph_health"]({"check": "never_referenced"})
    assert "OppSelectorTest" in out

@pytest.mark.asyncio
async def test_health_never_referenced_exclude_tests():
    out = await _tools()["graph_health"](
        {"check": "never_referenced", "exclude_tests": True}
    )
    assert "OppSelectorTest" not in out

@pytest.mark.asyncio
async def test_health_both_default():
    out = await _tools()["graph_health"]({})
    assert "orphaned" in out.lower()
    assert "never-referenced" in out.lower()


# ------------------------------------------------------------------
# get_source (Day 3) — cache-backed
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_source_apex_class(tmp_path):
    handlers = await _tools_with_cache(tmp_path)
    out = await handlers["get_source"]({"name": "Helper"})
    assert "Source of Helper" in out
    assert "public class Helper" in out

@pytest.mark.asyncio
async def test_get_source_apex_trigger(tmp_path):
    handlers = await _tools_with_cache(tmp_path)
    out = await handlers["get_source"]({"name": "AccountTrigger"})
    assert "trigger AccountTrigger" in out

@pytest.mark.asyncio
async def test_get_source_flow_returns_xml(tmp_path):
    handlers = await _tools_with_cache(tmp_path)
    out = await handlers["get_source"]({"name": "My_Flow"})
    assert "Flow XML of My_Flow" in out
    assert "<Flow>" in out

@pytest.mark.asyncio
async def test_get_source_object_has_no_source(tmp_path):
    handlers = await _tools_with_cache(tmp_path)
    out = await handlers["get_source"]({"name": "Opportunity"})
    assert "derived Object node" in out
    assert "no source" in out

@pytest.mark.asyncio
async def test_get_source_unknown_name(tmp_path):
    handlers = await _tools_with_cache(tmp_path)
    out = await handlers["get_source"]({"name": "Ghost"})
    assert "No metadata named" in out

@pytest.mark.asyncio
async def test_get_source_apex_no_body_cached(tmp_path):
    # Node exists in graph but no cache record → clear "no cached source".
    g = _graph()
    cache = MetadataCache(tmp_path / "empty.db")
    await cache.init_schema()  # schema but no records
    _, handlers = build_tools(QueryEngine(g), g, cache, ORG)
    out = await handlers["get_source"]({"name": "Caller"})
    assert "No cached source" in out

@pytest.mark.asyncio
async def test_get_source_truncates_large_body(tmp_path):
    g = _graph()
    cache = MetadataCache(tmp_path / "big.db")
    await cache.init_schema()
    big = "// x\n" * 5000  # ~25k chars, over the 12k cap
    await cache.put(org_key=ORG, metadata_type="ApexClass",
                    records=[_Rec(Id="01p4", Name="Helper", Body=big)])
    _, handlers = build_tools(QueryEngine(g), g, cache, ORG)
    out = await handlers["get_source"]({"name": "Helper"})
    assert "[truncated" in out
