# ============================================================
# PYTHON CODE
# ============================================================
"""Graph builder — turns the flat metadata cache into a MetadataGraph.

Four passes over the org's cached metadata:
  1. NODES:        one Node per cached ApexClass/ApexTrigger record.
                   Each node gets is_test from the classifier.
  2. REF EDGES:    REFERENCES edges via the ReferenceAnalyzer (string-scan).
  3. PARSER EDGES: Apex parser → derived Object nodes, CALLS (Apex→Apex),
                   USES_OBJECT (Apex→Object).
  4. FLOW EDGES:   Flow parser → Flow nodes + Flow→Object (USES_OBJECT),
                   Flow→Apex (CALLS), Flow→Flow (CALLS). Week 7 Day 5.

Edge direction: source → target.
  REFERENCES:  source mentions target (string-scan)
  CALLS:       source invokes target (Apex method call OR flow apex action OR subflow)
  USES_OBJECT: source queries/DMLs/triggers-on target object

ADR-009: REFERENCES edges reuse ReferenceAnalyzer.
ADR-010: Object nodes derived from parser output, not Tooling API.
ADR-011: MultiDiGraph — parallel typed edges coexist.
"""
from __future__ import annotations

from app.intelligence.analyzer import ReferenceAnalyzer
from app.intelligence.code.apex_parser import parse_apex_body
from app.intelligence.code.flow_parser import parse_flow_xml
from app.intelligence.graph.classifier import is_test_class
from app.intelligence.graph.models import (
    Edge,
    EdgeType,
    MetadataGraph,
    Node,
    NodeType,
)
from app.intelligence.graph.storage import MetadataCache

_METADATA_TYPE_TO_NODE_TYPE: dict[str, NodeType] = {
    "ApexClass": NodeType.APEX_CLASS,
    "ApexTrigger": NodeType.APEX_TRIGGER,
}

DEFAULT_NODE_TYPES: tuple[str, ...] = tuple(_METADATA_TYPE_TO_NODE_TYPE)

_UNKNOWN_NAME = "<unknown>"
_MIN_OBJECT_NAME_LEN = 2

_SOQL_NOISE_TOKENS = frozenset({
    "the", "a", "an", "of", "in", "at", "by", "to", "is",
    "elements", "console", "within",
})


class GraphBuilder:
    """Builds a MetadataGraph from a MetadataCache for one org."""

    def __init__(
        self,
        cache: MetadataCache,
        analyzer: ReferenceAnalyzer | None = None,
    ) -> None:
        self._cache = cache
        self._analyzer = analyzer or ReferenceAnalyzer(cache)

    async def build(
        self,
        *,
        org_key: str,
        node_types: tuple[str, ...] = DEFAULT_NODE_TYPES,
    ) -> MetadataGraph:
        graph = MetadataGraph()
        await self._add_nodes(graph, org_key=org_key, node_types=node_types)
        await self._add_reference_edges(graph, org_key=org_key, node_types=node_types)
        await self._add_parser_edges(graph, org_key=org_key, node_types=node_types)
        await self._add_flow_edges(graph, org_key=org_key)
        return graph

    # ------------------------------------------------------------------
    # Pass 1 — Apex nodes
    # ------------------------------------------------------------------

    async def _add_nodes(
        self, graph: MetadataGraph, *, org_key: str, node_types: tuple[str, ...]
    ) -> None:
        for metadata_type in node_types:
            node_type = _METADATA_TYPE_TO_NODE_TYPE.get(metadata_type)
            if node_type is None:
                continue
            records = await self._cache.get(org_key=org_key, metadata_type=metadata_type)
            for rec in records:
                graph.add_node(
                    Node(
                        id=rec["Id"],
                        name=rec.get("Name") or rec.get("DeveloperName") or _UNKNOWN_NAME,
                        node_type=node_type,
                        org_key=org_key,
                        attributes={"is_test": is_test_class(rec)},
                    )
                )

    # ------------------------------------------------------------------
    # Pass 2 — REFERENCES edges (string-scan, ADR-009)
    # ------------------------------------------------------------------

    async def _add_reference_edges(
        self, graph: MetadataGraph, *, org_key: str, node_types: tuple[str, ...]
    ) -> None:
        for node in graph.all_nodes():
            if node.name == _UNKNOWN_NAME:
                continue
            report = await self._analyzer.find_references(
                org_key=org_key,
                identifier=node.name,
                metadata_types=node_types,
            )
            for ref in report.references:
                if ref.record_id == node.id:
                    continue
                if graph.get_node(ref.record_id) is None:
                    continue
                graph.add_edge(
                    Edge(
                        source_id=ref.record_id,
                        target_id=node.id,
                        edge_type=EdgeType.REFERENCES,
                        attributes={
                            "line_numbers": ref.line_numbers,
                            "match_count": ref.match_count,
                        },
                    )
                )

    # ------------------------------------------------------------------
    # Pass 3 — Apex parser: Object nodes + CALLS + USES_OBJECT
    # ------------------------------------------------------------------

    async def _add_parser_edges(
        self, graph: MetadataGraph, *, org_key: str, node_types: tuple[str, ...]
    ) -> None:
        for metadata_type in node_types:
            records = await self._cache.get(org_key=org_key, metadata_type=metadata_type)
            for rec in records:
                source_id = rec["Id"]
                if graph.get_node(source_id) is None:
                    continue
                body = rec.get("Body") or ""
                if not body.strip():
                    continue
                result = parse_apex_body(body)

                for class_ref in result.class_references:
                    target_node = self._find_node_by_name(graph, class_ref.class_name)
                    if target_node is None or target_node.id == source_id:
                        continue
                    graph.add_edge(
                        Edge(
                            source_id=source_id,
                            target_id=target_node.id,
                            edge_type=EdgeType.CALLS,
                            attributes={"method": class_ref.method_name},
                        )
                    )

                for soql_ref in result.soql_references:
                    obj_name = soql_ref.object_name
                    if not _is_valid_object_name(obj_name):
                        continue
                    obj_node = self._get_or_create_object_node(
                        graph, obj_name, org_key=org_key
                    )
                    if obj_node.id == source_id:
                        continue
                    graph.add_edge(
                        Edge(
                            source_id=source_id,
                            target_id=obj_node.id,
                            edge_type=EdgeType.USES_OBJECT,
                            attributes={"via": "soql"},
                        )
                    )

    # ------------------------------------------------------------------
    # Pass 4 — Flow parser: Flow nodes + Flow→Object/Apex/Flow edges
    # ------------------------------------------------------------------

    async def _add_flow_edges(self, graph: MetadataGraph, *, org_key: str) -> None:
        """Create Flow nodes and their edges from cached Flow XML.

        Two sub-passes: first create ALL Flow nodes (so Flow→Flow subflow
        edges can target nodes that may be parsed later), then add edges.

        Edges:
          Flow→Object : USES_OBJECT (via="flow_trigger"), the triggering object
          Flow→Apex   : CALLS (via="flow_action"), apex invocable actions
          Flow→Flow   : CALLS (via="subflow"), subflow invocations
        """
        flow_records = await self._cache.get(org_key=org_key, metadata_type="Flow")
        if not flow_records:
            return

        # Sub-pass A: create every Flow node first (id = flow:<name casefold>).
        # Keeps Flow→Flow edges resolvable regardless of parse order.
        for rec in flow_records:
            name = rec.get("DeveloperName") or _UNKNOWN_NAME
            graph.add_node(
                Node(
                    id=_flow_node_id(name),
                    name=name,
                    node_type=NodeType.FLOW,
                    org_key=org_key,
                    attributes={"is_test": False, "source": "extracted"},
                )
            )

        # Sub-pass B: parse each Flow's XML and add edges.
        for rec in flow_records:
            name = rec.get("DeveloperName") or _UNKNOWN_NAME
            source_id = _flow_node_id(name)
            xml = rec.get("xml") or ""
            if not xml.strip():
                continue
            result = parse_flow_xml(xml)

            # Flow → Object (triggering object)
            if result.triggering_object and _is_valid_object_name(result.triggering_object):
                obj_node = self._get_or_create_object_node(
                    graph, result.triggering_object, org_key=org_key
                )
                graph.add_edge(
                    Edge(
                        source_id=source_id,
                        target_id=obj_node.id,
                        edge_type=EdgeType.USES_OBJECT,
                        attributes={"via": "flow_trigger"},
                    )
                )

            # Flow → Apex (apex invocable actions)
            for apex_ref in result.apex_actions:
                target_node = self._find_node_by_name(graph, apex_ref.apex_class_name)
                if target_node is None:
                    continue  # only edge to known Apex nodes
                graph.add_edge(
                    Edge(
                        source_id=source_id,
                        target_id=target_node.id,
                        edge_type=EdgeType.CALLS,
                        attributes={"via": "flow_action", "action": apex_ref.action_label},
                    )
                )

            # Flow → Flow (subflows)
            for sub_ref in result.subflows:
                target_id = _flow_node_id(sub_ref.flow_name)
                if graph.get_node(target_id) is None:
                    continue  # subflow not among active flows we cached
                if target_id == source_id:
                    continue
                graph.add_edge(
                    Edge(
                        source_id=source_id,
                        target_id=target_id,
                        edge_type=EdgeType.CALLS,
                        attributes={"via": "subflow", "action": sub_ref.action_label},
                    )
                )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _find_node_by_name(self, graph: MetadataGraph, name: str) -> Node | None:
        name_lower = name.casefold()
        for node in graph.all_nodes():
            if node.name.casefold() == name_lower:
                return node
        return None

    def _get_or_create_object_node(
        self, graph: MetadataGraph, name: str, *, org_key: str
    ) -> Node:
        node_id = f"obj:{name.casefold()}"
        existing = graph.get_node(node_id)
        if existing is not None:
            return existing
        node = Node(
            id=node_id,
            name=name,
            node_type=NodeType.OBJECT,
            org_key=org_key,
            attributes={"source": "derived", "is_test": False},
        )
        graph.add_node(node)
        return node


def _is_valid_object_name(name: str) -> bool:
    if len(name) < _MIN_OBJECT_NAME_LEN:
        return False
    if name.casefold() in _SOQL_NOISE_TOKENS:
        return False
    return True


def _flow_node_id(name: str) -> str:
    """Synthetic node id for a Flow, parallel to obj: ids for derived objects."""
    return f"flow:{name.casefold()}"


# ============================================================
# APEX EQUIVALENT (for comparison)
# ============================================================
# Pass 4 (Flow edges) in Apex would parse the cached Flow XML (Dom.Document)
# and add edges to the adjacency map, same shape as passes 2-3:
#
#    for (Metadata_Cache__c rec : flowRecords) {
#        FlowParseResult pr = FlowParser.parse(rec.Xml__c);
#        Id flowNodeId = 'flow:' + rec.Display_Name__c.toLowerCase();
#        if (pr.triggeringObject != null) {
#            Id objId = getOrCreateObjectNode(pr.triggeringObject);
#            addEdge(flowNodeId, objId, 'USES_OBJECT'); // via flow_trigger
#        }
#        for (ApexActionRef a : pr.apexActions) {
#            Node target = findByName(a.apexClassName);
#            if (target != null) addEdge(flowNodeId, target.id, 'CALLS'); // flow_action
#        }
#        for (SubflowRef s : pr.subflows) {
#            Id targetId = 'flow:' + s.flowName.toLowerCase();
#            if (nodeExists(targetId)) addEdge(flowNodeId, targetId, 'CALLS'); // subflow
#        }
#    }
#
# Concept mapping:
# - _flow_node_id('X') = 'flow:x'        → 'flow:' + name.toLowerCase()
# - two-sub-pass (nodes then edges)       → same: create all flow nodes, then edges
#   so Flow→Flow subflow targets resolve regardless of order
# - parse_flow_xml(xml)                   → FlowParser.parse(xml) (Dom.Document)
# - EdgeType.CALLS reused for apex+subflow → same edge type, 'via' attribute distinguishes
# ============================================================
