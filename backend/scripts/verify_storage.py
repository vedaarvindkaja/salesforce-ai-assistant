# No direct Apex equivalent — standalone verification script (dev plumbing)
"""Hermetic verification of the storage layer.

Run from backend/:  python -m scripts.verify_storage

No live org required — round-trips synthetic records through SQLite.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

from pydantic import BaseModel

from app.intelligence.graph.storage import MetadataCache


class _SampleRecord(BaseModel):
    Id: str
    DeveloperName: str
    Body: str | None = None


async def main() -> None:
    db_path = Path("data") / "verify_cache.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db_path.unlink(missing_ok=True)  # fresh run every time

    cache = MetadataCache(db_path)
    await cache.init_schema()
    print(f"[ok] schema initialised at {db_path}")

    written = await cache.put(
        org_key="demo-org",
        metadata_type="ApexClass",
        records=[
            _SampleRecord(Id="01p000000000001", DeveloperName="AccountService",
                          Body="public class AccountService {}"),
            _SampleRecord(Id="01p000000000002", DeveloperName="ContactTrigger"),
        ],
    )
    print(f"[ok] wrote {written} ApexClass records")

    all_rows = await cache.get(org_key="demo-org", metadata_type="ApexClass")
    print(f"[ok] read back {len(all_rows)}: {[r['DeveloperName'] for r in all_rows]}")

    by_name = await cache.get(org_key="demo-org", metadata_type="ApexClass",
                              display_name="AccountService")
    print(f"[ok] lookup by display_name: {len(by_name)} record")

    await cache.put(org_key="demo-org", metadata_type="ApexClass",
                    records=[_SampleRecord(Id="01p000000000001",
                                           DeveloperName="AccountService",
                                           Body="// updated")])
    refreshed = await cache.get_one(org_key="demo-org", metadata_type="ApexClass",
                                    record_id="01p000000000001")
    print(f"[ok] upsert updated body to: {refreshed['Body']!r}")

    print(f"[ok] stats: {await cache.stats(org_key='demo-org')}")
    print("\nAll storage checks passed.")


if __name__ == "__main__":
    asyncio.run(main())