"""SOQL generation entry point — thin wrapper over ask_cli (Week 9 Day 3).

Clean portfolio module name: `python -m app.interfaces.ask_soql "..."`. All
logic lives in ask_cli.main(); this only pins the default mode.

Scope note (ADR-010): soql mode grounds custom/queried fields in real source
via get_source, but the graph has NO field nodes — standard fields rest on
platform priors, not org verification. The prompt makes Claude label per-field
provenance ('confirmed in source' vs 'standard Salesforce field') so the
boundary is visible in every answer.
"""
from app.interfaces.ask_cli import main

if __name__ == "__main__":
    main(default_mode="soql")