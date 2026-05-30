# ============================================================
# PYTHON CODE
# ============================================================
"""Flow XML parser — extract structured facts from a Flow's Metadata XML.

Parses the raw <records> XML block returned by the Metadata API readMetadata
(see metadata_api.py) into structured references. Different from the Apex
parser: this is XML/ElementTree over well-formed nested markup, not regex
over free-form source.

Extracted facts (verified against real org Day 5):
  - triggering object   : <start><object>   (optional — some flows have none)
  - Apex actions invoked : <actionCalls> where <actionType>apex</actionType>,
                           target class = <actionName>
  - subflows called      : <subflows>, target flow = <flowName>

CRITICAL correctness rule (verified against real data): an <actionCalls>
block is only a Flow→Apex edge when <actionType> is 'apex'. Other actionTypes
(submit, emailAlert, chatterPost, ...) are standard platform actions, NOT
Apex — treating them as Apex would create phantom edges to non-existent
classes. The parser filters on actionType, same spirit as the Apex parser's
PascalCase / system-namespace noise filtering.

Pure function: takes the raw <records> XML string, returns a FlowParseResult.
No I/O, no cache, no graph dependency.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

# The Metadata API <records> block uses the Salesforce metadata namespace as
# the default xmlns. ElementTree prefixes every tag with {namespace}. We strip
# the namespace in _localname so callers match on plain tag names.
_METADATA_NS = "http://soap.sforce.com/2006/04/metadata"


@dataclass(frozen=True)
class ApexActionReference:
    """A Flow → Apex edge: the flow invokes an Apex invocable action."""
    apex_class_name: str   # <actionName> when <actionType> is 'apex'
    action_label: str      # <name> of the action node (for context)


@dataclass(frozen=True)
class SubflowReference:
    """A Flow → Flow edge: the flow calls another flow as a subflow."""
    flow_name: str         # <flowName>
    action_label: str      # <name> of the subflow node


@dataclass
class FlowParseResult:
    """Structured facts extracted from one Flow's XML.

    The parser reports what it sees; the builder decides what becomes
    nodes/edges. Lists are deduplicated and order-stable.
    """
    triggering_object: str | None = None   # <start><object>, may be absent
    process_type: str | None = None        # <processType>
    trigger_type: str | None = None        # <start><triggerType>, may be absent
    apex_actions: list[ApexActionReference] = field(default_factory=list)
    subflows: list[SubflowReference] = field(default_factory=list)

    @property
    def referenced_apex_classes(self) -> set[str]:
        return {a.apex_class_name for a in self.apex_actions}

    @property
    def referenced_subflows(self) -> set[str]:
        return {s.flow_name for s in self.subflows}


def _localname(tag: str) -> str:
    """Strip the {namespace} prefix ElementTree adds, leaving the plain tag."""
    return tag.split("}", 1)[-1] if "}" in tag else tag


def _find_child_text(elem: ET.Element, child_name: str) -> str | None:
    """First direct child with the given local name; its text, or None."""
    for child in elem:
        if _localname(child.tag) == child_name:
            text = (child.text or "").strip()
            return text or None
    return None


def _iter_children(elem: ET.Element, child_name: str):
    """All direct children with the given local name."""
    for child in elem:
        if _localname(child.tag) == child_name:
            yield child


def parse_flow_xml(xml: str) -> FlowParseResult:
    """Parse a Flow's <records> XML block into structured references.

    Args:
        xml: the raw <records>...</records> string from readMetadata.
             Empty/blank returns an empty result.

    Returns:
        FlowParseResult with triggering object, process/trigger type,
        Apex actions (actionType=apex only), and subflows.

    Namespace note: the Metadata API returns each <records> block carrying
    `xsi:type="Flow"`, but the `xsi` prefix is declared on the SOAP ENVELOPE,
    not the block. Since metadata_api.py extracts the bare <records> block,
    the `xsi` prefix is dangling and ElementTree rejects it ("unbound prefix").
    We defend against this by wrapping the fragment in a synthetic root that
    declares xsi, then descending to the records element. This keeps the parser
    robust to bare fragments regardless of how they were extracted.
    """
    if not xml or not xml.strip():
        return FlowParseResult()

    wrapped = (
        '<_flowroot xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
        + xml
        + "</_flowroot>"
    )
    try:
        wrapper = ET.fromstring(wrapped)
    except ET.ParseError:
        # Genuinely malformed XML — return empty rather than crash the build.
        return FlowParseResult()

    # The records element is the first child of the synthetic wrapper.
    root = None
    for child in wrapper:
        if _localname(child.tag) == "records":
            root = child
            break
    if root is None:
        # No <records> element (unexpected shape) — empty result.
        return FlowParseResult()

    result = FlowParseResult()
    result.process_type = _find_child_text(root, "processType")

    # <start><object> and <start><triggerType>
    for start in _iter_children(root, "start"):
        result.triggering_object = _find_child_text(start, "object")
        result.trigger_type = _find_child_text(start, "triggerType")
        break  # a flow has at most one <start>

    # <actionCalls> — Apex edges ONLY when actionType == 'apex'
    seen_apex: set[tuple[str, str]] = set()
    for ac in _iter_children(root, "actionCalls"):
        action_type = _find_child_text(ac, "actionType")
        if action_type != "apex":
            continue  # submit/emailAlert/etc. are not Flow→Apex edges
        apex_class = _find_child_text(ac, "actionName")
        if not apex_class:
            continue
        label = _find_child_text(ac, "name") or apex_class
        key = (apex_class.casefold(), label.casefold())
        if key not in seen_apex:
            seen_apex.add(key)
            result.apex_actions.append(
                ApexActionReference(apex_class_name=apex_class, action_label=label)
            )

    # <subflows> — Flow→Flow edges via <flowName>
    seen_sub: set[tuple[str, str]] = set()
    for sf in _iter_children(root, "subflows"):
        flow_name = _find_child_text(sf, "flowName")
        if not flow_name:
            continue
        label = _find_child_text(sf, "name") or flow_name
        key = (flow_name.casefold(), label.casefold())
        if key not in seen_sub:
            seen_sub.add(key)
            result.subflows.append(
                SubflowReference(flow_name=flow_name, action_label=label)
            )

    return result


# ============================================================
# APEX EQUIVALENT (for comparison)
# ============================================================
# In Apex you'd parse the Flow XML with the DOM classes (Dom.Document),
# or — if reading via the Metadata API from Apex — you'd get a strongly
# typed MetadataService.Flow and walk its fields directly.
#
#    Dom.Document doc = new Dom.Document();
#    doc.load(flowXml);
#    Dom.XmlNode root = doc.getRootElement();
#
#    // triggering object: root -> start -> object
#    Dom.XmlNode startNode = root.getChildElement('start', NS);
#    String triggerObject = (startNode != null)
#        ? startNode.getChildElement('object', NS)?.getText() : null;
#
#    // actionCalls with actionType == 'apex'
#    for (Dom.XmlNode ac : root.getChildElements()) {
#        if (ac.getName() != 'actionCalls') continue;
#        String actionType = ac.getChildElement('actionType', NS)?.getText();
#        if (actionType != 'apex') continue;            // the correctness rule
#        String apexClass = ac.getChildElement('actionName', NS)?.getText();
#        // -> Flow→Apex edge to apexClass
#    }
#
#    // subflows -> flowName
#    for (Dom.XmlNode sf : root.getChildElements()) {
#        if (sf.getName() != 'subflows') continue;
#        String target = sf.getChildElement('flowName', NS)?.getText();
#        // -> Flow→Flow edge to target
#    }
#
# Concept mapping:
# - xml.etree.ElementTree.fromstring   → Dom.Document().load(xml)
# - _localname (strip {ns} prefix)      → getName() returns local name already
# - _find_child_text(elem, 'object')   → node.getChildElement('object', ns).getText()
# - actionType == 'apex' filter         → identical guard (the key correctness rule)
# - @dataclass(frozen=True)             → Apex inner class with final-ish fields
# - set for dedup                       → Set<String> for dedup
# ============================================================
