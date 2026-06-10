"""Hermetic tests for the ask CLI's pure parts.

Week 8 Day 6: argparse wiring + _announce tool-wrapper.
Week 9 Day 1: --mode flag + CAPABILITY_REGISTRY (mode-dispatch).
Week 12 Day 4: debuglog is the 5th capability; analyze_debug_log is a
debuglog-only tool that sits outside the standard _ALL_TOOLS set.

The live API call is verified manually (costs money, non-deterministic).
What IS hermetically testable: parsing, the registry contract, and the
tool-subsetting decision (which lives in the registry, not in _ask).
"""
import pytest

from app.interfaces import ask_cli


# ------------------------------------------------------------------
# Argument parsing — question + quiet (Week 8, unchanged)
# ------------------------------------------------------------------

def test_parser_question_positional():
    args = ask_cli._build_parser().parse_args(["what depends on Opportunity?"])
    assert args.question == "what depends on Opportunity?"
    assert args.quiet is False


def test_parser_quiet_flag():
    args = ask_cli._build_parser().parse_args(["q", "--quiet"])
    assert args.quiet is True


def test_parser_quiet_short_flag():
    args = ask_cli._build_parser().parse_args(["q", "-q"])
    assert args.quiet is True


def test_parser_requires_question():
    with pytest.raises(SystemExit):
        ask_cli._build_parser().parse_args([])


# ------------------------------------------------------------------
# --mode flag (Week 9)
# ------------------------------------------------------------------

def test_parser_default_mode_is_qa():
    args = ask_cli._build_parser().parse_args(["q"])
    assert args.mode == "qa"


def test_parser_accepts_each_valid_mode():
    for mode in ("qa", "apex", "soql", "impact", "debuglog"):
        args = ask_cli._build_parser().parse_args(["q", "--mode", mode])
        assert args.mode == mode


def test_parser_mode_short_flag():
    args = ask_cli._build_parser().parse_args(["q", "-m", "apex"])
    assert args.mode == "apex"


def test_parser_rejects_unknown_mode():
    with pytest.raises(SystemExit):
        ask_cli._build_parser().parse_args(["q", "--mode", "garbage"])


def test_parser_default_mode_override():
    # Thin wrappers (ask_apex.py) set their own default via default_mode.
    args = ask_cli._build_parser(default_mode="apex").parse_args(["q"])
    assert args.mode == "apex"


def test_parser_explicit_mode_beats_default_override():
    # Even a wrapper's default can be overridden on the command line.
    args = ask_cli._build_parser(default_mode="apex").parse_args(["q", "-m", "soql"])
    assert args.mode == "soql"


# ------------------------------------------------------------------
# CAPABILITY_REGISTRY contract (Week 9)
# ------------------------------------------------------------------

def test_registry_has_all_five_capabilities():
    assert set(ask_cli.CAPABILITY_REGISTRY) == {"qa", "apex", "soql", "impact", "debuglog"}


def test_registry_every_mode_maps_to_builder_and_toolset():
    for mode, (builder, tools) in ask_cli.CAPABILITY_REGISTRY.items():
        assert callable(builder), f"{mode} builder must be callable"
        assert isinstance(tools, set) and tools, f"{mode} must have a non-empty toolset"


def test_registry_impact_excludes_get_source():
    _, impact_tools = ask_cli.CAPABILITY_REGISTRY["impact"]
    assert "get_source" not in impact_tools
    # but still has the graph-query tools
    assert "analyze_impact" in impact_tools
    assert "find_references_to" in impact_tools


def test_registry_non_impact_modes_include_get_source():
    for mode in ("qa", "apex", "soql"):
        _, tools = ask_cli.CAPABILITY_REGISTRY[mode]
        assert "get_source" in tools, f"{mode} should allow get_source"


def test_registry_toolsets_are_subsets_of_all_tools():
    # No mode can name a tool that doesn't exist in the full catalogue.
    # analyze_debug_log is a debuglog-only specialized tool, not part of the
    # standard _ALL_TOOLS set, so include it in the valid-names universe.
    valid = ask_cli._ALL_TOOLS | {"analyze_debug_log"}
    for mode, (_, tools) in ask_cli.CAPABILITY_REGISTRY.items():
        assert tools <= valid, f"{mode} names an unknown tool"


def test_valid_modes_matches_registry():
    assert set(ask_cli.VALID_MODES) == set(ask_cli.CAPABILITY_REGISTRY)


# ------------------------------------------------------------------
# _announce wrapper — preserves behaviour, announces on stderr (Week 8)
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_announce_returns_handler_result():
    async def fake_handler(inp: dict) -> str:
        return f"result for {inp['name']}"

    wrapped = ask_cli._announce("analyze_impact", fake_handler)
    out = await wrapped({"name": "Opportunity"})
    assert out == "result for Opportunity"


@pytest.mark.asyncio
async def test_announce_prints_to_stderr(capsys):
    async def fake_handler(inp: dict) -> str:
        return "ok"

    wrapped = ask_cli._announce("get_source", fake_handler)
    await wrapped({"name": "PricingFlowAction"})
    captured = capsys.readouterr()
    assert "[tool] get_source" in captured.err
    assert "PricingFlowAction" in captured.err
    assert captured.out == ""


@pytest.mark.asyncio
async def test_announce_passes_input_through():
    seen = {}

    async def fake_handler(inp: dict) -> str:
        seen.update(inp)
        return "ok"

    wrapped = ask_cli._announce("find_by_name", fake_handler)
    await wrapped({"query": "Opp", "extra": 1})
    assert seen == {"query": "Opp", "extra": 1}


# ------------------------------------------------------------------
# debuglog input — --log flag + the log-reference guard (Week 12 Day 5)
# ------------------------------------------------------------------

def test_parser_log_flag():
    args = ask_cli._build_parser().parse_args(
        ["q", "--mode", "debuglog", "--log", "run.log"]
    )
    assert args.log == "run.log"


def test_parser_log_defaults_none():
    args = ask_cli._build_parser().parse_args(["q"])
    assert args.log is None


def test_ask_debuglog_requires_log():
    import asyncio
    # The --log guard fires before _load(), so this never touches the cache.
    with pytest.raises(SystemExit):
        asyncio.run(ask_cli._ask("q", mode="debuglog", log=None))
