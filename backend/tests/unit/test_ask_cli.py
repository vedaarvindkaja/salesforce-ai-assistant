"""Hermetic tests for the ask CLI's pure parts (Week 8 Day 6).

The live API call is verified manually (it costs money and is
non-deterministic). What IS hermetically testable: the argparse wiring and the
_announce tool-wrapper. Those are pure and worth guarding.
"""
import pytest

from app.interfaces import ask_cli


# ------------------------------------------------------------------
# Argument parsing
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
# _announce wrapper — preserves behaviour, announces on stderr
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
    # Announcement goes to stderr, not stdout (keeps streamed answer clean).
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
