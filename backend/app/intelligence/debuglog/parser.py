# No direct Apex equivalent — Salesforce debug-log parser (text -> structured events).
"""Salesforce Apex debug-log parser (Week 12, Capability 5, Day 3).

Pure: raw debug-log text in, structured events out. No graph, no Claude, no
network — that purity is what makes it independently testable and lets the Day-3
gate evaluate it in isolation. Graph correlation is strictly Day 4's job.

Strategy (accepted Day 3):
  - Generic tokenizer: every event line -> (timestamp, nanos, event_type,
    fields). Unmodelled event types are captured generically, never dropped and
    never crash the parse — resilience is the whole point of "reliably extracts".
  - Lean model: one LogEvent plus a few derived convenience fields (code_line,
    apex_unit, apex_class_id), populated only for the events that carry them.

Log shape handled (verified against real Opportunity + Case logs):
  - Line 1: header  "<api> CAT,LEVEL;CAT,LEVEL;..."
  - Optional "Execute Anonymous: ..." source echo (anon-block runs only)
  - Event lines:  HH:MM:SS.fff (elapsed_nanos)|EVENT_TYPE|field|field|...
  - Continuation lines (no leading timestamp): the FATAL_ERROR stack, the
    indented LIMIT_USAGE_FOR_NS block, etc. -> attached to the preceding event.
"""
from __future__ import annotations

import dataclasses
import re
from dataclasses import dataclass

# Event line: "07:14:16.1 (10116467)|METHOD_ENTRY|[1]|01p...|Class.method()"
_EVENT_RE = re.compile(
    r"^(?P<ts>\d{2}:\d{2}:\d{2}\.\d+) \((?P<nanos>\d+)\)\|(?P<etype>[A-Z_]+)(?:\|(?P<rest>.*))?$"
)
# A leading "[123]" source-line marker (NOT "[EXTERNAL]").
_LINE_MARKER_RE = re.compile(r"^\[(\d+)\]$")
# A Salesforce id (01p... ApexClass, 01q... ApexTrigger), 15 or 18 chars.
_SFID_RE = re.compile(r"^[a-zA-Z0-9]{15,18}$")
# Header: "64.0 APEX_CODE,FINEST;DB,INFO;..."
_HEADER_RE = re.compile(
    r"^(?P<ver>\d+\.\d+)\s+(?P<cats>[A-Z_]+,[A-Z]+(?:;[A-Z_]+,[A-Z]+)*)\s*$"
)
_SOURCE_ECHO_PREFIX = "Execute Anonymous:"


@dataclass(frozen=True)
class LogEvent:
    """One parsed debug-log event.

    `fields` keeps the raw pipe-delimited tail verbatim; the derived fields are
    populated only for the event types that actually carry that information.
    """

    line_no: int                      # 1-based line index in the source log
    timestamp: str                    # wall-clock portion, e.g. "07:14:16.1"
    nanos: int                        # elapsed-time counter (the value in parens)
    event_type: str                   # e.g. "METHOD_ENTRY"
    fields: tuple[str, ...]           # raw fields after the event type
    detail: str = ""                  # continuation lines (stack / limit block)
    code_line: int | None = None      # the [N] source-line marker, if present
    apex_unit: str | None = None      # Apex class/trigger name, if this event names one
    apex_class_id: str | None = None  # 01p.../01q... id, if present


@dataclass(frozen=True)
class DebugLogParseResult:
    """Everything extracted from one debug log."""

    api_version: str | None
    log_categories: dict          # {"APEX_CODE": "FINEST", ...}
    events: tuple                 # tuple[LogEvent, ...]

    def by_type(self, event_type: str) -> list:
        return [e for e in self.events if e.event_type == event_type]

    def apex_units(self) -> set:
        """Distinct Apex class/trigger names named by any event — the set the
        Day-3 correlation gate intersects with graph node names."""
        return {e.apex_unit for e in self.events if e.apex_unit}

    def apex_units_from(self, *event_types: str) -> set:
        """Distinct apex_unit names restricted to the given event types."""
        wanted = set(event_types)
        return {e.apex_unit for e in self.events if e.apex_unit and e.event_type in wanted}

    def apex_class_ids(self) -> set:
        return {e.apex_class_id for e in self.events if e.apex_class_id}


# ------------------------------------------------------------------
# Derivation helpers — turn raw fields into the convenience fields.
# ------------------------------------------------------------------

def _strip_method_args(sig: str) -> str:
    """'TriggerHandler.setTriggerContext(String, Boolean)' -> '...setTriggerContext'."""
    paren = sig.find("(")
    return sig[:paren] if paren != -1 else sig


def _class_from_method_sig(sig: str) -> str | None:
    """'Case_Trigger_Handler.beforeInsert()' -> 'Case_Trigger_Handler'.
    Inner classes ('A.B.m()') keep their outer qualifier ('A.B')."""
    base = _strip_method_args(sig)
    if "." not in base:
        return None
    return base.rsplit(".", 1)[0]


def _derive(event_type: str, fields: tuple[str, ...]):
    """Return (code_line, apex_unit, apex_class_id) for one event."""
    code_line = apex_unit = apex_class_id = None

    if fields:
        m = _LINE_MARKER_RE.match(fields[0])
        if m:
            code_line = int(m.group(1))

    if event_type in ("METHOD_ENTRY", "METHOD_EXIT"):
        # [line] | <classId> | Class.method(args)
        if len(fields) >= 3 and _SFID_RE.match(fields[1]):
            apex_class_id = fields[1]
            apex_unit = _class_from_method_sig(fields[2])
        elif len(fields) >= 2:
            apex_unit = _class_from_method_sig(fields[-1])

    elif event_type in ("CONSTRUCTOR_ENTRY", "CONSTRUCTOR_EXIT"):
        # [line] | <classId> | <init>(args) | ClassName
        if len(fields) >= 2 and _SFID_RE.match(fields[1]):
            apex_class_id = fields[1]
        if fields and "(" not in fields[-1]:
            apex_unit = fields[-1]  # explicit class name is the trailing field

    elif event_type in ("CODE_UNIT_STARTED", "CODE_UNIT_FINISHED"):
        # Apex trigger unit: "...|__sfdc_trigger/CaseObjectTrigger" (+ a 01q id).
        # Workflow:Case / SLA / Flow:Opportunity / TRIGGERS are NOT Apex units.
        for f in fields:
            if f.startswith("__sfdc_trigger/"):
                apex_unit = f.split("/", 1)[1]
            elif _SFID_RE.match(f) and (f.startswith("01q") or f.startswith("01p")):
                apex_class_id = f

    return code_line, apex_unit, apex_class_id


# ------------------------------------------------------------------
# Parser entry points
# ------------------------------------------------------------------

def parse_debug_log(text: str) -> DebugLogParseResult:
    """Parse raw debug-log text into a DebugLogParseResult."""
    lines = text.splitlines()
    api_version: str | None = None
    categories: dict = {}
    events: list = []

    start = 0
    if lines:
        hm = _HEADER_RE.match(lines[0])
        if hm:
            api_version = hm.group("ver")
            for pair in hm.group("cats").split(";"):
                cat, _, lvl = pair.partition(",")
                categories[cat] = lvl
            start = 1

    # continuation lines for the most-recent event, by its index in `events`
    detail_acc: dict = {}

    for i in range(start, len(lines)):
        raw = lines[i]
        m = _EVENT_RE.match(raw)
        if m:
            rest = m.group("rest")
            fields = tuple(rest.split("|")) if rest else ()
            code_line, apex_unit, apex_class_id = _derive(m.group("etype"), fields)
            events.append(
                LogEvent(
                    line_no=i + 1,
                    timestamp=m.group("ts"),
                    nanos=int(m.group("nanos")),
                    event_type=m.group("etype"),
                    fields=fields,
                    code_line=code_line,
                    apex_unit=apex_unit,
                    apex_class_id=apex_class_id,
                )
            )
            continue

        # Non-event line:
        if raw.startswith(_SOURCE_ECHO_PREFIX) or raw.strip() == "":
            continue  # anon-block source echo, or blank — not signal
        if events:  # continuation of the preceding event (stack frame / limit block)
            detail_acc.setdefault(len(events) - 1, []).append(raw)

    if detail_acc:
        events = [
            dataclasses.replace(ev, detail="\n".join(detail_acc[idx]))
            if idx in detail_acc else ev
            for idx, ev in enumerate(events)
        ]

    return DebugLogParseResult(
        api_version=api_version,
        log_categories=categories,
        events=tuple(events),
    )


def parse_debug_log_file(path) -> DebugLogParseResult:
    """Convenience: parse a debug log from a file path (UTF-8)."""
    from pathlib import Path

    return parse_debug_log(Path(path).read_text(encoding="utf-8"))
