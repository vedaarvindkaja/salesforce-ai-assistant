"""Tests for ToolingAPIClient.

Uses httpx.MockTransport to fake Salesforce Tooling API responses without
making real network calls. Same pattern as test_salesforce_client.py
(Week 4 Day 4), but targeting the Tooling API client built Week 5 Day 2.

These tests verify:
- Typed query methods return correctly-parsed Pydantic models
- The generic ToolingQueryResponse[T] works for each record type
- SOQL building includes the right fields, WHERE, LIMIT
- extract_all_for_graph fires 6 concurrent queries
- query_raw returns dict for ad-hoc queries

Real-org verification lives in scripts/verify_tooling_api.py (manual,
not in the automated suite).
"""

import pytest
import httpx

from app.models.tooling import (
    ApexClass,
    ApexTrigger,
    CustomField,
    EntityDefinition,
    FlowDefinition,
    ValidationRule,
)
from app.salesforce.http_client import SalesforceHTTPClient
from app.salesforce.oauth_models import StoredTokens
from app.salesforce.tooling_api import ToolingAPIClient
from app.salesforce import token_storage


# ============================================================
# Fixtures: realistic Tooling API responses
# ============================================================

APEX_CLASS_RESPONSE = {
    "totalSize": 2,
    "done": True,
    "records": [
        {
            "attributes": {
                "type": "ApexClass",
                "url": "/services/data/v60.0/tooling/sobjects/ApexClass/01p000000000001",
            },
            "Id": "01p000000000001",
            "Name": "AccountTriggerHandler",
            "ApiVersion": 60.0,
            "Status": "Active",
            "IsValid": True,
            "LengthWithoutComments": 1247,
            "NamespacePrefix": None,
            "CreatedDate": "2024-03-15T10:30:00.000+0000",
            "LastModifiedDate": "2026-04-20T14:22:00.000+0000",
        },
        {
            "attributes": {
                "type": "ApexClass",
                "url": "/services/data/v60.0/tooling/sobjects/ApexClass/01p000000000002",
            },
            "Id": "01p000000000002",
            "Name": "MyManagedClass",
            "ApiVersion": 58.0,
            "Status": "Active",
            "IsValid": True,
            "LengthWithoutComments": 0,
            "NamespacePrefix": "mypkg",
            "CreatedDate": "2024-01-10T08:00:00.000+0000",
            "LastModifiedDate": "2024-01-10T08:00:00.000+0000",
        },
    ],
}

APEX_TRIGGER_RESPONSE = {
    "totalSize": 1,
    "done": True,
    "records": [
        {
            "attributes": {
                "type": "ApexTrigger",
                "url": "/services/data/v60.0/tooling/sobjects/ApexTrigger/01q000000000001",
            },
            "Id": "01q000000000001",
            "Name": "AccountTrigger",
            "TableEnumOrId": "Account",
            "ApiVersion": 60.0,
            "Status": "Active",
            "IsValid": True,
            "UsageBeforeInsert": True,
            "UsageAfterInsert": True,
            "UsageBeforeUpdate": True,
            "UsageAfterUpdate": True,
            "UsageBeforeDelete": False,
            "UsageAfterDelete": False,
            "UsageAfterUndelete": False,
            "LengthWithoutComments": 89,
            "NamespacePrefix": None,
            "CreatedDate": "2024-03-15T10:35:00.000+0000",
            "LastModifiedDate": "2024-03-15T10:35:00.000+0000",
        },
    ],
}

ENTITY_DEFINITION_RESPONSE = {
    "totalSize": 2,
    "done": True,
    "records": [
        {
            "attributes": {
                "type": "EntityDefinition",
                "url": "/services/data/v60.0/tooling/sobjects/EntityDefinition/Account",
            },
            "DurableId": "Account",
            "QualifiedApiName": "Account",
            "Label": "Account",
            "IsCustomizable": True,
            "IsCustomSetting": False,
            "IsApexTriggerable": True,
            "IsWorkflowEnabled": True,
            "KeyPrefix": "001",
            "NamespacePrefix": None,
        },
        {
            "attributes": {
                "type": "EntityDefinition",
                "url": "/services/data/v60.0/tooling/sobjects/EntityDefinition/01I000000000001",
            },
            "DurableId": "01I000000000001",
            "QualifiedApiName": "MyCustomObject__c",
            "Label": "My Custom Object",
            "IsCustomizable": True,
            "IsCustomSetting": False,
            "IsApexTriggerable": True,
            "IsWorkflowEnabled": False,
            "KeyPrefix": "a01",
            "NamespacePrefix": None,
        },
    ],
}

CUSTOM_FIELD_RESPONSE = {
    "totalSize": 1,
    "done": True,
    "records": [
        {
            "attributes": {
                "type": "CustomField",
                "url": "/services/data/v60.0/tooling/sobjects/CustomField/00N000000000001",
            },
            "Id": "00N000000000001",
            "DeveloperName": "Priority",
            "TableEnumOrId": "Account",
            "NamespacePrefix": None,
            "CreatedDate": "2024-05-01T12:00:00.000+0000",
            "LastModifiedDate": "2024-05-01T12:00:00.000+0000",
        },
    ],
}

VALIDATION_RULE_RESPONSE = {
    "totalSize": 1,
    "done": True,
    "records": [
        {
            "attributes": {
                "type": "ValidationRule",
                "url": "/services/data/v60.0/tooling/sobjects/ValidationRule/03d000000000001",
            },
            "Id": "03d000000000001",
            "ValidationName": "Amount_Must_Be_Positive",
            "EntityDefinitionId": "Opportunity",
            "Active": True,
            "Description": "Ensures opportunity amount is non-negative",
            "ErrorMessage": "Amount cannot be negative.",
            "CreatedDate": "2024-02-10T09:00:00.000+0000",
            "LastModifiedDate": "2024-02-10T09:00:00.000+0000",
        },
    ],
}

FLOW_DEFINITION_RESPONSE = {
    "totalSize": 1,
    "done": True,
    "records": [
        {
            "attributes": {
                "type": "FlowDefinition",
                "url": "/services/data/v60.0/tooling/sobjects/FlowDefinition/300000000000001",
            },
            "Id": "300000000000001",
            "DeveloperName": "Update_Account_Owner",
            "MasterLabel": "Update Account Owner",
            "ActiveVersionId": "301000000000001",
            "LatestVersionId": "301000000000002",
            "NamespacePrefix": None,
            "CreatedDate": "2024-06-15T11:00:00.000+0000",
            "LastModifiedDate": "2026-03-10T16:45:00.000+0000",
        },
        {
            "attributes": {
                "type": "FlowDefinition",
                "url": "/services/data/v60.0/tooling/sobjects/FlowDefinition/300000000000002",
            },
            "Id": "300000000000002",
            "DeveloperName": "Opportunity_Approval_Orchestrator",
            "MasterLabel": None,
            "ActiveVersionId": "301000000000003",
            "LatestVersionId": "301000000000003",
            "NamespacePrefix": None,
            "CreatedDate": "2024-06-15T11:00:00.000+0000",
            "LastModifiedDate": "2024-06-15T11:00:00.000+0000",
        },
    ],
}

VALID_TOKENS = StoredTokens(
    access_token="VALID_TOKEN",
    refresh_token="VALID_REFRESH",
    instance_url="https://test.my.salesforce.com",
)


# ============================================================
# Helper: build a ToolingAPIClient wired to a MockTransport
# ============================================================

def _build_tooling_client(handler) -> tuple[ToolingAPIClient, SalesforceHTTPClient]:
    """Construct a ToolingAPIClient backed by a MockTransport.

    Returns both the tooling client and the underlying HTTP client so
    tests can close the HTTP client at the end.
    """
    http = SalesforceHTTPClient()
    http._http = httpx.AsyncClient(transport=httpx.MockTransport(handler), timeout=5.0)
    http._tokens = VALID_TOKENS
    tooling = ToolingAPIClient(http=http)
    return tooling, http


# ============================================================
# Patch token_storage so tests don't touch the real tokens.json
# ============================================================

@pytest.fixture(autouse=True)
def isolate_token_storage(monkeypatch, tmp_path):
    fake_path = tmp_path / "tokens.json"
    monkeypatch.setattr(token_storage, "_TOKEN_FILE", fake_path)


# ============================================================
# Tests — typed query methods
# ============================================================

@pytest.mark.asyncio
async def test_query_apex_classes_parses_response():
    """query_apex_classes returns ToolingQueryResponse[ApexClass] with typed records."""
    captured_soql: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_soql.append(request.url.params.get("q", ""))
        return httpx.Response(200, json=APEX_CLASS_RESPONSE)

    tooling, http = _build_tooling_client(handler)
    result = await tooling.query_apex_classes()

    # Response is correctly typed and parsed
    assert result.totalSize == 2
    assert result.done is True
    assert len(result.records) == 2

    # First record is a properly-typed ApexClass
    first = result.records[0]
    assert isinstance(first, ApexClass)
    assert first.Name == "AccountTriggerHandler"
    assert first.ApiVersion == 60.0
    assert first.Status == "Active"
    assert first.Body is None  # include_body defaults to False
    assert first.NamespacePrefix is None

    # Managed-package class is also parsed correctly
    second = result.records[1]
    assert second.NamespacePrefix == "mypkg"

    # SOQL was built without Body field (default include_body=False)
    soql = captured_soql[0]
    assert "Body" not in soql
    assert "ApexClass" in soql
    assert "ApiVersion" in soql

    await http._http.aclose()


@pytest.mark.asyncio
async def test_query_apex_classes_with_body_includes_body_in_soql():
    """include_body=True adds Body to the SELECT list."""
    captured_soql: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_soql.append(request.url.params.get("q", ""))
        return httpx.Response(200, json=APEX_CLASS_RESPONSE)

    tooling, http = _build_tooling_client(handler)
    await tooling.query_apex_classes(include_body=True)

    assert "Body" in captured_soql[0]

    await http._http.aclose()


@pytest.mark.asyncio
async def test_query_apex_classes_with_where_and_limit():
    """where and limit parameters are included in the SOQL."""
    captured_soql: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_soql.append(request.url.params.get("q", ""))
        return httpx.Response(200, json=APEX_CLASS_RESPONSE)

    tooling, http = _build_tooling_client(handler)
    await tooling.query_apex_classes(where="NamespacePrefix = null", limit=10)

    soql = captured_soql[0]
    assert "WHERE NamespacePrefix = null" in soql
    assert "LIMIT 10" in soql

    await http._http.aclose()


@pytest.mark.asyncio
async def test_query_apex_triggers_parses_all_usage_flags():
    """All 7 trigger event flags are correctly parsed."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=APEX_TRIGGER_RESPONSE)

    tooling, http = _build_tooling_client(handler)
    result = await tooling.query_apex_triggers()

    trigger = result.records[0]
    assert isinstance(trigger, ApexTrigger)
    assert trigger.TableEnumOrId == "Account"
    assert trigger.UsageBeforeInsert is True
    assert trigger.UsageAfterInsert is True
    assert trigger.UsageBeforeUpdate is True
    assert trigger.UsageAfterUpdate is True
    assert trigger.UsageBeforeDelete is False
    assert trigger.UsageAfterDelete is False
    assert trigger.UsageAfterUndelete is False

    await http._http.aclose()


@pytest.mark.asyncio
async def test_query_entity_definitions_handles_standard_and_custom():
    """EntityDefinition unifies standard (Account) and custom (MyCustom__c)."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=ENTITY_DEFINITION_RESPONSE)

    tooling, http = _build_tooling_client(handler)
    result = await tooling.query_entity_definitions()

    assert len(result.records) == 2

    standard = result.records[0]
    assert isinstance(standard, EntityDefinition)
    assert standard.DurableId == "Account"
    assert standard.QualifiedApiName == "Account"
    assert standard.KeyPrefix == "001"

    custom = result.records[1]
    assert custom.QualifiedApiName == "MyCustomObject__c"
    assert custom.DurableId == "01I000000000001"  # Custom objects get Id-shaped DurableId

    await http._http.aclose()


@pytest.mark.asyncio
async def test_query_custom_fields():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=CUSTOM_FIELD_RESPONSE)

    tooling, http = _build_tooling_client(handler)
    result = await tooling.query_custom_fields()

    field = result.records[0]
    assert isinstance(field, CustomField)
    assert field.DeveloperName == "Priority"
    assert field.TableEnumOrId == "Account"

    await http._http.aclose()


@pytest.mark.asyncio
async def test_query_validation_rules():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=VALIDATION_RULE_RESPONSE)

    tooling, http = _build_tooling_client(handler)
    result = await tooling.query_validation_rules()

    rule = result.records[0]
    assert isinstance(rule, ValidationRule)
    assert rule.ValidationName == "Amount_Must_Be_Positive"
    assert rule.EntityDefinitionId == "Opportunity"
    assert rule.Active is True

    await http._http.aclose()


@pytest.mark.asyncio
async def test_query_flow_definitions():
    """Verify FlowDefinition parsing handles real Salesforce behavior.

    Real-world finding (Week 5 Day 2 verification against a dev org):
    FlowDefinition.MasterLabel via Tooling API SOQL is unreliable — even
    active, well-named flows return null. The model accepts this and the
    test encodes the behavior so future engineers don't trust the schema
    over the actual data.
    """
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=FLOW_DEFINITION_RESPONSE)

    tooling, http = _build_tooling_client(handler)
    result = await tooling.query_flow_definitions()

    assert len(result.records) == 2

    # First flow: rare case — MasterLabel actually populated
    flow = result.records[0]
    assert isinstance(flow, FlowDefinition)
    assert flow.DeveloperName == "Update_Account_Owner"
    assert flow.MasterLabel == "Update Account Owner"

    # Second flow: typical case — active flow with null MasterLabel.
    # DeveloperName is the reliable label source.
    typical_flow = result.records[1]
    assert typical_flow.DeveloperName == "Opportunity_Approval_Orchestrator"
    assert typical_flow.MasterLabel is None
    assert typical_flow.ActiveVersionId is not None  # Active despite null label

    await http._http.aclose()

# ============================================================
# Tests — query_raw escape hatch
# ============================================================

@pytest.mark.asyncio
async def test_query_raw_returns_dict():
    """query_raw returns raw dict, not Pydantic model."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=APEX_CLASS_RESPONSE)

    tooling, http = _build_tooling_client(handler)
    result = await tooling.query_raw("SELECT Id, Name FROM ApexClass")

    assert isinstance(result, dict)
    assert result["totalSize"] == 2
    assert isinstance(result["records"], list)
    # Raw dict — record entries are dicts, not ApexClass instances
    assert isinstance(result["records"][0], dict)

    await http._http.aclose()


# ============================================================
# Tests — extract_all_for_graph (concurrent queries)
# ============================================================

@pytest.mark.asyncio
async def test_extract_all_for_graph_fires_six_queries():
    """extract_all_for_graph runs all 6 queries concurrently."""
    query_count = {"value": 0}
    queries_seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        query_count["value"] += 1
        soql = request.url.params.get("q", "")
        queries_seen.append(soql)

        # Return the appropriate response based on which sObject is queried
        if "FROM ApexClass" in soql:
            return httpx.Response(200, json=APEX_CLASS_RESPONSE)
        if "FROM ApexTrigger" in soql:
            return httpx.Response(200, json=APEX_TRIGGER_RESPONSE)
        if "FROM EntityDefinition" in soql:
            return httpx.Response(200, json=ENTITY_DEFINITION_RESPONSE)
        if "FROM CustomField" in soql:
            return httpx.Response(200, json=CUSTOM_FIELD_RESPONSE)
        if "FROM ValidationRule" in soql:
            return httpx.Response(200, json=VALIDATION_RULE_RESPONSE)
        if "FROM FlowDefinition" in soql:
            return httpx.Response(200, json=FLOW_DEFINITION_RESPONSE)
        raise AssertionError(f"Unexpected SOQL: {soql}")

    tooling, http = _build_tooling_client(handler)
    result = await tooling.extract_all_for_graph()

    # All 6 queries fired
    assert query_count["value"] == 6

    # All 6 keys present, all are ToolingQueryResponse (have .records)
    assert set(result.keys()) == {
        "apex_classes", "apex_triggers", "entity_definitions",
        "custom_fields", "validation_rules", "flow_definitions",
    }
    assert len(result["apex_classes"].records) == 2
    assert len(result["entity_definitions"].records) == 2
    assert isinstance(result["apex_classes"].records[0], ApexClass)

    await http._http.aclose()