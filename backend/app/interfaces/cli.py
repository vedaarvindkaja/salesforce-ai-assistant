# No direct Apex equivalent — CLI entry point + argparse (consumer-facing plumbing)
"""Command-line interface for the metadata graph (ADR-001: interfaces/ layer).

Builds the graph from the local cache and answers one dependency question,
then exits. No server, no HTTP. The graph is rebuilt each run (Option A — no
persistence); at current scale that's ~0.3 s, imperceptible for a CLI.

Name resolution and edge-label formatting live in intelligence/graph/naming.py
(ADR-013) so the CLI and the orchestration tool layer describe metadata
identically. The module-level _resolve_one / _fmt_node aliases below preserve
the original import paths used by the existing CLI tests.

Examples (from backend/):
    python -m app.interfaces.cli depends-on TriggerActionFlow
    python -m app.interfaces.cli depends-on TriggerActionFlow --transitive
    python -m app.interfaces.cli dependencies MetadataTriggerHandler
    python -m app.interfaces.cli impact Opportunity
    python -m app.interfaces.cli path AccountTrigger TriggerActionConstants
    python -m app.interfaces.cli find Trigger
    python -m app.interfaces.cli orphans
    python -m app.interfaces.cli never-referenced
    python -m app.interfaces.cli never-referenced --no-tests
    python -m app.interfaces.cli stats

Design: each _cmd_* handler is a PURE function returning its output string;
only main() prints. Keeps handlers unit-testable without capturing stdout.
"""
from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from app.intelligence.graph.builder import GraphBuilder
from app.intelligence.graph.models import MetadataGraph, Node
from app.intelligence.graph.naming import (
    edge_method_detail,
    edge_relation_label,
    fmt_node,
    resolve_one,
)
from app.intelligence.graph.query import QueryEngine
from app.intelligence.graph.storage import MetadataCache
from app.salesforce.token_storage import load_tokens

_CACHE_PATH = Path("data") / "metadata_cache.db"

# Backwards-compatible aliases (ADR-013 refactor). The resolution and
# formatting logic now lives in naming.py; these names keep the original
# cli._resolve_one / cli._fmt_node import paths working for existing tests.
_resolve_one = resolve_one
_fmt_node = fmt_node


# ------------------------------------------------------------------
# Command handlers — pure: take engine/graph, return a string
# ------------------------------------------------------------------

def _cmd_depends_on(engine: QueryEngine, name: str, *, transitive: bool) -> str:
    node, err = resolve_one(engine, name)
    if err:
        return err
    deps = engine.what_depends_on(node.id, transitive=transitive)
    kind = "transitive" if transitive else "direct"
    if not deps:
        return f"Nothing depends on {fmt_node(node)}."
    head = f"{len(deps)} {kind} dependent(s) of {fmt_node(node)}:"
    return "\n".join([head, *(f"  {fmt_node(n)}" for n in deps)])


def _cmd_dependencies(engine: QueryEngine, name: str, *, transitive: bool) -> str:
    node, err = resolve_one(engine, name)
    if err:
        return err
    deps = engine.what_does_it_depend_on(node.id, transitive=transitive)
    kind = "transitive" if transitive else "direct"
    if not deps:
        return f"{fmt_node(node)} depends on nothing (in Apex)."
    head = f"{fmt_node(node)} has {len(deps)} {kind} dependenc(ies):"
    return "\n".join([head, *(f"  {fmt_node(n)}" for n in deps)])


def _cmd_impact(engine: QueryEngine, graph: MetadataGraph, name: str) -> str:
    """Impact view: which Apex/Flow touches this node, and HOW.

    Built for the field-impact demo on Object nodes ('what breaks if I change
    Opportunity'), but works on any node — for a class it shows callers and
    referencers annotated by relationship type. Edge labels come from
    naming.edge_relation_label (via-driven), shared with the analyze_impact tool.
    """
    node, err = resolve_one(engine, name)
    if err:
        return err

    edges = engine.incoming_edges(node.id)
    if not edges:
        return f"Nothing touches {fmt_node(node)}."

    head = f"Impact of {fmt_node(node)} — {len(edges)} reference(s) touch it:"
    lines = [head]
    for e in edges:
        src = graph.get_node(e.source_id)
        src_label = fmt_node(src) if src else e.source_id
        relation = edge_relation_label(e)
        detail = edge_method_detail(e)
        lines.append(f"  {src_label}  via {relation}{detail}")
    return "\n".join(lines)


def _cmd_path(engine: QueryEngine, graph: MetadataGraph,
              from_name: str, to_name: str) -> str:
    src, e1 = resolve_one(engine, from_name)
    if e1:
        return e1
    dst, e2 = resolve_one(engine, to_name)
    if e2:
        return e2
    edges = engine.find_path(src.id, dst.id)
    if not edges:
        return f"No dependency path from {src.name} to {dst.name}."
    out = [f"Path from {src.name} to {dst.name} ({len(edges)} hop(s)):"]
    for e in edges:
        s = graph.get_node(e.source_id)
        t = graph.get_node(e.target_id)
        lns = e.attributes.get("line_numbers", [])
        if len(lns) == 1:
            loc = f"line {lns[0]}"
        elif lns:
            loc = "lines " + ", ".join(str(x) for x in lns)
        else:
            loc = "location unknown"
        out.append(f"  {s.name} --references--> {t.name}  ({loc})")
    return "\n".join(out)


def _cmd_find(engine: QueryEngine, name: str) -> str:
    matches = engine.find_by_name(name)
    if not matches:
        return f"No metadata matching '{name}'."
    head = f"{len(matches)} match(es) for '{name}':"
    return "\n".join([head, *(f"  {fmt_node(n)}" for n in matches)])


def _cmd_orphans(engine: QueryEngine) -> str:
    nodes = engine.find_orphaned()
    if not nodes:
        return "No orphaned metadata (every node has at least one Apex link)."
    head = f"{len(nodes)} orphan(s) — no Apex references in or out (dead or UI-bound):"
    return "\n".join([head, *(f"  {fmt_node(n)}" for n in nodes)])


def _cmd_never_referenced(engine: QueryEngine, *, no_tests: bool = False) -> str:
    nodes = engine.find_never_referenced(exclude_tests=no_tests)
    if not nodes:
        msg = "No never-referenced metadata"
        return msg + " (excluding test classes)." if no_tests else msg + "."

    def _fmt(n: Node) -> str:
        suffix = "  [test]" if n.attributes.get("is_test") else ""
        return f"  {fmt_node(n)}{suffix}"

    filter_note = " (test classes excluded)" if no_tests else ""
    head = (
        f"{len(nodes)} never-referenced{filter_note} — nothing in Apex references "
        f"them, but they reference others. Non-test entries are the interesting "
        f"signal (metadata-wired actions, flow/invocable entry points, or dead code):"
    )
    return "\n".join([head, *(_fmt(n) for n in nodes)])


def _cmd_stats(graph: MetadataGraph) -> str:
    s = graph.stats()
    return "\n".join([
        "Graph stats:",
        f"  nodes: {s.node_count}  {s.node_type_counts}",
        f"  edges: {s.edge_count}  {s.edge_type_counts}",
    ])


# ------------------------------------------------------------------
# Argument parsing
# ------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cli",
        description="Query the Salesforce metadata dependency graph.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("depends-on", help="what depends on NAME")
    p.add_argument("name")
    p.add_argument("--transitive", "-t", action="store_true",
                   help="full blast radius, not just direct dependents")

    p = sub.add_parser("dependencies", help="what NAME depends on")
    p.add_argument("name")
    p.add_argument("--transitive", "-t", action="store_true",
                   help="everything NAME reaches, not just direct dependencies")

    p = sub.add_parser("impact",
                        help="what touches NAME and how (SOQL/DML/call/reference)")
    p.add_argument("name")

    p = sub.add_parser("path", help="shortest dependency path FROM -> TO")
    p.add_argument("from_name")
    p.add_argument("to_name")

    p = sub.add_parser("find", help="find nodes by (partial) name")
    p.add_argument("name")

    sub.add_parser("orphans", help="nodes with no references in or out")

    p = sub.add_parser("never-referenced",
                        help="nodes nothing references (in==0, out>0)")
    p.add_argument("--no-tests", action="store_true",
                   help="exclude @isTest classes — surfaces production-code signal only")

    sub.add_parser("stats", help="node/edge counts")
    return parser


def _dispatch(args, engine: QueryEngine, graph: MetadataGraph) -> str:
    if args.command == "depends-on":
        return _cmd_depends_on(engine, args.name, transitive=args.transitive)
    if args.command == "dependencies":
        return _cmd_dependencies(engine, args.name, transitive=args.transitive)
    if args.command == "impact":
        return _cmd_impact(engine, graph, args.name)
    if args.command == "path":
        return _cmd_path(engine, graph, args.from_name, args.to_name)
    if args.command == "find":
        return _cmd_find(engine, args.name)
    if args.command == "orphans":
        return _cmd_orphans(engine)
    if args.command == "never-referenced":
        return _cmd_never_referenced(engine, no_tests=args.no_tests)
    if args.command == "stats":
        return _cmd_stats(graph)
    return f"Unknown command: {args.command}"  # unreachable (argparse guards)


# ------------------------------------------------------------------
# Graph bootstrap + entry point
# ------------------------------------------------------------------

async def _load_graph() -> tuple[QueryEngine, MetadataGraph]:
    tokens = load_tokens()
    if tokens is None:
        raise SystemExit(
            "No OAuth tokens found. Visit http://localhost:8000/auth/login, "
            "then run: python -m scripts.extract_to_cache"
        )
    org_key = tokens.instance_url
    if not _CACHE_PATH.exists():
        raise SystemExit(
            f"Cache not found at {_CACHE_PATH}. Run: python -m scripts.extract_to_cache"
        )
    cache = MetadataCache(_CACHE_PATH)
    graph = await GraphBuilder(cache).build(org_key=org_key)
    if graph.stats().node_count == 0:
        raise SystemExit(
            f"Graph is empty for org_key={org_key!r}. "
            "Re-run: python -m scripts.extract_to_cache"
        )
    return QueryEngine(graph), graph


async def _run(args) -> None:
    engine, graph = await _load_graph()
    print(_dispatch(args, engine, graph))


def main() -> None:
    args = _build_parser().parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
