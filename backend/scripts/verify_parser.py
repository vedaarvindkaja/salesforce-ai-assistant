# No direct Apex equivalent — throwaway dev script (plumbing, not product)
"""Run the Apex pattern parser over every cached class/trigger and report findings.

Usage (from backend/):
    python -m scripts.verify_parser

Output:
  - Per-class summary: what each class contributes (SOQL objects, DML ops,
    field refs, class calls)
  - Aggregate counts across the org
  - Top referenced objects, fields, and classes
  - Classes with zero extractions (parser found nothing — worth eyeballing)

Zero API calls — reads the local SQLite cache only.
"""
from __future__ import annotations

import asyncio
import time
from collections import Counter
from pathlib import Path

from app.intelligence.code.apex_parser import parse_apex_body
from app.intelligence.graph.storage import MetadataCache
from app.salesforce.token_storage import load_tokens

_CACHE_PATH = Path("data") / "metadata_cache.db"


async def main() -> None:
    tokens = load_tokens()
    if tokens is None:
        raise SystemExit("No tokens. Run the auth flow first.")
    org_key = tokens.instance_url

    cache = MetadataCache(_CACHE_PATH)
    records: list[dict] = []
    for mtype in ("ApexClass", "ApexTrigger"):
        rows = await cache.get(org_key=org_key, metadata_type=mtype)
        for r in rows:
            r["_mtype"] = mtype
        records.extend(rows)

    print(f"\n{'='*60}")
    print(f"Apex Parser — real-org verification")
    print(f"Org: {org_key}")
    print(f"Records: {len(records)}")
    print(f"{'='*60}")

    # Aggregate counters
    soql_counter: Counter = Counter()
    dml_counter: Counter = Counter()
    field_counter: Counter = Counter()
    class_counter: Counter = Counter()
    zero_extraction: list[str] = []

    t0 = time.perf_counter()

    for rec in sorted(records, key=lambda r: r.get("Name", "")):
        name = rec.get("Name") or rec.get("DeveloperName") or "<unknown>"
        body = rec.get("Body") or ""
        result = parse_apex_body(body)

        total = (
            len(result.soql_references)
            + len(result.dml_references)
            + len(result.field_references)
            + len(result.class_references)
        )

        if total == 0:
            zero_extraction.append(name)
            continue

        print(f"\n{name} ({rec['_mtype']})")
        if result.soql_references:
            objs = ", ".join(r.object_name for r in result.soql_references)
            print(f"  SOQL objects  : {objs}")
            for r in result.soql_references:
                soql_counter[r.object_name] += 1
        if result.dml_references:
            ops = ", ".join(f"{r.operation}({r.object_name})" for r in result.dml_references)
            print(f"  DML ops       : {ops}")
            for r in result.dml_references:
                dml_counter[f"{r.operation}({r.object_name})"] += 1
        if result.field_references:
            refs = ", ".join(f"{r.qualifier}.{r.field_name}" for r in result.field_references[:8])
            more = f" (+{len(result.field_references)-8} more)" if len(result.field_references) > 8 else ""
            print(f"  Field refs    : {refs}{more}")
            for r in result.field_references:
                field_counter[f"{r.qualifier}.{r.field_name}"] += 1
        if result.class_references:
            refs = ", ".join(f"{r.class_name}.{r.method_name}()" for r in result.class_references[:8])
            more = f" (+{len(result.class_references)-8} more)" if len(result.class_references) > 8 else ""
            print(f"  Class calls   : {refs}{more}")
            for r in result.class_references:
                class_counter[r.class_name] += 1

    elapsed = (time.perf_counter() - t0) * 1000

    print(f"\n{'='*60}")
    print(f"AGGREGATE SUMMARY")
    print(f"{'='*60}")
    print(f"Parse time      : {elapsed:.0f} ms for {len(records)} records")
    print(f"Zero extractions: {len(zero_extraction)} classes")
    if zero_extraction:
        print(f"  {', '.join(zero_extraction)}")

    if soql_counter:
        print(f"\nTop SOQL objects (by class count):")
        for obj, count in soql_counter.most_common(10):
            print(f"  {count:3d}  {obj}")

    if dml_counter:
        print(f"\nTop DML operations:")
        for op, count in dml_counter.most_common(10):
            print(f"  {count:3d}  {op}")

    if class_counter:
        print(f"\nTop referenced classes (method calls):")
        for cls, count in class_counter.most_common(10):
            print(f"  {count:3d}  {cls}")

    if field_counter:
        print(f"\nTop field references (qualifier.field):")
        for fld, count in field_counter.most_common(15):
            print(f"  {count:3d}  {fld}")

    print(f"\n{'='*60}")
    print("Review zero-extraction classes above.")
    print("Check top field refs — high-frequency ones are graph edge candidates.")
    print("Check top SOQL objects — these become Object nodes on Day 3.")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    asyncio.run(main())
