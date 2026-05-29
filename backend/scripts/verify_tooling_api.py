"""Manual verification of ToolingAPIClient against real Salesforce.

Run this against your dev org to confirm:
- Each typed query method returns parseable responses
- Field names in our Pydantic models match what Salesforce actually returns
- extract_all_for_graph completes in the expected concurrent time

Usage (from backend/ with USE_MOCK_DATA=false and valid tokens.json):

    python scripts/verify_tooling_api.py

This is NOT part of the automated test suite. It hits real Salesforce
and burns API quota (~6 calls per run). Run it once after building each
typed query method; otherwise rely on the unit tests.
"""

import asyncio
import time

from app.salesforce.http_client import SalesforceHTTPClient
from app.salesforce.tooling_api import ToolingAPIClient


async def main() -> None:
    print("=" * 60)
    print("ToolingAPIClient — real-org verification")
    print("=" * 60)

    http = SalesforceHTTPClient()
    async with http:
        try:
            await http.authenticate()
        except RuntimeError as e:
            print(f"\n❌ Auth failed: {e}")
            print("   Run /auth/login in your browser first.")
            return

        print(f"\n✅ Authenticated. Instance: {http._tokens.instance_url}\n")

        tooling = ToolingAPIClient(http=http)

        # --- Individual queries ---

        print("1. query_apex_classes (no body)...")
        t0 = time.perf_counter()
        result = await tooling.query_apex_classes(limit=5)
        elapsed = time.perf_counter() - t0
        print(f"   ✅ {result.totalSize} total, {len(result.records)} returned in {elapsed:.2f}s")
        if result.records:
            sample = result.records[0]
            print(f"   Sample: {sample.Name} (v{sample.ApiVersion}, Status={sample.Status})")

        print("\n2. query_apex_triggers...")
        t0 = time.perf_counter()
        result = await tooling.query_apex_triggers(limit=5)
        elapsed = time.perf_counter() - t0
        print(f"   ✅ {result.totalSize} total, {len(result.records)} returned in {elapsed:.2f}s")
        if result.records:
            sample = result.records[0]
            events = [e for e in [
                ("BeforeInsert", sample.UsageBeforeInsert),
                ("AfterInsert", sample.UsageAfterInsert),
                ("BeforeUpdate", sample.UsageBeforeUpdate),
                ("AfterUpdate", sample.UsageAfterUpdate),
            ] if e[1]]
            print(f"   Sample: {sample.Name} on {sample.TableEnumOrId}, events={[e[0] for e in events]}")

        print("\n3. query_entity_definitions (IsCustomizable=true, limit 10)...")
        t0 = time.perf_counter()
        result = await tooling.query_entity_definitions(
            where="IsCustomizable = true",
            limit=10,
        )
        elapsed = time.perf_counter() - t0
        print(f"   ✅ {result.totalSize} total, {len(result.records)} returned in {elapsed:.2f}s")
        for r in result.records[:5]:
            print(f"   - {r.QualifiedApiName} (DurableId={r.DurableId}, KeyPrefix={r.KeyPrefix})")

        print("\n4. query_custom_fields (limit 5)...")
        t0 = time.perf_counter()
        result = await tooling.query_custom_fields(limit=5)
        elapsed = time.perf_counter() - t0
        print(f"   ✅ {result.totalSize} total, {len(result.records)} returned in {elapsed:.2f}s")
        for r in result.records[:5]:
            print(f"   - {r.DeveloperName}__c on {r.TableEnumOrId}")

        print("\n5. query_validation_rules (limit 5)...")
        t0 = time.perf_counter()
        result = await tooling.query_validation_rules(limit=5)
        elapsed = time.perf_counter() - t0
        print(f"   ✅ {result.totalSize} total, {len(result.records)} returned in {elapsed:.2f}s")
        for r in result.records[:5]:
            print(f"   - {r.ValidationName} on EntityDef={r.EntityDefinitionId} (Active={r.Active})")

        print("\n6. query_flow_definitions (limit 5)...")
        t0 = time.perf_counter()
        result = await tooling.query_flow_definitions(limit=5)
        elapsed = time.perf_counter() - t0
        print(f"   ✅ {result.totalSize} total, {len(result.records)} returned in {elapsed:.2f}s")
        for r in result.records[:5]:
            active = "ACTIVE" if r.ActiveVersionId else "no active version"
            print(f"   - {r.DeveloperName} ({r.MasterLabel}) — {active}")

        # --- The headline test: concurrent extraction ---

        print("\n" + "=" * 60)
        print("7. extract_all_for_graph — 6 queries concurrent")
        print("=" * 60)

        t0 = time.perf_counter()
        bundle = await tooling.extract_all_for_graph()
        elapsed = time.perf_counter() - t0

        print(f"   ✅ All 6 queries done in {elapsed:.2f}s")
        print(f"      apex_classes:       {bundle['apex_classes'].totalSize}")
        print(f"      apex_triggers:      {bundle['apex_triggers'].totalSize}")
        print(f"      entity_definitions: {bundle['entity_definitions'].totalSize}")
        print(f"      custom_fields:      {bundle['custom_fields'].totalSize}")
        print(f"      validation_rules:   {bundle['validation_rules'].totalSize}")
        print(f"      flow_definitions:   {bundle['flow_definitions'].totalSize}")
        print()
        print(f"   Compare to ~6 sequential queries × 0.3-0.5s = ~2-3s expected.")
        print(f"   Concurrent wall time: {elapsed:.2f}s")
        if elapsed < 2.0:
            print("   ✅ Asyncio.gather paying off — well under sequential.")
        else:
            print("   ⚠️  Slower than expected; may indicate network latency or quota throttling.")


if __name__ == "__main__":
    asyncio.run(main())