"""Hermetic tests for GraphBuilder (Week 6 Day 2 + Week 7 Day 3 additions)."""
import pytest
from pydantic import BaseModel

from app.intelligence.graph.storage import MetadataCache
from app.intelligence.graph.builder import GraphBuilder
from app.intelligence.graph.models import NodeType, EdgeType

ORG = "https://test.my.salesforce.com"


class _Rec(BaseModel):
    Id: str
    Name: str
    Body: str | None = None


async def _cache(tmp_path):
    c = MetadataCache(tmp_path / "g.db")
    await c.init_schema()
    return c


# ------------------------------------------------------------------
# Week 6 — Apex node + REFERENCES edge tests
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_empty_cache_empty_graph(tmp_path):
    g = await GraphBuilder(await _cache(tmp_path)).build(org_key=ORG)
    s = g.stats()
    assert s.node_count == 0 and s.edge_count == 0


@pytest.mark.asyncio
async def test_one_node_per_record(tmp_path):
    c = await _cache(tmp_path)
    await c.put(org_key=ORG, metadata_type="ApexClass", records=[
        _Rec(Id="01p1", Name="Alpha", Body="public class Alpha {}"),
        _Rec(Id="01p2", Name="Beta", Body="public class Beta {}"),
    ])
    g = await GraphBuilder(c).build(org_key=ORG)
    assert g.stats().node_count == 2
    assert g.get_node("01p1").node_type == NodeType.APEX_CLASS


@pytest.mark.asyncio
async def test_reference_creates_edge_with_direction(tmp_path):
    c = await _cache(tmp_path)
    await c.put(org_key=ORG, metadata_type="ApexClass", records=[
        _Rec(Id="01p1", Name="AccountService",
             Body="public class AccountService {\n  GeneralUtils.log('x');\n}"),
        _Rec(Id="01p2", Name="GeneralUtils",
             Body="public class GeneralUtils { public static void log(String s){} }"),
    ])
    g = await GraphBuilder(c).build(org_key=ORG)
    succ = {n.id for n in g.successors("01p1")}
    assert succ == {"01p2"}
    pred = {n.id for n in g.predecessors("01p2")}
    assert pred == {"01p1"}


@pytest.mark.asyncio
async def test_self_reference_excluded(tmp_path):
    c = await _cache(tmp_path)
    await c.put(org_key=ORG, metadata_type="ApexClass", records=[
        _Rec(Id="01p1", Name="Loner", Body="public class Loner {\n  Integer x = 1;\n}"),
    ])
    g = await GraphBuilder(c).build(org_key=ORG)
    assert g.stats().edge_count == 0


@pytest.mark.asyncio
async def test_orphan_has_no_edges(tmp_path):
    c = await _cache(tmp_path)
    await c.put(org_key=ORG, metadata_type="ApexClass", records=[
        _Rec(Id="01p1", Name="Connected", Body="Helper.run();"),
        _Rec(Id="01p2", Name="Helper", Body="public class Helper { static void run(){} }"),
        _Rec(Id="01p3", Name="Orphan", Body="public class Orphan { Integer y; }"),
    ])
    g = await GraphBuilder(c).build(org_key=ORG)
    assert g.successors("01p3") == []
    assert g.predecessors("01p3") == []
    assert g.stats().node_count == 3


@pytest.mark.asyncio
async def test_edge_attributes_carry_lines_and_count(tmp_path):
    c = await _cache(tmp_path)
    await c.put(org_key=ORG, metadata_type="ApexClass", records=[
        _Rec(Id="01p1", Name="Caller", Body="Helper.a();\nHelper.b();\n// done"),
        _Rec(Id="01p2", Name="Helper", Body="public class Helper {}"),
    ])
    g = await GraphBuilder(c).build(org_key=ORG)
    ref_edges = [e for e in g.all_edges() if e.edge_type == EdgeType.REFERENCES]
    assert len(ref_edges) >= 1
    edge = ref_edges[0]
    assert edge.source_id == "01p1" and edge.target_id == "01p2"
    assert edge.attributes["line_numbers"] == [1, 2]
    assert edge.attributes["match_count"] == 2


@pytest.mark.asyncio
async def test_trigger_to_class_edge(tmp_path):
    c = await _cache(tmp_path)
    await c.put(org_key=ORG, metadata_type="ApexClass", records=[
        _Rec(Id="01p1", Name="MetadataTriggerHandler",
             Body="public class MetadataTriggerHandler {}"),
    ])
    await c.put(org_key=ORG, metadata_type="ApexTrigger", records=[
        _Rec(Id="01q1", Name="AccountTrigger",
             Body="trigger AccountTrigger on Account (before insert) {\n  new MetadataTriggerHandler().run();\n}"),
    ])
    g = await GraphBuilder(c).build(org_key=ORG)
    succ = {n.id for n in g.successors("01q1")}
    assert "01p1" in succ
    assert g.get_node("01q1").node_type == NodeType.APEX_TRIGGER


@pytest.mark.asyncio
async def test_word_boundary_no_false_edge(tmp_path):
    c = await _cache(tmp_path)
    await c.put(org_key=ORG, metadata_type="ApexClass", records=[
        _Rec(Id="01p1", Name="AccountService", Body="public class AccountService {}"),
        _Rec(Id="01p2", Name="Other",
             Body="public class Other { AccountServiceImpl impl; }"),
    ])
    g = await GraphBuilder(c).build(org_key=ORG)
    assert g.predecessors("01p1") == []


@pytest.mark.asyncio
async def test_case_insensitive_edge(tmp_path):
    c = await _cache(tmp_path)
    await c.put(org_key=ORG, metadata_type="ApexClass", records=[
        _Rec(Id="01p1", Name="Helper", Body="public class Helper {}"),
        _Rec(Id="01p2", Name="Caller", Body="helper.run();"),
    ])
    g = await GraphBuilder(c).build(org_key=ORG)
    assert {n.id for n in g.predecessors("01p1")} == {"01p2"}


@pytest.mark.asyncio
async def test_stats_reflect_built_graph(tmp_path):
    c = await _cache(tmp_path)
    await c.put(org_key=ORG, metadata_type="ApexClass", records=[
        _Rec(Id="01p1", Name="A", Body="B.x();"),
        _Rec(Id="01p2", Name="B", Body="public class B {}"),
    ])
    await c.put(org_key=ORG, metadata_type="ApexTrigger", records=[
        _Rec(Id="01q1", Name="T", Body="trigger T on Account(before insert){ A.y(); }"),
    ])
    g = await GraphBuilder(c).build(org_key=ORG)
    s = g.stats()
    assert s.node_type_counts.get("ApexClass") == 2
    assert s.node_type_counts.get("ApexTrigger") == 1


@pytest.mark.asyncio
async def test_injected_analyzer_is_used(tmp_path):
    from app.intelligence.analyzer import ReferenceAnalyzer
    c = await _cache(tmp_path)
    await c.put(org_key=ORG, metadata_type="ApexClass", records=[
        _Rec(Id="01p1", Name="A", Body="B.x();"),
        _Rec(Id="01p2", Name="B", Body="public class B {}"),
    ])
    g = await GraphBuilder(c, analyzer=ReferenceAnalyzer(c)).build(org_key=ORG)
    assert g.stats().edge_count >= 1


@pytest.mark.asyncio
async def test_test_class_node_has_is_test_true(tmp_path):
    c = await _cache(tmp_path)
    await c.put(org_key=ORG, metadata_type="ApexClass", records=[
        _Rec(Id="01p1", Name="AccountServiceTest",
             Body="@isTest\npublic class AccountServiceTest {}"),
    ])
    g = await GraphBuilder(c).build(org_key=ORG)
    assert g.get_node("01p1").attributes["is_test"] is True


@pytest.mark.asyncio
async def test_non_test_class_node_has_is_test_false(tmp_path):
    c = await _cache(tmp_path)
    await c.put(org_key=ORG, metadata_type="ApexClass", records=[
        _Rec(Id="01p1", Name="AccountService", Body="public class AccountService {}"),
    ])
    g = await GraphBuilder(c).build(org_key=ORG)
    assert g.get_node("01p1").attributes["is_test"] is False


# ------------------------------------------------------------------
# Week 7 Day 3 — CALLS edges
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_calls_edge_created_for_method_call(tmp_path):
    c = await _cache(tmp_path)
    await c.put(org_key=ORG, metadata_type="ApexClass", records=[
        _Rec(Id="01p1", Name="OrderService",
             Body="public class OrderService { void run() { TriggerBase.execute(); } }"),
        _Rec(Id="01p2", Name="TriggerBase",
             Body="public class TriggerBase { public static void execute(){} }"),
    ])
    g = await GraphBuilder(c).build(org_key=ORG)
    calls_edges = [e for e in g.all_edges() if e.edge_type == EdgeType.CALLS]
    assert any(e.source_id == "01p1" and e.target_id == "01p2" for e in calls_edges)


@pytest.mark.asyncio
async def test_calls_edge_has_method_attribute(tmp_path):
    c = await _cache(tmp_path)
    await c.put(org_key=ORG, metadata_type="ApexClass", records=[
        _Rec(Id="01p1", Name="Caller",
             Body="public class Caller { void go() { Helper.process(); } }"),
        _Rec(Id="01p2", Name="Helper",
             Body="public class Helper { public static void process(){} }"),
    ])
    g = await GraphBuilder(c).build(org_key=ORG)
    calls_edges = [e for e in g.all_edges()
                   if e.edge_type == EdgeType.CALLS
                   and e.source_id == "01p1" and e.target_id == "01p2"]
    assert len(calls_edges) == 1
    assert calls_edges[0].attributes["method"] == "process"


@pytest.mark.asyncio
async def test_calls_edge_only_to_known_nodes(tmp_path):
    # UnknownClass is not in the graph — no CALLS edge should be created
    c = await _cache(tmp_path)
    await c.put(org_key=ORG, metadata_type="ApexClass", records=[
        _Rec(Id="01p1", Name="Caller",
             Body="public class Caller { void go() { UnknownClass.run(); } }"),
    ])
    g = await GraphBuilder(c).build(org_key=ORG)
    calls_edges = [e for e in g.all_edges() if e.edge_type == EdgeType.CALLS]
    assert calls_edges == []


@pytest.mark.asyncio
async def test_no_calls_self_edge(tmp_path):
    c = await _cache(tmp_path)
    await c.put(org_key=ORG, metadata_type="ApexClass", records=[
        _Rec(Id="01p1", Name="MyService",
             Body="public class MyService { void go() { MyService.helper(); } }"),
    ])
    g = await GraphBuilder(c).build(org_key=ORG)
    self_edges = [e for e in g.all_edges()
                  if e.source_id == "01p1" and e.target_id == "01p1"]
    assert self_edges == []


# ------------------------------------------------------------------
# Week 7 Day 3 — Object nodes + USES_OBJECT edges
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_object_node_created_from_soql(tmp_path):
    c = await _cache(tmp_path)
    await c.put(org_key=ORG, metadata_type="ApexClass", records=[
        _Rec(Id="01p1", Name="AccountSelector",
             Body="public class AccountSelector { "
                  "List<Account> run() { return [SELECT Id FROM Account]; } }"),
    ])
    g = await GraphBuilder(c).build(org_key=ORG)
    obj_node = g.get_node("obj:account")
    assert obj_node is not None
    assert obj_node.node_type == NodeType.OBJECT
    assert obj_node.attributes["source"] == "derived"


@pytest.mark.asyncio
async def test_uses_object_edge_created(tmp_path):
    c = await _cache(tmp_path)
    await c.put(org_key=ORG, metadata_type="ApexClass", records=[
        _Rec(Id="01p1", Name="AccountSelector",
             Body="List<Account> run() { return [SELECT Id FROM Account]; }"),
    ])
    g = await GraphBuilder(c).build(org_key=ORG)
    uses_edges = [e for e in g.all_edges() if e.edge_type == EdgeType.USES_OBJECT]
    assert any(e.source_id == "01p1" and e.target_id == "obj:account"
               for e in uses_edges)


@pytest.mark.asyncio
async def test_noise_tokens_not_created_as_object_nodes(tmp_path):
    # 'the', 'elements' are SOQL noise — should not become Object nodes
    c = await _cache(tmp_path)
    await c.put(org_key=ORG, metadata_type="ApexClass", records=[
        _Rec(Id="01p1", Name="MyClass",
             Body="// inherited FROM the base\nList<Account> a = [SELECT Id FROM Account];"),
    ])
    g = await GraphBuilder(c).build(org_key=ORG)
    assert g.get_node("obj:the") is None
    assert g_node_exists(g, NodeType.OBJECT, "Account")


@pytest.mark.asyncio
async def test_object_node_deduplicates_across_classes(tmp_path):
    # Two classes querying Account should produce only one Account node
    c = await _cache(tmp_path)
    await c.put(org_key=ORG, metadata_type="ApexClass", records=[
        _Rec(Id="01p1", Name="ClassA",
             Body="List<Account> a = [SELECT Id FROM Account];"),
        _Rec(Id="01p2", Name="ClassB",
             Body="List<Account> b = [SELECT Name FROM Account];"),
    ])
    g = await GraphBuilder(c).build(org_key=ORG)
    object_nodes = [n for n in g.all_nodes() if n.node_type == NodeType.OBJECT]
    account_nodes = [n for n in object_nodes if n.name == "Account"]
    assert len(account_nodes) == 1


# ------------------------------------------------------------------
# Helper
# ------------------------------------------------------------------

def g_node_exists(graph, node_type, name) -> bool:
    return any(
        n.node_type == node_type and n.name == name
        for n in graph.all_nodes()
    )
