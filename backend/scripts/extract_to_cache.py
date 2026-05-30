# ============================================================
# PYTHON CODE
# ============================================================
"""Extract real Apex classes, triggers, AND flows from Salesforce into the cache.

Hits a real org (burns ~5-8 API calls) — NOT part of the test suite,
same class of script as verify_tooling_api.py.

Run (from backend/, with USE_MOCK_DATA=false and valid tokens.json):
    python -m scripts.extract_to_cache

Flow extraction (Week 7 Day 5):
  1. query_flow_definitions (Tooling) → name→id for ACTIVE flows
  2. read_flows (Metadata SOAP) → raw Flow XML per flow
  3. cache as metadata_type="Flow" with the raw <records> XML in payload
The Flow XML is parsed at graph-build time (flow_parser.py), consistent with
how ApexClass.Body is cached raw and scanned at build time.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

from app.salesforce.http_client import SalesforceHTTPClient
from app.salesforce.tooling_api import ToolingAPIClient
from app.salesforce.metadata_api import MetadataAPIClient
from app.salesforce.token_storage import load_tokens
from app.intelligence.graph.storage import MetadataCache


async def main() -> None:
    # ADR-005: cache partition key = org instance_url, via load_tokens()
    tokens = load_tokens()
    if tokens is None:
        raise RuntimeError(
            "No OAuth tokens found. Visit http://localhost:8000/auth/login first."
        )
    org_key = tokens.instance_url
    print(f"[ok] org_key={org_key!r}")

    db_path = Path("data") / "metadata_cache.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)

    cache = MetadataCache(db_path)
    await cache.init_schema()

    http = SalesforceHTTPClient()
    async with http:
        await http.authenticate()
        tooling = ToolingAPIClient(http)
        metadata = MetadataAPIClient(http)

        # Classes
        class_response = await tooling.query_apex_classes(include_body=True, limit=50)
        class_records = class_response.records
        written_c = await cache.put(
            org_key=org_key, metadata_type="ApexClass", records=class_records
        )
        print(f"[ok] cached {written_c} ApexClass records")

        # Triggers
        trigger_response = await tooling.query_apex_triggers(include_body=True, limit=50)
        trigger_records = trigger_response.records
        written_t = await cache.put(
            org_key=org_key, metadata_type="ApexTrigger", records=trigger_records
        )
        print(f"[ok] cached {written_t} ApexTrigger records")

        # Flows (Week 7 Day 5): Tooling for the active-flow list, SOAP for XML.
        flow_defs = await tooling.query_flow_definitions()
        names_to_ids = {
            fd.DeveloperName: fd.Id
            for fd in flow_defs.records
            if fd.ActiveVersionId  # only active flows have structure worth caching
        }
        print(f"[ok] {len(names_to_ids)} active flows to read via Metadata SOAP")
        if names_to_ids:
            flow_records = await metadata.read_flows(names_to_ids=names_to_ids)
            written_f = await cache.put(
                org_key=org_key, metadata_type="Flow", records=flow_records
            )
            print(f"[ok] cached {written_f} Flow records")
        else:
            print("[ok] no active flows — skipping Flow cache")

    # Read-back verification per type.
    for mtype in ("ApexClass", "ApexTrigger"):
        rows = await cache.get(org_key=org_key, metadata_type=mtype)
        with_body = sum(1 for r in rows if r.get("Body"))
        print(f"[ok] {mtype}: {with_body}/{len(rows)} have non-empty Body")

    flow_rows = await cache.get(org_key=org_key, metadata_type="Flow")
    with_xml = sum(1 for r in flow_rows if r.get("xml"))
    print(f"[ok] Flow: {with_xml}/{len(flow_rows)} have non-empty xml")

    print(f"[ok] stats: {await cache.stats(org_key=org_key)}")
    print("\nReal extraction cached (classes + triggers + flows). Ready for the builder.")


if __name__ == "__main__":
    asyncio.run(main())


# ============================================================
# APEX EQUIVALENT (for comparison)
# ============================================================
# Extraction orchestration has no clean Apex parallel — it's a dev-tool
# script pulling metadata FROM an org, not in-org logic. The closest
# in-org analog would be a Batch Apex job querying Tooling objects, but
# the Metadata API SOAP read_flows step has no in-Apex equivalent except
# the auto-generated MetadataService wrapper (see metadata_api.py's Apex
# block). Skipping a full translation — this is plumbing, not domain logic.
# ============================================================
