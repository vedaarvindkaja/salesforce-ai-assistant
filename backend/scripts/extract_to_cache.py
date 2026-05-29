# ============================================================
# PYTHON CODE
# ============================================================
"""Extract real Apex classes AND triggers from Salesforce into the cache.

Hits a real org (burns ~2-3 API calls) — NOT part of the test suite,
same class of script as verify_tooling_api.py.

Run (from backend/, with USE_MOCK_DATA=false and valid tokens.json):
    python -m scripts.extract_to_cache
"""
from __future__ import annotations

import asyncio
from pathlib import Path

from app.salesforce.http_client import SalesforceHTTPClient
from app.salesforce.tooling_api import ToolingAPIClient
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

        # Classes
        class_response = await tooling.query_apex_classes(include_body=True, limit=50)
        # CHANGE if query_apex_classes returns a bare list: records = class_response
        class_records = class_response.records
        written_c = await cache.put(
            org_key=org_key, metadata_type="ApexClass", records=class_records
        )
        print(f"[ok] cached {written_c} ApexClass records")

        # Triggers — same shape. If query_apex_triggers lacks include_body,
        # this line raises TypeError (clear) — remove the kwarg and the
        # with_body check below will reveal whether bodies came through.
        trigger_response = await tooling.query_apex_triggers(include_body=True, limit=50)
        # CHANGE if query_apex_triggers returns a bare list: records = trigger_response
        trigger_records = trigger_response.records
        written_t = await cache.put(
            org_key=org_key, metadata_type="ApexTrigger", records=trigger_records
        )
        print(f"[ok] cached {written_t} ApexTrigger records")

    # Read-back verification per type — with_body is the gate for insight A.
    for mtype in ("ApexClass", "ApexTrigger"):
        rows = await cache.get(org_key=org_key, metadata_type=mtype)
        with_body = sum(1 for r in rows if r.get("Body"))
        print(f"[ok] {mtype}: {with_body}/{len(rows)} have non-empty Body")

    print(f"[ok] stats: {await cache.stats(org_key=org_key)}")
    print("\nReal extraction cached (classes + triggers). Ready for the analyzer.")


if __name__ == "__main__":
    asyncio.run(main())


# ============================================================
# APEX EQUIVALENT (for comparison)
# ============================================================
# A Batch class querying both ApexClass and ApexTrigger and upserting:
#
#    public class ExtractApexToCache implements Database.Batchable<sObject> {
#        public Iterable<sObject> start(Database.BatchableContext bc) {
#            List<sObject> all = new List<sObject>();
#            all.addAll([SELECT Id, Name, Body FROM ApexClass LIMIT 50]);
#            all.addAll([SELECT Id, Name, Body FROM ApexTrigger LIMIT 50]);
#            return all;
#        }
#        public void execute(Database.BatchableContext bc, List<sObject> scope) {
#            // map each to Metadata_Cache__c, upsert on Record_Id__c external Id
#        }
#        public void finish(Database.BatchableContext bc) {}
#    }
#
# Concept mapping:
# - two query_* calls + two put()s   → two SOQL queries into one batch scope
# - metadata_type tag per put        → SObjectType.getDescribe().getName()
# - upsert on external Id            → cache.put ON CONFLICT DO UPDATE
# ============================================================