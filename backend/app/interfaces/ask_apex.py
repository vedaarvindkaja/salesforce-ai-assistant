"""Apex explanation/refactoring entry point — thin wrapper over ask_cli (Week 9 Day 2).

A clean module name for the portfolio: `python -m app.interfaces.ask_apex "..."`
reads better than `--mode apex` and signals the capability directly. All logic
lives in ask_cli.main(); this only pins the default mode. The --mode flag still
works, so an explicit override is possible but pointless here.
"""
from app.interfaces.ask_cli import main

if __name__ == "__main__":
    main(default_mode="apex")