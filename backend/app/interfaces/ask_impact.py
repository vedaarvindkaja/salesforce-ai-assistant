"""Deployment impact entry point — thin wrapper over ask_cli (Week 9 Day 4).

Clean portfolio module name: `python -m app.interfaces.ask_impact "..."`. All
logic lives in ask_cli.main(); this only pins the default mode.

Scope note: impact mode runs get_source-free (graph topology is sufficient for
blast-radius analysis — verified Day 4). The structured output (DIRECT /
TRANSITIVE / MECHANISM / RISK / CHECKS) is graph-grounded in its SKELETON —
every named component is a real node/edge — but the risk COMMENTARY is advisory
interpretation, not graph-established fact. Week-10 refinement #10 (edge labels
on find_dependencies) should let Claude state mechanism precisely and reduce
that interpretive gap.
"""
from app.interfaces.ask_cli import main

if __name__ == "__main__":
    main(default_mode="impact")