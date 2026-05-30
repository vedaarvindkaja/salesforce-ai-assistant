# ============================================================
# PYTHON CODE
# ============================================================
"""Salesforce Metadata API (SOAP) client — Flow structure retrieval.

Wraps SalesforceHTTPClient to call the Metadata API's readMetadata operation
over SOAP. Unlike the Tooling API (REST/JSON), the Metadata API is SOAP/XML:
auth is a <sessionId> element inside a SOAP header, not an Authorization
Bearer header, and the response is a SOAP XML envelope.

Probe finding (Day 5 step 0, verified against real org): the existing OAuth
access_token works as the SOAP sessionId — no separate SOAP login() needed.
So this client borrows the same SalesforceHTTPClient token state the Tooling
client uses (ADR-003: one shared HTTP transport).

Scope: readMetadata('Flow', names). readMetadata is SYNCHRONOUS — one call
in, structure back — chosen over the asynchronous retrieve() (poll + zip)
because we need Flow structure for analysis, not deployable file artifacts.

readMetadata caps at 10 names per call; we batch in chunks of 10. At current
org scale (6 flows) batching never triggers, but it's correct for any org.

Returned FlowMetadata holds the RAW XML <records> block. We cache raw XML
(consistent with how ApexClass.Body is cached as raw source) and parse it at
graph-build time (flow_parser.py, Step 2). Re-parsing never needs a re-fetch.
"""
from __future__ import annotations

import html
import re
from typing import Optional

from pydantic import BaseModel

from app.salesforce.http_client import SalesforceHTTPClient

# Metadata API SOAP endpoint. 'm' = metadata service. Version matches the
# REST/Tooling version used elsewhere (v60.0).
_METADATA_SOAP_PATH = "/services/Soap/m/60.0"

# readMetadata caps at 10 fullNames per call (Salesforce limit).
_READ_METADATA_BATCH = 10

# SOAP envelope for readMetadata. {session_id} is the OAuth access_token;
# {names_xml} is one <met:fullNames>NAME</met:fullNames> per flow.
_ENVELOPE = """<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope
    xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
    xmlns:met="http://soap.sforce.com/2006/04/metadata">
  <soapenv:Header>
    <met:SessionHeader>
      <met:sessionId>{session_id}</met:sessionId>
    </met:SessionHeader>
  </soapenv:Header>
  <soapenv:Body>
    <met:readMetadata>
      <met:type>Flow</met:type>
      {names_xml}
    </met:readMetadata>
  </soapenv:Body>
</soapenv:Envelope>"""

# Pull each <records>...</records> block out of the SOAP response. Each block
# is one flow's full structure. DOTALL so . matches newlines across the block.
_RECORDS_BLOCK = re.compile(r"<records\b.*?</records>", re.DOTALL)

# Inside a records block, the flow's API name is in <fullName>.
_FULLNAME = re.compile(r"<fullName>(.*?)</fullName>", re.DOTALL)


class FlowMetadata(BaseModel):
    """One Flow's raw structure as returned by readMetadata.

    Shaped to satisfy MetadataCache.put (needs .Id, a name field, and is
    JSON-serializable). The Id is the FlowDefinition Id (stable cache PK);
    DeveloperName is the flow's fullName; xml is the raw <records> block,
    parsed at graph-build time.
    """
    Id: str
    DeveloperName: str
    xml: str


class MetadataAPIClient:
    """Salesforce Metadata API (SOAP) client.

    Usage:
        http = SalesforceHTTPClient()
        async with http:
            await http.authenticate()
            md = MetadataAPIClient(http=http)
            flows = await md.read_flows(
                names_to_ids={"My_Flow": "300xx..."}
            )

    Like ToolingAPIClient, this borrows an already-authenticated HTTP client
    and does not own the auth lifecycle (ADR-003).
    """

    def __init__(self, http: SalesforceHTTPClient) -> None:
        self._http = http

    async def read_flows(
        self, *, names_to_ids: dict[str, str]
    ) -> list[FlowMetadata]:
        """Read Flow structures by name via readMetadata, batched at 10.

        Args:
            names_to_ids: maps each flow's DeveloperName (fullName) to its
                          FlowDefinition Id. The Id becomes the cache PK; the
                          name is what readMetadata queries by.

        Returns:
            One FlowMetadata per flow that came back with a <records> block.
            Flows absent from the response (e.g. no such name) are skipped.
        """
        names = list(names_to_ids)
        results: list[FlowMetadata] = []

        for start in range(0, len(names), _READ_METADATA_BATCH):
            batch = names[start:start + _READ_METADATA_BATCH]
            xml_body = await self._read_metadata_batch(batch)
            for block in _RECORDS_BLOCK.findall(xml_body):
                fn_match = _FULLNAME.search(block)
                if fn_match is None:
                    continue
                full_name = html.unescape(fn_match.group(1)).strip()
                flow_id = names_to_ids.get(full_name)
                if flow_id is None:
                    # Name came back that we didn't ask for — defensive skip.
                    continue
                results.append(
                    FlowMetadata(Id=flow_id, DeveloperName=full_name, xml=block)
                )
        return results

    async def _read_metadata_batch(self, names: list[str]) -> str:
        """POST one readMetadata SOAP call for up to 10 names; return raw XML."""
        assert self._http._tokens is not None, "HTTP client not authenticated"
        session_id = self._http._tokens.access_token
        instance_url = self._http._tokens.instance_url

        names_xml = "\n      ".join(
            f"<met:fullNames>{_xml_escape(n)}</met:fullNames>" for n in names
        )
        envelope = _ENVELOPE.format(session_id=session_id, names_xml=names_xml)

        url = instance_url + _METADATA_SOAP_PATH
        headers = {
            "Content-Type": "text/xml; charset=UTF-8",
            "SOAPAction": '""',
        }
        # Bypass http.request() — that path sets a Bearer header + JSON body;
        # SOAP needs neither. We use the raw httpx client directly.
        resp = await self._http._http.post(url, content=envelope, headers=headers)
        resp.raise_for_status()
        return resp.text


def _xml_escape(value: str) -> str:
    """Escape XML special chars for safe inclusion in the SOAP envelope.

    Flow DeveloperNames are alphanumeric+underscore in practice, but escaping
    is correct hygiene — a name with & or < would otherwise break the XML.
    """
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


# ============================================================
# APEX EQUIVALENT (for comparison)
# ============================================================
# The Metadata API is itself a SOAP service Salesforce provides. From Apex
# you'd use the auto-generated MetadataService wrapper (or the Apex Metadata
# API). readMetadata maps to MetadataService.readMetadata:
#
#    MetadataService.MetadataPort service = new MetadataService.MetadataPort();
#    service.SessionHeader = new MetadataService.SessionHeader_element();
#    service.SessionHeader.sessionId = UserInfo.getSessionId();
#
#    MetadataService.IReadResult result =
#        service.readMetadata('Flow', new String[]{ 'My_Flow' });
#    MetadataService.Flow flow = (MetadataService.Flow) result.getRecords()[0];
#    String triggerObject = flow.start.object_x;   // 'object' is reserved → object_x
#
# Concept mapping:
# - access_token as <sessionId>          → UserInfo.getSessionId() in-org
# - SOAP envelope hand-built as XML       → auto-generated MetadataService stubs
# - readMetadata('Flow', names)           → service.readMetadata('Flow', names)
# - batch of 10 names                     → same 10-record limit applies in Apex
# - raw <records> XML kept for parsing    → strongly-typed MetadataService.Flow
#   (Apex deserializes for you; here we keep XML and parse in flow_parser.py)
# - SOAPAction header / text/xml          → handled by the generated WSDL stub
# ============================================================
