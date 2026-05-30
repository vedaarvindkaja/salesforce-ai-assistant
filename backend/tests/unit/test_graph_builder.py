"""Hermetic tests for GraphBuilder (Week 6 Day 2 + Week 7 Day 3/5 additions)."""
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


class _FlowRec(BaseModel):
    Id: str
    DeveloperName: str
    xml: str


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
    calls = [e for e in g.all_edges() if e.edge_type == EdgeType.CALLS]
    assert any(e.source_id == "01p1" and e.target_id == "01p2" for e in calls)


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
    calls = [e for e in g.all_edges()
             if e.edge_type == EdgeType.CALLS
             and e.source_id == "01p1" and e.target_id == "01p2"]
    assert len(calls) == 1 and calls[0].attributes["method"] == "process"


@pytest.mark.asyncio
async def test_calls_edge_only_to_known_nodes(tmp_path):
    c = await _cache(tmp_path)
    await c.put(org_key=ORG, metadata_type="ApexClass", records=[
        _Rec(Id="01p1", Name="Caller",
             Body="public class Caller { void go() { UnknownClass.run(); } }"),
    ])
    g = await GraphBuilder(c).build(org_key=ORG)
    assert [e for e in g.all_edges() if e.edge_type == EdgeType.CALLS] == []


@pytest.mark.asyncio
async def test_no_calls_self_edge(tmp_path):
    c = await _cache(tmp_path)
    await c.put(org_key=ORG, metadata_type="ApexClass", records=[
        _Rec(Id="01p1", Name="MyService",
             Body="public class MyService { void go() { MyService.helper(); } }"),
    ])
    g = await GraphBuilder(c).build(org_key=ORG)
    assert [e for e in g.all_edges()
            if e.source_id == "01p1" and e.target_id == "01p1"] == []


# ------------------------------------------------------------------
# Week 7 Day 3 — Object nodes + USES_OBJECT edges
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_object_node_created_from_soql(tmp_path):
    c = await _cache(tmp_path)
    await c.put(org_key=ORG, metadata_type="ApexClass", records=[
        _Rec(Id="01p1", Name="AccountSelector",
             Body="List<Account> run() { return [SELECT Id FROM Account]; }"),
    ])
    g = await GraphBuilder(c).build(org_key=ORG)
    obj = g.get_node("obj:account")
    assert obj is not None and obj.node_type == NodeType.OBJECT
    assert obj.attributes["source"] == "derived"


@pytest.mark.asyncio
async def test_uses_object_edge_created(tmp_path):
    c = await _cache(tmp_path)
    await c.put(org_key=ORG, metadata_type="ApexClass", records=[
        _Rec(Id="01p1", Name="AccountSelector",
             Body="List<Account> run() { return [SELECT Id FROM Account]; }"),
    ])
    g = await GraphBuilder(c).build(org_key=ORG)
    uses = [e for e in g.all_edges() if e.edge_type == EdgeType.USES_OBJECT]
    assert any(e.source_id == "01p1" and e.target_id == "obj:account" for e in uses)


@pytest.mark.asyncio
async def test_object_node_deduplicates_across_classes(tmp_path):
    c = await _cache(tmp_path)
    await c.put(org_key=ORG, metadata_type="ApexClass", records=[
        _Rec(Id="01p1", Name="ClassA", Body="List<Account> a = [SELECT Id FROM Account];"),
        _Rec(Id="01p2", Name="ClassB", Body="List<Account> b = [SELECT Name FROM Account];"),
    ])
    g = await GraphBuilder(c).build(org_key=ORG)
    accounts = [n for n in g.all_nodes()
                if n.node_type == NodeType.OBJECT and n.name == "Account"]
    assert len(accounts) == 1


# ------------------------------------------------------------------
# Week 7 Day 5 — Flow nodes + Flow edges
# ------------------------------------------------------------------

_FLOW_NS = 'xmlns="http://soap.sforce.com/2006/04/metadata"'

def _flow_xml(*, obj=None, apex=None, subflow=None):
    parts = [f'<records {_FLOW_NS}>', '<processType>AutoLaunchedFlow</processType>']
    if obj:
        parts.append(f'<start><object>{obj}</object><triggerType>RecordAfterSave</triggerType></start>')
    if apex:
        parts.append(
            f'<actionCalls><name>act</name><actionName>{apex}</actionName>'
            f'<actionType>apex</actionType></actionCalls>'
        )
    if subflow:
        parts.append(f'<subflows><name>sub</name><flowName>{subflow}</flowName></subflows>')
    parts.append('</records>')
    return "".join(parts)


@pytest.mark.asyncio
async def test_flow_node_created(tmp_path):
    c = await _cache(tmp_path)
    await c.put(org_key=ORG, metadata_type="Flow", records=[
        _FlowRec(Id="300a", DeveloperName="My_Flow", xml=_flow_xml(obj="Opportunity")),
    ])
    g = await GraphBuilder(c).build(org_key=ORG)
    node = g.get_node("flow:my_flow")
    assert node is not None and node.node_type == NodeType.FLOW
    assert node.name == "My_Flow"


@pytest.mark.asyncio
async def test_flow_to_object_edge(tmp_path):
    c = await _cache(tmp_path)
    await c.put(org_key=ORG, metadata_type="Flow", records=[
        _FlowRec(Id="300a", DeveloperName="My_Flow", xml=_flow_xml(obj="Opportunity")),
    ])
    g = await GraphBuilder(c).build(org_key=ORG)
    uses = [e for e in g.all_edges() if e.edge_type == EdgeType.USES_OBJECT]
    assert any(e.source_id == "flow:my_flow" and e.target_id == "obj:opportunity"
               and e.attributes.get("via") == "flow_trigger" for e in uses)


@pytest.mark.asyncio
async def test_flow_to_apex_edge(tmp_path):
    c = await _cache(tmp_path)
    await c.put(org_key=ORG, metadata_type="ApexClass", records=[
        _Rec(Id="01p1", Name="PricingFlowAction", Body="public class PricingFlowAction {}"),
    ])
    await c.put(org_key=ORG, metadata_type="Flow", records=[
        _FlowRec(Id="300a", DeveloperName="My_Flow", xml=_flow_xml(apex="PricingFlowAction")),
    ])
    g = await GraphBuilder(c).build(org_key=ORG)
    calls = [e for e in g.all_edges() if e.edge_type == EdgeType.CALLS]
    assert any(e.source_id == "flow:my_flow" and e.target_id == "01p1"
               and e.attributes.get("via") == "flow_action" for e in calls)


@pytest.mark.asyncio
async def test_flow_to_apex_edge_only_to_known_class(tmp_path):
    # Apex action references a class not in the graph — no edge
    c = await _cache(tmp_path)
    await c.put(org_key=ORG, metadata_type="Flow", records=[
        _FlowRec(Id="300a", DeveloperName="My_Flow", xml=_flow_xml(apex="GhostClass")),
    ])
    g = await GraphBuilder(c).build(org_key=ORG)
    assert [e for e in g.all_edges() if e.edge_type == EdgeType.CALLS] == []


@pytest.mark.asyncio
async def test_flow_to_subflow_edge(tmp_path):
    c = await _cache(tmp_path)
    await c.put(org_key=ORG, metadata_type="Flow", records=[
        _FlowRec(Id="300a", DeveloperName="Parent_Flow", xml=_flow_xml(subflow="Child_Flow")),
        _FlowRec(Id="300b", DeveloperName="Child_Flow", xml=_flow_xml(obj="Opportunity")),
    ])
    g = await GraphBuilder(c).build(org_key=ORG)
    calls = [e for e in g.all_edges() if e.edge_type == EdgeType.CALLS]
    assert any(e.source_id == "flow:parent_flow" and e.target_id == "flow:child_flow"
               and e.attributes.get("via") == "subflow" for e in calls)


@pytest.mark.asyncio
async def test_flow_subflow_to_unknown_flow_no_edge(tmp_path):
    # Subflow target not among cached flows — no edge
    c = await _cache(tmp_path)
    await c.put(org_key=ORG, metadata_type="Flow", records=[
        _FlowRec(Id="300a", DeveloperName="Parent_Flow", xml=_flow_xml(subflow="Missing_Flow")),
    ])
    g = await GraphBuilder(c).build(org_key=ORG)
    assert [e for e in g.all_edges() if e.attributes.get("via") == "subflow"] == []


@pytest.mark.asyncio
async def test_flow_node_count_in_stats(tmp_path):
    c = await _cache(tmp_path)
    await c.put(org_key=ORG, metadata_type="Flow", records=[
        _FlowRec(Id="300a", DeveloperName="Flow_A", xml=_flow_xml(obj="Account")),
        _FlowRec(Id="300b", DeveloperName="Flow_B", xml=_flow_xml(obj="Contact")),
    ])
    g = await GraphBuilder(c).build(org_key=ORG)
    assert g.stats().node_type_counts.get("Flow") == 2


@pytest.mark.asyncio
async def test_flow_with_no_object_still_creates_node(tmp_path):
    # Autolaunched flow with no start object (the Evaluate_Pricing_Need case)
    c = await _cache(tmp_path)
    await c.put(org_key=ORG, metadata_type="Flow", records=[
        _FlowRec(Id="300a", DeveloperName="Subflow_Only", xml=_flow_xml()),
    ])
    g = await GraphBuilder(c).build(org_key=ORG)
    assert g.get_node("flow:subflow_only") is not None
    # No USES_OBJECT edge since no triggering object
    uses = [e for e in g.all_edges()
            if e.edge_type == EdgeType.USES_OBJECT and e.source_id == "flow:subflow_only"]
    assert uses == []
