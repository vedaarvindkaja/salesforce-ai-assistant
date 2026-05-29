# No direct Apex equivalent — standalone demo runner (dev plumbing)
"""Run insight A against the real cached org. No org call — reads cache only.

    python -m scripts.run_insight_a Account
    python -m scripts.run_insight_a Contact
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from app.salesforce.token_storage import load_tokens
from app.intelligence.graph.storage import MetadataCache
from app.intelligence.analyzer import ReferenceAnalyzer


async def main() -> None:
    identifier = sys.argv[1] if len(sys.argv) > 1 else "Account"

    tokens = load_tokens()
    if tokens is None:
        raise RuntimeError("No tokens — run extract_to_cache first.")
    org_key = tokens.instance_url

    cache = MetadataCache(Path("data") / "metadata_cache.db")
    analyzer = ReferenceAnalyzer(cache)
    report = await analyzer.find_references(org_key=org_key, identifier=identifier)

    print(f"\n'{identifier}' referenced in {report.referencing_class_count} "
          f"of {report.classes_scanned} classes:\n")
    for ref in report.references:
        preview = ref.line_numbers[:5]
        more = "..." if ref.match_count > 5 else ""
        print(f"  {ref.class_name:<40} {ref.match_count:>3} refs  "
              f"(lines {preview}{more})")
    if not report.references:
        print("  (none)")


if __name__ == "__main__":
    asyncio.run(main())