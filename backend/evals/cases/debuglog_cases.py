"""Eval cases for debuglog mode — Apex debug-log root-cause analysis (Week 12).

Two fixtures, both format-valid Salesforce logs (real event keywords/structure;
synthetic, PII-free IDs and data):
  - debuglog_case_exception.log: a Case trigger-framework run that throws a
    DmlException. Names REAL graph components (CaseObjectTrigger,
    Case_Trigger_Handler, TriggerHandler) so it correlates against the live
    graph — exercises the grounding path.
  - debuglog_flow_only.log: an Opportunity Flow-only run with NO Apex units —
    exercises the honesty path (don't manufacture an Apex cause; the
    Opportunity-is-Flow-driven finding from Day 3, baked into an eval).

Assertions follow the Week-10 lesson: assert what we're GUARDING (grounding in
the real failing unit; no invented Apex cause for a Flow-only log), not the
exact phrasing of a correct answer.
"""
from evals.eval_case import EvalCase

_EXC = "evals/fixtures/debuglog_case_exception.log"
_FLOW = "evals/fixtures/debuglog_flow_only.log"

CASES = [
    EvalCase(
        description="Identifies the failing Apex unit from the log",
        query="What failed and which Apex class is implicated?",
        mode="debuglog",
        log=_EXC,
        required=["Case_Trigger_Handler", "DmlException"],
        forbidden=[],
    ),
    EvalCase(
        description="Lists the Apex units that actually executed",
        query="Which Apex units executed in this transaction?",
        mode="debuglog",
        log=_EXC,
        required=["Case_Trigger_Handler", "TriggerHandler"],
        forbidden=[],
    ),
    EvalCase(
        description="Discriminates an Apex failure from Flow automation",
        query="Is this failure rooted in Apex or in Flow?",
        mode="debuglog",
        log=_EXC,
        required=["Apex"],
        forbidden=[],
    ),
    EvalCase(
        description="Flow-only log: reports Flow, doesn't blame an Apex class",
        query="What ran in this transaction, and was there an Apex failure?",
        mode="debuglog",
        log=_FLOW,
        required=["Flow"],
        forbidden=["Case_Trigger_Handler"],
    ),
    EvalCase(
        description="Flow-only log: does not manufacture an Apex root cause",
        query="Which Apex class caused this?",
        mode="debuglog",
        log=_FLOW,
        required=[],
        # No Apex units ran — must not invent one (the honesty guard).
        forbidden=["Case_Trigger_Handler", "TriggerHandler", "CaseObjectTrigger"],
    ),
]
