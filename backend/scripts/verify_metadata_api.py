# No direct Apex equivalent — real-org verification script (dev plumbing)
"""Real-org smoke test for MetadataAPIClient.read_flows.

Day 5 — proves the SOAP client pulls actual Flow structures from the org
and the raw XML comes back intact, before the parser is built on it.

Flow: list FlowDefinitions via Tooling (proven Week 5) to get name→id, then
read_flows() via the Metadata SOAP client. Reports what came back.

Run (from backend/, valid tokens.json):
    python -m scripts.verify_metadata_api

Burns a handful of API calls. Not in the test suite.
"""
from __future__ import annotations

import asyncio
import re

from app.salesforce.http_client import SalesforceHTTPClient
from app.salesforce.tooling_api import ToolingAPIClient
from app.salesforce.metadata_api import MetadataAPIClient
from app.salesforce.token_storage import load_tokens


async def main() -> None:
    tokens = load_tokens()
    if tokens is None:
        raise SystemExit("No tokens. Run the auth flow first.")

    http = SalesforceHTTPClient()
    async with http:
        await http.authenticate()
        tooling = ToolingAPIClient(http)
        metadata = MetadataAPIClient(http)

        print("=" * 60)
        print("METADATA SOAP CLIENT — real-org verification")
        print("=" * 60)

        # name -> FlowDefinition Id (active flows only — inactive have no
        # structure worth reading; matches what we'll cache).
        defs = await tooling.query_flow_definitions()
        names_to_ids = {
            fd.DeveloperName: fd.Id
            for fd in defs.records
            if fd.ActiveVersionId
        }
        print(f"\n[step 1] {len(names_to_ids)} active flows to read")

        if not names_to_ids:
            print("  No active flows. Nothing to verify.")
            return

        flows = await metadata.read_flows(names_to_ids=names_to_ids)
        print(f"[step 2] read_flows returned {len(flows)} flow structures\n")

        for f in flows:
            obj = re.search(r"<object>(.*?)</object>", f.xml)
            proc = re.search(r"<processType>(.*?)</processType>", f.xml)
            trig = re.search(r"<triggerType>(.*?)</triggerType>", f.xml)
            actions = len(re.findall(r"<actionCalls>", f.xml))
            subflows = len(re.findall(r"<subflows>", f.xml))
            print(f"  {f.DeveloperName}  (Id={f.Id})")
            print(f"    xml length    : {len(f.xml)} chars")
            print(f"    processType   : {proc.group(1) if proc else '-'}")
            print(f"    start object  : {obj.group(1) if obj else '-'}")
            print(f"    triggerType   : {trig.group(1) if trig else '-'}")
            print(f"    actionCalls   : {actions}")
            print(f"    subflows      : {subflows}")

        print(f"\n{'=' * 60}")
        print("Check before building the parser:")
        print("  - Did read_flows return all active flows?")
        print("  - Is xml non-empty and reasonable length per flow?")
        print("  - Do start object / processType / triggerType populate?")
        print("  - Any flows with actionCalls (Apex/subflow edges to extract)?")
        print(f"{'=' * 60}")


if __name__ == "__main__":
    asyncio.run(main())
