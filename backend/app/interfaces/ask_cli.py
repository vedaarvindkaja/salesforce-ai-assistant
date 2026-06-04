# No direct Apex equivalent — AI Q&A CLI entry point (orchestration plumbing)
"""Ask-Claude CLI — mode-dispatched AI surface (ADR-001 interfaces/ layer).

Wires the whole orchestration stack into one command, with a --mode flag that
selects which capability lens Claude applies:

    python -m app.interfaces.ask_cli "question"               # qa (default)
    python -m app.interfaces.ask_cli --mode apex "question"   # Apex explanation
    python -m app.interfaces.ask_cli --mode soql "question"   # SOQL generation
    python -m app.interfaces.ask_cli --mode impact "question" # Deployment impact

The per-mode wiring (which prompt builder + which tool subset) lives in
orchestration/capabilities.py, shared with the MCP server so the capability
definitions have one home (see ADR-013-style discipline). This module owns only
the CLI concerns: argument parsing, graph bootstrap, streaming to stdout, and
tool-call announcement on stderr.

Separate from cli.py on purpose: cli.py is the DETERMINISTIC graph-query surface
(pure, synchronous, free). This is the PROBABILISTIC one — it calls the live
API, costs money, streams, and can fail with API errors.

Thin entry-point wrappers (ask_apex.py, ask_soql.py, ask_impact.py) call
main(default_mode=...) so each capability has a clean module name for the
portfolio, without duplicating any logic here.

Tool calls are announced on stderr (ADR-014 observability). Suppress with --quiet.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from dotenv import load_dotenv

from app.intelligence.graph.builder import GraphBuilder
from app.intelligence.graph.query import QueryEngine
from app.intelligence.graph.storage import MetadataCache
from app.intelligence.orchestration.capabilities import (
    CAPABILITY_REGISTRY,
    VALID_MODES,
    _ALL_TOOLS,
    build_capability_client,
)
from app.salesforce.token_storage import load_tokens

load_dotenv()

_CACHE_PATH = Path("data") / "metadata_cache.db"

# Re-exported above (CAPABILITY_REGISTRY, VALID_MODES, _ALL_TOOLS) so existing
# import paths (ask_cli.CAPABILITY_REGISTRY etc.) keep resolving after the
# capabilities.py extraction — same back-compat-alias trick cli.py used in the
# ADR-013 naming refactor. The definitions now live in capabilities.py.


# ------------------------------------------------------------------
# Graph + cache bootstrap
# ------------------------------------------------------------------

async def _load() -> tuple[QueryEngine, "MetadataGraph", MetadataCache, str]:
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
    return QueryEngine(graph), graph, cache, org_key


# ------------------------------------------------------------------
# Tool-call observability (ADR-014)
# ------------------------------------------------------------------

def _announce(name: str, handler):
    """Wrap a handler so each invocation prints to stderr before running."""
    async def wrapped(inp: dict) -> str:
        print(f"  [tool] {name}({inp})", file=sys.stderr, flush=True)
        return await handler(inp)
    return wrapped


# ------------------------------------------------------------------
# Core ask flow
# ------------------------------------------------------------------

async def _ask(question: str, *, mode: str = "qa", show_tools: bool = True) -> None:
    if mode not in CAPABILITY_REGISTRY:
        raise SystemExit(
            f"Unknown mode {mode!r}. Valid modes: {', '.join(VALID_MODES)}"
        )

    engine, graph, cache, org_key = await _load()
    client, schemas = build_capability_client(
        mode, engine, graph, cache, org_key,
        handler_wrapper=_announce if show_tools else None,
    )

    if mode != "qa":
        print(f"  [mode] {mode}", file=sys.stderr, flush=True)

    print(f"\nQ: {question}\n")
    async for chunk in client.ask(question, tools=schemas):
        print(chunk, end="", flush=True)
    print("\n")
    print(client.session.summary(), file=sys.stderr)


# ------------------------------------------------------------------
# CLI wiring
# ------------------------------------------------------------------

def _build_parser(default_mode: str = "qa") -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ask",
        description="Ask Claude about your Salesforce org's metadata graph.",
    )
    parser.add_argument("question", help="natural-language question (quote it)")
    parser.add_argument(
        "--mode", "-m",
        choices=VALID_MODES,
        default=default_mode,
        help=f"capability mode (default: {default_mode}). "
             f"Choices: {', '.join(VALID_MODES)}",
    )
    parser.add_argument(
        "--quiet", "-q", action="store_true",
        help="don't announce which tools Claude calls",
    )
    return parser


def main(default_mode: str = "qa") -> None:
    """Entry point. default_mode lets thin wrappers (ask_apex.py etc.) set
    their mode without duplicating any logic."""
    args = _build_parser(default_mode=default_mode).parse_args()
    asyncio.run(_ask(args.question, mode=args.mode, show_tools=not args.quiet))


if __name__ == "__main__":
    main()
