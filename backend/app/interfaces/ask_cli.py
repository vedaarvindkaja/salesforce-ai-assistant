# No direct Apex equivalent — AI Q&A CLI entry point (orchestration plumbing)
"""Ask-Claude CLI — mode-dispatched AI surface (ADR-001 interfaces/ layer).

Wires the whole orchestration stack into one command, with a --mode flag that
selects which capability lens Claude applies:

    python -m app.interfaces.ask_cli "question"               # qa (default)
    python -m app.interfaces.ask_cli --mode apex "question"   # Apex explanation
    python -m app.interfaces.ask_cli --mode soql "question"   # SOQL generation
    python -m app.interfaces.ask_cli --mode impact "question" # Deployment impact

Each mode maps to a (system_prompt_builder, tool_name_set) pair in
CAPABILITY_REGISTRY. The tool subsetting happens here — ask_cli owns the
decision of what Claude sees per capability; build_tools() stays a pure factory.

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
from app.intelligence.orchestration.claude_client import ClaudeClient
from app.intelligence.orchestration.system_prompt import (
    build_apex_prompt,
    build_impact_prompt,
    build_soql_prompt,
    build_system_prompt,
)
from app.intelligence.orchestration.tool_definitions import build_tools
from app.salesforce.token_storage import load_tokens

load_dotenv()

_CACHE_PATH = Path("data") / "metadata_cache.db"

# ------------------------------------------------------------------
# Tool subsets — what Claude can see per capability mode.
# impact excludes get_source: topology is sufficient; source reading
# adds cost with no benefit for blast-radius analysis.
# ------------------------------------------------------------------
_ALL_TOOLS = {
    "find_dependencies", "find_references_to", "analyze_impact",
    "find_by_name", "graph_health", "get_source",
}
_GRAPH_ONLY = _ALL_TOOLS - {"get_source"}

# Registry: mode -> (prompt_builder, allowed_tool_names)
# Adding a new capability = one new entry here + a new builder in system_prompt.py.
CAPABILITY_REGISTRY: dict[str, tuple] = {
    "qa":     (build_system_prompt, _ALL_TOOLS),
    "apex":   (build_apex_prompt,   _ALL_TOOLS),
    "soql":   (build_soql_prompt,   _ALL_TOOLS),
    "impact": (build_impact_prompt, _GRAPH_ONLY),
}

VALID_MODES = list(CAPABILITY_REGISTRY.keys())


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

    prompt_builder, allowed_tools = CAPABILITY_REGISTRY[mode]
    engine, graph, cache, org_key = await _load()

    system_prompt = prompt_builder(graph)
    all_schemas, all_handlers = build_tools(engine, graph, cache, org_key)

    # Subset schemas and handlers to what this capability allows.
    schemas = [s for s in all_schemas if s["name"] in allowed_tools]
    handlers = {n: h for n, h in all_handlers.items() if n in allowed_tools}

    client = ClaudeClient(system_prompt=system_prompt)
    for tool_name, handler in handlers.items():
        client.register_tool(
            tool_name,
            _announce(tool_name, handler) if show_tools else handler,
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
