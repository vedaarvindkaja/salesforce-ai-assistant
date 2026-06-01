"""Semantic eval runner for the AI metadata graph capabilities.

Runs live API calls against Claude with the real cached graph. Each case
asserts required strings are present and forbidden strings are absent in
the AI output.

Usage:
    python -m evals.eval_runner                    # all capabilities
    python -m evals.eval_runner --mode impact      # one capability
    python -m evals.eval_runner --mode impact qa   # multiple

Cost: ~$0.035/case average. 20 cases ~ $0.70 per full run.
NOT included in the default pytest suite (live API calls, real cost).
Run deliberately as a regression check, not on every commit.

Output on pass: one line per case.
Output on failure: full AI response printed so you can diagnose without
re-running.
"""
from __future__ import annotations

import argparse
import asyncio
import io
import sys
import time
from contextlib import redirect_stdout

from evals.cases.apex_cases import CASES as APEX_CASES
from evals.cases.impact_cases import CASES as IMPACT_CASES
from evals.cases.qa_cases import CASES as QA_CASES
from evals.cases.soql_cases import CASES as SOQL_CASES
from evals.eval_case import EvalCase

ALL_CASES: dict[str, list[EvalCase]] = {
    "qa": QA_CASES,
    "apex": APEX_CASES,
    "soql": SOQL_CASES,
    "impact": IMPACT_CASES,
}

# Colour codes — degrade gracefully on terminals that don't support them
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"
BOLD = "\033[1m"


def _run_case(case: EvalCase) -> tuple[bool, str, list[str]]:
    """Run one eval case. Returns (passed, ai_output, failure_reasons)."""
    # Import here so the module can be imported without triggering graph load
    from app.interfaces.ask_cli import _ask

    buf = io.StringIO()
    with redirect_stdout(buf):
        asyncio.run(_ask(case.query, mode=case.mode, show_tools=False))
    output = buf.getvalue()

    failures: list[str] = []
    for req in case.required:
        if req not in output:
            failures.append(f"REQUIRED not found: {req!r}")
    for forb in case.forbidden:
        if forb in output:
            failures.append(f"FORBIDDEN found: {forb!r}")

    return (len(failures) == 0), output, failures


def _run_suite(
    modes: list[str],
) -> tuple[int, int]:
    """Run all cases for the given modes. Returns (passed, total)."""
    passed = total = 0

    for mode in modes:
        cases = ALL_CASES[mode]
        print(f"\n{BOLD}── {mode.upper()} ({len(cases)} cases) ──{RESET}")

        for i, case in enumerate(cases, 1):
            total += 1
            start = time.monotonic()
            ok, output, reasons = _run_case(case)
            elapsed = time.monotonic() - start

            if ok:
                passed += 1
                print(f"  {GREEN}PASS{RESET} [{elapsed:.1f}s] {case.description}")
            else:
                print(f"  {RED}FAIL{RESET} [{elapsed:.1f}s] {case.description}")
                for r in reasons:
                    print(f"       {YELLOW}↳ {r}{RESET}")
                print(f"\n  {'─'*60}")
                print(f"  Full AI output for case {i} ({mode}):")
                print(f"  {'─'*60}")
                for line in output.splitlines():
                    print(f"  {line}")
                print(f"  {'─'*60}\n")

    return passed, total


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run semantic evals for the Salesforce AI metadata graph."
    )
    parser.add_argument(
        "--mode",
        nargs="*",
        choices=list(ALL_CASES.keys()),
        default=None,
        help="Capabilities to eval. Omit to run all.",
    )
    args = parser.parse_args()
    modes = args.mode or list(ALL_CASES.keys())

    print(f"{BOLD}Salesforce AI Metadata Graph — Semantic Eval Suite{RESET}")
    print(f"Modes: {', '.join(modes)}")
    print(f"Cases: {sum(len(ALL_CASES[m]) for m in modes)}")
    print(f"Note: live API calls — costs ~$0.035/case\n")

    passed, total = _run_suite(modes)

    print(f"\n{BOLD}{'═'*50}{RESET}")
    color = GREEN if passed == total else RED
    print(f"{color}{BOLD}  {passed}/{total} passed{RESET}")
    if passed < total:
        print(f"  {total - passed} failed")
    print(f"{'═'*50}\n")

    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()