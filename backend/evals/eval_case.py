"""Eval case definition — the unit of work for the semantic eval harness.

A case specifies:
  - query: the natural-language question sent to the capability
  - mode: which capability handles it (qa/apex/soql/impact)
  - required: strings that MUST appear in the output (grounding + structure)
  - forbidden: strings that must NOT appear (known failure modes)
  - description: what this case is testing (for the report)

Assertions are substring checks on the full AI output — coarse but fast,
determinism-friendly, and sufficient to catch the failure modes we care about.
"""
from dataclasses import dataclass, field


@dataclass
class EvalCase:
    description: str
    query: str
    mode: str
    required: list[str] = field(default_factory=list)
    forbidden: list[str] = field(default_factory=list)