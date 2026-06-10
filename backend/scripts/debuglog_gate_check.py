"""Day-3 go/no-go gate for the debug-log capability (Week 12).

Evaluates the PRE-COMMITTED, LOCKED bar against a real debug log + the live
metadata graph — no rationalizing after the fact:

  Clause 1: >=1 apex_unit from METHOD_ENTRY or EXCEPTION_THROWN is a graph node.
            (CODE_UNIT Flow/trigger wrappers alone do NOT satisfy this.)
  Clause 2: >=30% of the DISTINCT apex_units extracted from
            METHOD_ENTRY / CODE_UNIT / EXCEPTION_THROWN are graph nodes.

Both must hold to CONTINUE to Day 4. Otherwise STOP, write the revival note,
and spend Days 4-6 on REST hardening + eval expansion (the pre-agreed branch).

Run from backend/:
  python -m scripts.debuglog_gate_check tests/fixtures/debuglog/case_trigger.log
"""
from __future__ import annotations

import asyncio
import sys

from app.intelligence.debuglog.parser import parse_debug_log_file
from app.intelligence.graph.bootstrap import load_graph

_THRESHOLD = 0.30
_DENOM_TYPES = (
    "METHOD_ENTRY", "METHOD_EXIT",
    "CODE_UNIT_STARTED", "CODE_UNIT_FINISHED",
    "EXCEPTION_THROWN",
)
_CLAUSE1_TYPES = ("METHOD_ENTRY", "EXCEPTION_THROWN")


async def main(log_path: str) -> int:
    result = parse_debug_log_file(log_path)
    _engine, graph, _cache, org_key = await load_graph()
    node_names = {n.name for n in graph.all_nodes()}

    denom = result.apex_units_from(*_DENOM_TYPES)
    clause1_units = result.apex_units_from(*_CLAUSE1_TYPES)

    hits = denom & node_names
    clause1_hits = clause1_units & node_names
    overlap = (len(hits) / len(denom)) if denom else 0.0

    print(f"Log:              {log_path}")
    print(f"org_key:          {org_key}")
    print(f"graph nodes:      {len(node_names)}")
    print(f"apex_units:       {sorted(denom)}")
    print(f"  in graph:       {sorted(hits)}")
    print(f"  NOT in graph:   {sorted(denom - node_names)}")
    print(f"clause-1 units:   {sorted(clause1_units)}  (METHOD_ENTRY/EXCEPTION_THROWN)")
    print(f"  in graph:       {sorted(clause1_hits)}")
    print()

    clause1 = len(clause1_hits) >= 1
    clause2 = overlap >= _THRESHOLD
    print(f"Clause 1  (>=1 METHOD_ENTRY/EXCEPTION unit is a graph node):  "
          f"{'PASS' if clause1 else 'FAIL'}")
    print(f"Clause 2  (>={_THRESHOLD:.0%} of distinct apex_units are nodes):    "
          f"{overlap:.0%}  ->  {'PASS' if clause2 else 'FAIL'}")
    print()
    verdict = clause1 and clause2
    print("GATE:", "PASS  ->  continue to Day 4"
          if verdict else "FAIL  ->  STOP, write the revival note")
    return 0 if verdict else 1


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "tests/fixtures/debuglog/case_trigger.log"
    raise SystemExit(asyncio.run(main(path)))
