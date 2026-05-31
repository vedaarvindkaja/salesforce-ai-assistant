# No direct Apex equivalent — AI Q&A CLI entry point (orchestration plumbing)
"""Ask-Claude CLI — the first end-to-end surface (ADR-001 interfaces/ layer).

Wires the whole Week-8 stack into one command:
    build the graph from cache
      -> build_system_prompt(graph)      (orientation, ADR-014 tool-pull)
      -> build_tools(engine, graph, cache, org_key)  (the 6 tools)
      -> ClaudeClient(system_prompt=...)  (streaming agentic loop)
      -> stream the answer; report token cost.

Separate from cli.py on purpose: cli.py is the DETERMINISTIC graph-query surface
(pure, synchronous, free). This is the PROBABILISTIC one — it calls the live
API, costs money, streams, and can fail with API errors. Different beasts; kept
as distinct entry points.

Usage (from backend/, needs a populated cache + ANTHROPIC_API_KEY in .env):
    python -m app.interfaces.ask_cli "what depends on the Opportunity object?"
    python -m app.interfaces.ask_cli "show me the source of PricingFlowAction"
    python -m app.interfaces.ask_cli "any dead or orphaned components?" --quiet

Tool calls are announced on stderr (so the streamed answer on stdout stays
clean) — this is how we watch Claude's tool-call pattern, the data ADR-014's
Option-B revival trigger depends on. Suppress with --quiet.
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
from app.intelligence.orchestration.system_prompt import build_system_prompt
from app.intelligence.orchestration.tool_definitions import build_tools
from app.salesforce.token_storage import load_tokens

# Load .env explicitly so ANTHROPIC_API_KEY is present before the client is
# constructed — don't rely on the incidental load_dotenv() in auth.py.
load_dotenv()

_CACHE_PATH = Path("data") / "metadata_cache.db"


async def _load() -> tuple[QueryEngine, "MetadataGraph", MetadataCache, str]:
    """Build the graph + return everything the tools need (engine, graph,
    cache, org_key). Same guard clauses as cli.py's bootstrap; ask additionally
    needs the cache + org_key for get_source."""
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


def _announce(name: str, handler):
    """Wrap a tool handler so each invocation prints to stderr before running.

    Keeps the client generic (it knows nothing about display); the CLI, as the
    consumer, decides to surface tool activity. stderr keeps the streamed answer
    on stdout uncluttered.
    """
    async def wrapped(inp: dict) -> str:
        print(f"  [tool] {name}({inp})", file=sys.stderr, flush=True)
        return await handler(inp)

    return wrapped


async def _ask(question: str, *, show_tools: bool = True) -> None:
    engine, graph, cache, org_key = await _load()
    system_prompt = build_system_prompt(graph)
    schemas, handlers = build_tools(engine, graph, cache, org_key)

    client = ClaudeClient(system_prompt=system_prompt)
    for tool_name, handler in handlers.items():
        client.register_tool(
            tool_name,
            _announce(tool_name, handler) if show_tools else handler,
        )

    print(f"\nQ: {question}\n")
    async for chunk in client.ask(question, tools=schemas):
        print(chunk, end="", flush=True)
    print("\n")
    # Cost/usage to stderr so it doesn't mix into the answer if piped.
    print(client.session.summary(), file=sys.stderr)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ask",
        description="Ask Claude about your Salesforce org's metadata graph.",
    )
    parser.add_argument("question", help="natural-language question (quote it)")
    parser.add_argument(
        "--quiet", "-q", action="store_true",
        help="don't announce which tools Claude calls",
    )
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    asyncio.run(_ask(args.question, show_tools=not args.quiet))


if __name__ == "__main__":
    main()
