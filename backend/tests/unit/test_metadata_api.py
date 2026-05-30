"""Hermetic tests for MetadataAPIClient (Week 7 Day 5).

Uses httpx.MockTransport to fake the Metadata API SOAP response — no real
org, no network. The fixture XML is modeled on the real readMetadata(Flow)
response captured during the Day 5 SOAP probe against the dev org.
"""
import pytest
import httpx

from app.salesforce.http_client import SalesforceHTTPClient
from app.salesforce.oauth_models import StoredTokens
from app.salesforce.metadata_api import MetadataAPIClient, FlowMetadata
from app.salesforce import token_storage


VALID_TOKENS = StoredTokens(
    access_token="VALID_SESSION_TOKEN",
    refresh_token="VALID_REFRESH",
    instance_url="https://test.my.salesforce.com",
)


# A two-flow readMetadata response, modeled on the real probe output.
TWO_FLOW_RESPONSE = """<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
    xmlns="http://soap.sforce.com/2006/04/metadata"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <soapenv:Body>
    <readMetadataResponse>
      <result>
        <records xsi:type="Flow">
          <fullName>Update_Contact_Phone_When_Account_Phone_Updates</fullName>
          <apiVersion>64.0</apiVersion>
          <processType>AutoLaunchedFlow</processType>
          <start>
            <object>Account</object>
            <triggerType>RecordAfterSave</triggerType>
          </start>
        </records>
        <records xsi:type="Flow">
          <fullName>Opportunity_Approval_Orchestrator</fullName>
          <apiVersion>60.0</apiVersion>
          <processType>AutoLaunchedFlow</processType>
          <start>
            <object>Opportunity</object>
            <triggerType>RecordAfterSave</triggerType>
          </start>
        </records>
      </result>
    </readMetadataResponse>
  </soapenv:Body>
</soapenv:Envelope>"""


EMPTY_RESPONSE = """<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
    xmlns="http://soap.sforce.com/2006/04/metadata">
  <soapenv:Body>
    <readMetadataResponse><result></result></readMetadataResponse>
  </soapenv:Body>
</soapenv:Envelope>"""


def _build_client(handler) -> tuple[MetadataAPIClient, SalesforceHTTPClient]:
    http = SalesforceHTTPClient()
    http._http = httpx.AsyncClient(transport=httpx.MockTransport(handler), timeout=5.0)
    http._tokens = VALID_TOKENS
    return MetadataAPIClient(http=http), http


@pytest.fixture(autouse=True)
def isolate_token_storage(monkeypatch, tmp_path):
    monkeypatch.setattr(token_storage, "_TOKEN_FILE", tmp_path / "tokens.json")


# ------------------------------------------------------------------
# read_flows — happy path
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_read_flows_returns_one_per_record():
    def handler(request):
        return httpx.Response(200, text=TWO_FLOW_RESPONSE)

    client, http = _build_client(handler)
    names_to_ids = {
        "Update_Contact_Phone_When_Account_Phone_Updates": "300aaa",
        "Opportunity_Approval_Orchestrator": "300bbb",
    }
    flows = await client.read_flows(names_to_ids=names_to_ids)
    assert len(flows) == 2
    assert all(isinstance(f, FlowMetadata) for f in flows)
    await http._http.aclose()


@pytest.mark.asyncio
async def test_read_flows_maps_name_to_id():
    def handler(request):
        return httpx.Response(200, text=TWO_FLOW_RESPONSE)

    client, http = _build_client(handler)
    names_to_ids = {
        "Update_Contact_Phone_When_Account_Phone_Updates": "300aaa",
        "Opportunity_Approval_Orchestrator": "300bbb",
    }
    flows = await client.read_flows(names_to_ids=names_to_ids)
    by_name = {f.DeveloperName: f for f in flows}
    assert by_name["Update_Contact_Phone_When_Account_Phone_Updates"].Id == "300aaa"
    assert by_name["Opportunity_Approval_Orchestrator"].Id == "300bbb"
    await http._http.aclose()


@pytest.mark.asyncio
async def test_read_flows_keeps_raw_xml():
    def handler(request):
        return httpx.Response(200, text=TWO_FLOW_RESPONSE)

    client, http = _build_client(handler)
    flows = await client.read_flows(
        names_to_ids={"Update_Contact_Phone_When_Account_Phone_Updates": "300aaa",
                      "Opportunity_Approval_Orchestrator": "300bbb"}
    )
    flow = next(f for f in flows if f.Id == "300aaa")
    # The raw <records> block is preserved for the parser
    assert "<records" in flow.xml
    assert "<object>Account</object>" in flow.xml
    assert "RecordAfterSave" in flow.xml
    await http._http.aclose()


# ------------------------------------------------------------------
# read_flows — edge cases
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_read_flows_empty_response():
    def handler(request):
        return httpx.Response(200, text=EMPTY_RESPONSE)

    client, http = _build_client(handler)
    flows = await client.read_flows(names_to_ids={"Whatever": "300xxx"})
    assert flows == []
    await http._http.aclose()


@pytest.mark.asyncio
async def test_read_flows_skips_unrequested_names():
    # Response contains a flow we didn't ask for — defensive skip
    def handler(request):
        return httpx.Response(200, text=TWO_FLOW_RESPONSE)

    client, http = _build_client(handler)
    # Only ask for one of the two flows in the response
    flows = await client.read_flows(
        names_to_ids={"Opportunity_Approval_Orchestrator": "300bbb"}
    )
    assert len(flows) == 1
    assert flows[0].DeveloperName == "Opportunity_Approval_Orchestrator"
    await http._http.aclose()


@pytest.mark.asyncio
async def test_read_flows_empty_input():
    def handler(request):
        return httpx.Response(200, text=EMPTY_RESPONSE)

    client, http = _build_client(handler)
    flows = await client.read_flows(names_to_ids={})
    assert flows == []
    await http._http.aclose()


# ------------------------------------------------------------------
# batching — the request envelope carries the names
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_read_flows_sends_soap_envelope_with_session_and_names():
    captured = {}

    def handler(request):
        captured["content"] = request.content.decode()
        captured["content_type"] = request.headers.get("content-type")
        return httpx.Response(200, text=TWO_FLOW_RESPONSE)

    client, http = _build_client(handler)
    await client.read_flows(
        names_to_ids={"Update_Contact_Phone_When_Account_Phone_Updates": "300aaa",
                      "Opportunity_Approval_Orchestrator": "300bbb"}
    )
    # Session id (our access_token) is embedded in the SOAP header
    assert "VALID_SESSION_TOKEN" in captured["content"]
    # Both flow names are in the envelope as fullNames
    assert "Update_Contact_Phone_When_Account_Phone_Updates" in captured["content"]
    assert "Opportunity_Approval_Orchestrator" in captured["content"]
    assert "text/xml" in captured["content_type"]
    await http._http.aclose()


@pytest.mark.asyncio
async def test_read_flows_batches_over_ten():
    # 12 names → 2 batches (10 + 2). Count how many POSTs fire.
    call_count = {"n": 0}

    def handler(request):
        call_count["n"] += 1
        return httpx.Response(200, text=EMPTY_RESPONSE)

    client, http = _build_client(handler)
    names_to_ids = {f"Flow_{i}": f"300{i:03d}" for i in range(12)}
    await client.read_flows(names_to_ids=names_to_ids)
    assert call_count["n"] == 2  # 10 + 2 = two batches
    await http._http.aclose()
