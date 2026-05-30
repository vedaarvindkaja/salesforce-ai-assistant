"""Hermetic tests for the Flow XML parser (Week 7, Day 5).

Fixtures are modeled on REAL Flow XML captured from the dev org Day 5
(scripts/dump_flow_actions.py output) — so tests verify against the actual
Metadata API structure, not an assumed schema.
"""
import pytest

from app.intelligence.code.flow_parser import (
    ApexActionReference,
    FlowParseResult,
    SubflowReference,
    parse_flow_xml,
)


# Record-triggered flow with a start object, no actions/subflows.
RECORD_TRIGGERED = """<records xmlns="http://soap.sforce.com/2006/04/metadata" xsi:type="Flow">
  <fullName>Update_Contact_Phone</fullName>
  <processType>AutoLaunchedFlow</processType>
  <start>
    <object>Contact</object>
    <triggerType>RecordAfterSave</triggerType>
  </start>
</records>"""

# Flow with an apex actionCall (the real PricingFlowAction case).
WITH_APEX_ACTION = """<records xmlns="http://soap.sforce.com/2006/04/metadata" xsi:type="Flow">
  <fullName>Opportunity_Sales_Orchestration_Flow</fullName>
  <processType>AutoLaunchedFlow</processType>
  <start><object>Opportunity</object></start>
  <actionCalls>
    <name>getPricing</name>
    <actionName>PricingFlowAction</actionName>
    <actionType>apex</actionType>
  </actionCalls>
  <subflows>
    <name>Evalvate_Pricing</name>
    <flowName>Evaluate_Pricing_Need</flowName>
  </subflows>
</records>"""

# Flow whose only actionCall is a non-apex 'submit' (the real Approval case).
# Must NOT produce a Flow→Apex edge.
WITH_SUBMIT_ACTION = """<records xmlns="http://soap.sforce.com/2006/04/metadata" xsi:type="Flow">
  <fullName>Opportunity_Approval_Orchestrator</fullName>
  <processType>AutoLaunchedFlow</processType>
  <start><object>Opportunity</object></start>
  <actionCalls>
    <name>Submit_For_Approval</name>
    <actionName>submit</actionName>
    <actionType>submit</actionType>
  </actionCalls>
</records>"""

# Autolaunched flow with NO start object (the Evaluate_Pricing_Need case).
NO_START_OBJECT = """<records xmlns="http://soap.sforce.com/2006/04/metadata" xsi:type="Flow">
  <fullName>Evaluate_Pricing_Need</fullName>
  <processType>AutoLaunchedFlow</processType>
</records>"""


# ------------------------------------------------------------------
# Empty / malformed
# ------------------------------------------------------------------

def test_empty_xml_returns_empty_result():
    assert parse_flow_xml("") == FlowParseResult()

def test_whitespace_xml_returns_empty_result():
    assert parse_flow_xml("   \n  ") == FlowParseResult()

def test_malformed_xml_returns_empty_not_crash():
    result = parse_flow_xml("<records><unclosed>")
    assert result == FlowParseResult()


# ------------------------------------------------------------------
# Triggering object + metadata
# ------------------------------------------------------------------

def test_record_triggered_object():
    result = parse_flow_xml(RECORD_TRIGGERED)
    assert result.triggering_object == "Contact"
    assert result.trigger_type == "RecordAfterSave"
    assert result.process_type == "AutoLaunchedFlow"

def test_no_start_object_is_none():
    result = parse_flow_xml(NO_START_OBJECT)
    assert result.triggering_object is None
    assert result.trigger_type is None
    assert result.process_type == "AutoLaunchedFlow"


# ------------------------------------------------------------------
# Apex actions — the actionType=apex correctness rule
# ------------------------------------------------------------------

def test_apex_action_extracted():
    result = parse_flow_xml(WITH_APEX_ACTION)
    assert ApexActionReference(
        apex_class_name="PricingFlowAction", action_label="getPricing"
    ) in result.apex_actions

def test_apex_class_in_referenced_set():
    result = parse_flow_xml(WITH_APEX_ACTION)
    assert "PricingFlowAction" in result.referenced_apex_classes

def test_submit_action_NOT_treated_as_apex():
    # The critical correctness rule: actionType=submit is not a Flow→Apex edge
    result = parse_flow_xml(WITH_SUBMIT_ACTION)
    assert result.apex_actions == []
    assert result.referenced_apex_classes == set()

def test_submit_flow_still_has_object():
    # Even though no apex edge, the Flow→Object edge should still extract
    result = parse_flow_xml(WITH_SUBMIT_ACTION)
    assert result.triggering_object == "Opportunity"


# ------------------------------------------------------------------
# Subflows — Flow→Flow
# ------------------------------------------------------------------

def test_subflow_extracted():
    result = parse_flow_xml(WITH_APEX_ACTION)
    assert SubflowReference(
        flow_name="Evaluate_Pricing_Need", action_label="Evalvate_Pricing"
    ) in result.subflows

def test_subflow_in_referenced_set():
    result = parse_flow_xml(WITH_APEX_ACTION)
    assert "Evaluate_Pricing_Need" in result.referenced_subflows

def test_no_subflows_empty():
    result = parse_flow_xml(RECORD_TRIGGERED)
    assert result.subflows == []


# ------------------------------------------------------------------
# Combined / realistic
# ------------------------------------------------------------------

def test_full_flow_all_facts():
    result = parse_flow_xml(WITH_APEX_ACTION)
    assert result.triggering_object == "Opportunity"
    assert "PricingFlowAction" in result.referenced_apex_classes
    assert "Evaluate_Pricing_Need" in result.referenced_subflows

def test_apex_actions_dedupe():
    xml = """<records xmlns="http://soap.sforce.com/2006/04/metadata">
      <actionCalls><name>a</name><actionName>MyClass</actionName><actionType>apex</actionType></actionCalls>
      <actionCalls><name>a</name><actionName>MyClass</actionName><actionType>apex</actionType></actionCalls>
    </records>"""
    result = parse_flow_xml(xml)
    matching = [a for a in result.apex_actions if a.apex_class_name == "MyClass"]
    assert len(matching) == 1
