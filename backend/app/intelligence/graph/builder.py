# ============================================================
# PYTHON CODE
# ============================================================
"""Graph builder — turns the flat metadata cache into a MetadataGraph.

Three passes over the org's cached metadata:
  1. NODES:        one Node per cached record (ApexClass, ApexTrigger).
                   Each node gets is_test attribute from the classifier.
  2. REF EDGES:    REFERENCES edges via the ReferenceAnalyzer (string-scan,
                   ADR-009). O(N²) body scans; fine at current scale.
  3. PARSER EDGES: run the Apex pattern parser over each Apex body to derive:
                   - Object nodes (SOQL FROM targets, NodeType.OBJECT)
                   - CALLS edges  (ApexClass → ApexClass method calls)
                   - USES_OBJECT edges (ApexClass → Object via SOQL/DML)
                   Object nodes are derived, not extracted (ADR-010).
                   They carry source="derived" for Phase 2 enrichment.

Edge direction: source → target.
  REFERENCES:  source mentions target (string-scan)
  CALLS:       source calls a method on target class (parser)
  USES_OBJECT: source queries/DMLs target object (parser)

ADR-009: REFERENCES edges reuse ReferenceAnalyzer (keeps matching semantics
identical). ADR-010: Object nodes derived from parser, not Tooling API.
"""
from __future__ import annotations

from app.intelligence.analyzer import ReferenceAnalyzer
from app.intelligence.code.apex_parser import parse_apex_body
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

# Minimum length for a derived object name to be graph-worthy.
# Filters single-character noise ('a', 'e') that slip through comment
# stripping from string literals.
_MIN_OBJECT_NAME_LEN = 2

# Known non-sObject tokens that occasionally appear after FROM even after
# comment stripping (string literals in test code, enum names, etc.).
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
    # Pass 3 — Parser-derived Object nodes + CALLS + USES_OBJECT edges
    # ------------------------------------------------------------------

    async def _add_parser_edges(
        self, graph: MetadataGraph, *, org_key: str, node_types: tuple[str, ...]
    ) -> None:
        """Run the Apex parser over every Apex body and derive:
          - Object nodes from SOQL FROM targets (NodeType.OBJECT, ADR-010)
          - CALLS edges: ApexClass → ApexClass (method call refs)
          - USES_OBJECT edges: ApexClass → Object (SOQL/DML refs)

        Object nodes are only created when the name passes basic sanity
        checks (_MIN_OBJECT_NAME_LEN, not in _SOQL_NOISE_TOKENS). They
        carry source='derived' so Phase 2 can enrich without rebuilding.
        """
        for metadata_type in node_types:
            records = await self._cache.get(org_key=org_key, metadata_type=metadata_type)
            for rec in records:
                source_id = rec["Id"]
                if graph.get_node(source_id) is None:
                    continue  # defensive: source must be a tracked node

                body = rec.get("Body") or ""
                if not body.strip():
                    continue

                result = parse_apex_body(body)

                # --- CALLS edges (ApexClass → ApexClass) ---
                for class_ref in result.class_references:
                    target_node = self._find_node_by_name(graph, class_ref.class_name)
                    if target_node is None:
                        continue  # only draw CALLS edges to known graph nodes
                    if target_node.id == source_id:
                        continue  # no self-edges
                    graph.add_edge(
                        Edge(
                            source_id=source_id,
                            target_id=target_node.id,
                            edge_type=EdgeType.CALLS,
                            attributes={"method": class_ref.method_name},
                        )
                    )

                # --- Object nodes + USES_OBJECT edges ---
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
    # Helpers
    # ------------------------------------------------------------------

    def _find_node_by_name(self, graph: MetadataGraph, name: str) -> Node | None:
        """Case-insensitive name lookup — returns first exact match or None."""
        name_lower = name.casefold()
        for node in graph.all_nodes():
            if node.name.casefold() == name_lower:
                return node
        return None

    def _get_or_create_object_node(
        self, graph: MetadataGraph, name: str, *, org_key: str
    ) -> Node:
        """Return the existing Object node for name, or create and add it.

        Derived nodes use name as id (no Salesforce Id available).
        source='derived' marks them for Phase 2 enrichment (ADR-010).
        """
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
    """Return True if name looks like a real sObject name, not noise."""
    if len(name) < _MIN_OBJECT_NAME_LEN:
        return False
    if name.casefold() in _SOQL_NOISE_TOKENS:
        return False
    return True


# ============================================================
# APEX EQUIVALENT (for comparison)
# ============================================================
#
#    public class GraphBuilder {
#
#        public MetadataGraph build(List<String> nodeTypes) {
#            // Pass 1: Apex nodes
#            List<Metadata_Cache__c> rows = [
#                SELECT Id, Name, Body__c, Metadata_Type__c
#                FROM Metadata_Cache__c
#                WHERE Metadata_Type__c IN :nodeTypes
#            ];
#            Map<Id, Node> nodesById = new Map<Id, Node>();
#            for (Metadata_Cache__c r : rows) {
#                Node n = new Node();
#                n.id = r.Id; n.name = r.Name;
#                n.attributes.put('is_test', ApexClassifier.isTestClass(r.Name, r.Body__c));
#                nodesById.put(r.Id, n);
#            }
#
#            // Pass 2: REFERENCES edges (string-scan)
#            // ... O(N^2) body scan loop (ADR-009) ...
#
#            // Pass 3: parser-derived Object nodes + CALLS + USES_OBJECT
# //            for (Metadata_Cache__c r : rows) {
# //                ParseResult pr = ApexBodyParser.parse(r.Body__c);
# //                for (ClassRef cr : pr.classRefs) {
# //                    Node target = findByName(nodesById, cr.className);
# //                    if (target != null) addEdge(r.Id, target.id, 'CALLS');
# //                }
# //                for (SoqlRef sr : pr.soqlRefs) {
# //                    if (!isValidObjectName(sr.objectName)) continue;
# //                    Node obj = getOrCreateObjectNode(sr.objectName);
# //                    addEdge(r.Id, obj.id, 'USES_OBJECT');
# //                }
# //            }
# //        }
# //    }
# //
# // Concept mapping:
# // - async def build()                → synchronous build() (no async in Apex)
# // - parse_apex_body(body)            → ApexBodyParser.parse(body) static call
# // - _get_or_create_object_node()     → getOrCreateObjectNode() helper method
# // - f"obj:{name.casefold()}"         → 'obj:' + name.toLowerCase() for derived id
# // - frozenset _SOQL_NOISE_TOKENS     → static final Set<String> (static initializer)
# // ============================================================
