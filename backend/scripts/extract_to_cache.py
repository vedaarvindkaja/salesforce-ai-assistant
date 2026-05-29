# ============================================================
# PYTHON CODE
# ============================================================
"""Extract real Apex classes from Salesforce into the local cache.

Hits a real org (burns ~1-2 API calls) — NOT part of the test suite,
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
    # ADR-005: cache partition key = org instance_url, read via load_tokens()
    # (the same loader the HTTP client uses — public front door, no private reach).
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

        # include_body=True is the whole point — insight A scans the source.
        # limit keeps the first real extraction small; raise/remove later.
        response = await tooling.query_apex_classes(include_body=True, limit=50)

        # CHANGE THIS LINE if query_apex_classes returns a bare list instead
        # of ToolingQueryResponse[ApexClass]: use `records = response`.
        records = response.records
        print(f"[ok] fetched {len(records)} ApexClass records from org")

        written = await cache.put(
            org_key=org_key,
            metadata_type="ApexClass",
            records=records,
        )
        print(f"[ok] cached {written} records to {db_path}")

    read_back = await cache.get(org_key=org_key, metadata_type="ApexClass")
    print(f"[ok] read back {len(read_back)} records")
    with_body = sum(1 for r in read_back if r.get("Body"))
    print(f"[ok] {with_body}/{len(read_back)} have non-empty Body (needed for insight A)")
    print(f"[ok] stats: {await cache.stats(org_key=org_key)}")
    print("\nReal extraction cached. Ready for the analyzer.")


if __name__ == "__main__":
    asyncio.run(main())


# ============================================================
# APEX EQUIVALENT (for comparison)
# ============================================================
# The closest Apex parallel is a Batch class that queries metadata and
# upserts it into a custom object — though you'd rarely query your OWN
# org's Tooling API from Apex; this pattern fits a DevOps/tooling org
# reaching into a target org via Named Credential.
#
#    public class ExtractApexToCache implements Database.Batchable<sObject> {
#        public Database.QueryLocator start(Database.BatchableContext bc) {
#            return Database.getQueryLocator(
#                'SELECT Id, Name, Body FROM ApexClass LIMIT 50'
#            );
#        }
#        public void execute(Database.BatchableContext bc, List<ApexClass> scope) {
#            List<Metadata_Cache__c> rows = new List<Metadata_Cache__c>();
#            for (ApexClass ac : scope) {
#                rows.add(new Metadata_Cache__c(
#                    Record_Id__c     = ac.Id,        // external Id
#                    Metadata_Type__c = 'ApexClass',
#                    Display_Name__c  = ac.Name,
#                    Payload__c       = JSON.serialize(ac)
#                ));
#            }
#            upsert rows Record_Id__c;
#        }
#        public void finish(Database.BatchableContext bc) {}
#    }
#
# Concept mapping:
# - load_tokens().instance_url      → SELECT Instance_URL__c FROM Auth_Token__c
# - query_apex_classes(body=True)   → SOQL SELECT Body FROM ApexClass
# - cache.put / ON CONFLICT         → upsert rows Record_Id__c
# - async def main + asyncio.run    → Batchable start/execute/finish lifecycle
# ============================================================