# No direct Apex equivalent — standalone verification script (dev plumbing)
"""Build the metadata graph from the real local cache and report on it.

Reads the EXISTING cache at data/metadata_cache.db (populated by
scripts.extract_to_cache). Does NOT hit Salesforce — zero API calls.
Only load_tokens() is used, to get org_key = instance_url (ADR-005), so
the graph is built for the same partition the extraction wrote to.

Run (from backend/):
    python -m scripts.verify_graph
"""
from __future__ import annotations

import asyncio
import time
from pathlib import Path

from app.intelligence.graph.builder import GraphBuilder
from app.intelligence.graph.models import MetadataGraph
from app.intelligence.graph.storage import MetadataCache
from app.salesforce.token_storage import load_tokens


def _in_degree(graph: MetadataGraph, node_id: str) -> int:
    """How many nodes reference this one (things that depend on it)."""
    return len(graph.predecessors(node_id))


def _out_degree(graph: MetadataGraph, node_id: str) -> int:
    """How many nodes this one references (its dependencies)."""
    return len(graph.successors(node_id))


def _report(graph: MetadataGraph, build_seconds: float) -> None:
    nodes = graph.all_nodes()
    stats = graph.stats()

    print("\n" + "=" * 60)
    print("GRAPH BUILD REPORT")
    print("=" * 60)
    print(f"Build time      : {build_seconds * 1000:.1f} ms")
    print(f"Nodes           : {stats.node_count}")
    print(f"Edges           : {stats.edge_count}")
    print(f"Nodes by type   : {stats.node_type_counts}")
    print(f"Edges by type   : {stats.edge_type_counts}")

    # Most depended-upon — the hubs. In a trigger-actions org we expect the
    # handler/dispatch classes to top this list.
    by_in = sorted(nodes, key=lambda n: _in_degree(graph, n.id), reverse=True)
    print("\nTop 10 most-referenced (highest in-degree — the hubs):")
    for n in by_in[:10]:
        deg = _in_degree(graph, n.id)
        if deg == 0:
            break
        print(f"  {deg:3d}  <- {n.name}  ({n.node_type.value})")

    # Most dependencies — classes that touch the most other classes.
    by_out = sorted(nodes, key=lambda n: _out_degree(graph, n.id), reverse=True)
    print("\nTop 10 with most dependencies (highest out-degree):")
    for n in by_out[:10]:
        deg = _out_degree(graph, n.id)
        if deg == 0:
            break
        print(f"  {deg:3d}  -> {n.name}  ({n.node_type.value})")

    # Orphans — no edges in either direction. In a metadata-driven framework
    # these are often action classes wired via custom metadata, invisible to
    # an Apex-only string scan. That's the finding, not a bug.
    orphans = [
        n for n in nodes
        if _in_degree(graph, n.id) == 0 and _out_degree(graph, n.id) == 0
    ]
    print(f"\nOrphans (no Apex references in or out): {len(orphans)}/{len(nodes)}")
    for n in orphans[:15]:
        print(f"  .   {n.name}  ({n.node_type.value})")
    if len(orphans) > 15:
        print(f"  ... and {len(orphans) - 15} more")

    print("\n" + "=" * 60)
    print("Interpretation hints:")
    print("  - High-in-degree hubs = core classes; a change here is high-blast-radius.")
    print("  - Orphans in a trigger-actions org often mean metadata-wired action")
    print("    classes the Apex string-scan can't see (cf. MetadataComponentDependency).")
    print("=" * 60 + "\n")


async def main() -> None:
    tokens = load_tokens()
    if tokens is None:
        raise RuntimeError(
            "No OAuth tokens found. Visit http://localhost:8000/auth/login, "
            "then run scripts.extract_to_cache to populate the cache."
        )
    org_key = tokens.instance_url
    print(f"[ok] org_key={org_key!r}")

    db_path = Path("data") / "metadata_cache.db"
    if not db_path.exists():
        raise RuntimeError(
            f"Cache not found at {db_path}. Run scripts.extract_to_cache first."
        )

    cache = MetadataCache(db_path)
    cache_stats = await cache.stats(org_key=org_key)
    print(f"[ok] cache contents: {cache_stats}")
    if not cache_stats:
        raise RuntimeError(
            f"Cache has no records for org_key={org_key!r}. "
            "Re-run scripts.extract_to_cache (org_key must match)."
        )

    start = time.perf_counter()
    graph = await GraphBuilder(cache).build(org_key=org_key)
    build_seconds = time.perf_counter() - start

    _report(graph, build_seconds)


if __name__ == "__main__":
    asyncio.run(main())
