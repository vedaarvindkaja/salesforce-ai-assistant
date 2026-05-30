# No direct Apex equivalent — CLI entry point + argparse (consumer-facing plumbing)
"""Command-line interface for the metadata graph (ADR-001: interfaces/ layer).

Builds the graph from the local cache and answers one dependency question,
then exits. No server, no HTTP. The graph is rebuilt each run (Option A — no
persistence); at current scale that's ~0.3 s, imperceptible for a CLI.

Examples (from backend/):
    python -m app.interfaces.cli depends-on TriggerActionFlow
    python -m app.interfaces.cli depends-on TriggerActionFlow --transitive
    python -m app.interfaces.cli dependencies MetadataTriggerHandler
    python -m app.interfaces.cli path AccountTrigger TriggerActionConstants
    python -m app.interfaces.cli find Trigger
    python -m app.interfaces.cli orphans
    python -m app.interfaces.cli never-referenced
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
from app.intelligence.graph.query import QueryEngine
from app.intelligence.graph.storage import MetadataCache
from app.salesforce.token_storage import load_tokens

_CACHE_PATH = Path("data") / "metadata_cache.db"


# ------------------------------------------------------------------
# Name resolution — turn a human-typed name into a single Node
# ------------------------------------------------------------------

def _resolve_one(engine: QueryEngine, name: str) -> tuple[Node | None, str | None]:
    """Resolve a name to exactly one Node. Returns (node, None) on success or
    (None, error_message) when the name is missing or ambiguous.

    Strategy: exact (case-insensitive) match wins; otherwise a single
    substring match auto-resolves; otherwise report the ambiguity.
    """
    exact = engine.find_by_name(name, exact=True)
    if len(exact) == 1:
        return exact[0], None
    if len(exact) > 1:  # rare for class names, but be explicit
        names = ", ".join(n.name for n in exact)
        return None, f"'{name}' matches several nodes exactly: {names}"

    partial = engine.find_by_name(name)
    if len(partial) == 1:
        return partial[0], None
    if not partial:
        return None, f"No metadata named '{name}'. Try: cli find <partial-name>"
    shown = ", ".join(n.name for n in partial[:10])
    more = "" if len(partial) <= 10 else f" (+{len(partial) - 10} more)"
    return None, (
        f"'{name}' is ambiguous — matches {len(partial)}: {shown}{more}. "
        f"Use the exact name."
    )


def _fmt_node(n: Node) -> str:
    return f"{n.name} ({n.node_type.value})"


# ------------------------------------------------------------------
# Command handlers — pure: take engine/graph, return a string
# ------------------------------------------------------------------

def _cmd_depends_on(engine: QueryEngine, name: str, *, transitive: bool) -> str:
    node, err = _resolve_one(engine, name)
    if err:
        return err
    deps = engine.what_depends_on(node.id, transitive=transitive)
    kind = "transitive" if transitive else "direct"
    if not deps:
        return f"Nothing depends on {_fmt_node(node)}."
    head = f"{len(deps)} {kind} dependent(s) of {_fmt_node(node)}:"
    return "\n".join([head, *(f"  {_fmt_node(n)}" for n in deps)])


def _cmd_dependencies(engine: QueryEngine, name: str, *, transitive: bool) -> str:
    node, err = _resolve_one(engine, name)
    if err:
        return err
    deps = engine.what_does_it_depend_on(node.id, transitive=transitive)
    kind = "transitive" if transitive else "direct"
    if not deps:
        return f"{_fmt_node(node)} depends on nothing (in Apex)."
    head = f"{_fmt_node(node)} has {len(deps)} {kind} dependenc(ies):"
    return "\n".join([head, *(f"  {_fmt_node(n)}" for n in deps)])


def _cmd_path(engine: QueryEngine, graph: MetadataGraph,
              from_name: str, to_name: str) -> str:
    src, e1 = _resolve_one(engine, from_name)
    if e1:
        return e1
    dst, e2 = _resolve_one(engine, to_name)
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
    return "\n".join([head, *(f"  {_fmt_node(n)}" for n in matches)])


def _cmd_orphans(engine: QueryEngine) -> str:
    nodes = engine.find_orphaned()
    if not nodes:
        return "No orphaned metadata (every node has at least one Apex link)."
    head = f"{len(nodes)} orphan(s) — no Apex references in or out (dead or UI-bound):"
    return "\n".join([head, *(f"  {_fmt_node(n)}" for n in nodes)])


def _cmd_never_referenced(engine: QueryEngine) -> str:
    nodes = engine.find_never_referenced()
    if not nodes:
        return "No never-referenced metadata."
    head = (
        f"{len(nodes)} never-referenced — nothing in Apex references them, but "
        f"they reference others. Expect mostly test classes (run by @isTest, "
        f"not by reference); non-test entries are the interesting ones "
        f"(metadata-wired actions, flow/invocable entry points, or dead code):"
    )
    return "\n".join([head, *(f"  {_fmt_node(n)}" for n in nodes)])


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

    p = sub.add_parser("path", help="shortest dependency path FROM -> TO")
    p.add_argument("from_name")
    p.add_argument("to_name")

    p = sub.add_parser("find", help="find nodes by (partial) name")
    p.add_argument("name")

    sub.add_parser("orphans", help="nodes with no references in or out")
    sub.add_parser("never-referenced", help="nodes nothing references (in==0, out>0)")
    sub.add_parser("stats", help="node/edge counts")
    return parser


def _dispatch(args, engine: QueryEngine, graph: MetadataGraph) -> str:
    if args.command == "depends-on":
        return _cmd_depends_on(engine, args.name, transitive=args.transitive)
    if args.command == "dependencies":
        return _cmd_dependencies(engine, args.name, transitive=args.transitive)
    if args.command == "path":
        return _cmd_path(engine, graph, args.from_name, args.to_name)
    if args.command == "find":
        return _cmd_find(engine, args.name)
    if args.command == "orphans":
        return _cmd_orphans(engine)
    if args.command == "never-referenced":
        return _cmd_never_referenced(engine)
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
