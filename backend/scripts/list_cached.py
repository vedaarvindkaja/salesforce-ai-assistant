# No direct Apex equivalent — throwaway cache inspector (dev plumbing)
"""List what's in the cache by type. python -m scripts.list_cached"""
from __future__ import annotations

import asyncio
from pathlib import Path

from app.salesforce.token_storage import load_tokens
from app.intelligence.graph.storage import MetadataCache


async def main() -> None:
    org_key = load_tokens().instance_url
    cache = MetadataCache(Path("data") / "metadata_cache.db")
    for mtype in ("ApexClass", "ApexTrigger"):
        rows = await cache.get(org_key=org_key, metadata_type=mtype)
        names = sorted(r.get("Name", "<unknown>") for r in rows)
        print(f"\n{mtype} ({len(names)}):")
        for n in names:
            print(f"  {n}")


if __name__ == "__main__":
    asyncio.run(main())