"""Hermetic tests for GraphBuilder (Week 6, Day 2)."""
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
    assert g.successors("01p1") == []


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
    edge = g.all_edges()[0]
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
    assert s.node_type_counts == {"ApexClass": 2, "ApexTrigger": 1}
    assert s.edge_type_counts == {"REFERENCES": 2}


@pytest.mark.asyncio
async def test_injected_analyzer_is_used(tmp_path):
    from app.intelligence.analyzer import ReferenceAnalyzer
    c = await _cache(tmp_path)
    await c.put(org_key=ORG, metadata_type="ApexClass", records=[
        _Rec(Id="01p1", Name="A", Body="B.x();"),
        _Rec(Id="01p2", Name="B", Body="public class B {}"),
    ])
    g = await GraphBuilder(c, analyzer=ReferenceAnalyzer(c)).build(org_key=ORG)
    assert g.stats().edge_count == 1