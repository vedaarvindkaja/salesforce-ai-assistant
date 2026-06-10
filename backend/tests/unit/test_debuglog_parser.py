"""Hermetic tests for the debug-log parser (Week 12, Day 3).

Uses a compact SYNTHETIC log (faithful to the real Opportunity/Case format, but
with no org PII) so the tests are self-contained and the parser's contract is
pinned independent of any captured file. Covers: header parse, source-echo skip,
apex_unit/apex_class_id derivation for METHOD_ENTRY / CONSTRUCTOR / trigger
CODE_UNIT, continuation capture, and generic capture of an unknown event type.
"""
from app.intelligence.debuglog.parser import parse_debug_log

SYNTH = """64.0 APEX_CODE,FINEST;DB,INFO;SYSTEM,DEBUG
Execute Anonymous: System.debug('hi');
07:14:16.1 (1485342)|USER_INFO|[EXTERNAL]|005xx|user@example.com|GMT
07:14:16.1 (1591415)|EXECUTION_STARTED
07:14:16.1 (1619115)|CODE_UNIT_STARTED|[EXTERNAL]|TRIGGERS
07:14:16.1 (1656606)|CODE_UNIT_STARTED|[EXTERNAL]|01q000000000001|MyTrigger on Case trigger event BeforeInsert|__sfdc_trigger/MyTrigger
07:14:16.1 (10116467)|METHOD_ENTRY|[1]|01p000000000001|Handler.Handler()
07:14:16.1 (10459985)|CONSTRUCTOR_ENTRY|[2]|01p000000000001|<init>()|Handler
07:14:16.1 (13802616)|METHOD_ENTRY|[24]|01p000000000002|Base.setContext(String, Boolean)
07:14:16.1 (3122776)|USER_DEBUG|[1]|DEBUG|hello world
07:14:16.1 (101456792)|SOQL_EXECUTE_BEGIN|[11]|Aggregations:0|SELECT Id FROM Account LIMIT 1
07:14:16.1 (129857295)|EXCEPTION_THROWN|[20]|System.DmlException: boom REQUIRED_FIELD_MISSING
07:14:16.1 (130846719)|FATAL_ERROR|System.DmlException: boom

Class.Handler: line 44, column 1
07:14:16.1 (130864680)|SOME_FUTURE_EVENT|[5]|whatever|payload
07:14:16.130 (130900000)|LIMIT_USAGE_FOR_NS|(default)|
  Number of SOQL queries: 1 out of 100
  Number of DML statements: 1 out of 150
07:14:16.1 (130974622)|CODE_UNIT_FINISHED|execute_anonymous_apex
07:14:16.1 (130987483)|EXECUTION_FINISHED
"""


def _parsed():
    return parse_debug_log(SYNTH)


def test_header_parsed():
    r = _parsed()
    assert r.api_version == "64.0"
    assert r.log_categories["APEX_CODE"] == "FINEST"
    assert r.log_categories["DB"] == "INFO"


def test_source_echo_and_blank_lines_skipped():
    r = _parsed()
    # No event should be the "Execute Anonymous:" echo line.
    assert all(e.event_type != "Execute" for e in r.events)
    assert not any("Execute Anonymous" in "".join(e.fields) for e in r.events)


def test_method_entry_units_and_ids():
    r = _parsed()
    me = r.by_type("METHOD_ENTRY")
    assert len(me) == 2
    assert {e.apex_unit for e in me} == {"Handler", "Base"}
    assert {e.apex_class_id for e in me} == {"01p000000000001", "01p000000000002"}
    # args stripped from the class derivation
    base = next(e for e in me if e.apex_unit == "Base")
    assert base.code_line == 24


def test_constructor_class_name_is_trailing_field():
    r = _parsed()
    ctor = r.by_type("CONSTRUCTOR_ENTRY")[0]
    assert ctor.apex_unit == "Handler"          # explicit trailing class name
    assert ctor.apex_class_id == "01p000000000001"


def test_trigger_code_unit_becomes_apex_unit():
    r = _parsed()
    units = r.apex_units()
    assert "MyTrigger" in units                 # from __sfdc_trigger/MyTrigger
    # the bare TRIGGERS marker and execute_anonymous_apex are NOT apex units
    assert "TRIGGERS" not in units
    assert "execute_anonymous_apex" not in units


def test_apex_units_aggregate():
    r = _parsed()
    assert r.apex_units() == {"Handler", "Base", "MyTrigger"}
    assert r.apex_units_from("METHOD_ENTRY", "EXCEPTION_THROWN") == {"Handler", "Base"}


def test_unknown_event_captured_generically():
    r = _parsed()
    unknown = r.by_type("SOME_FUTURE_EVENT")
    assert len(unknown) == 1
    assert unknown[0].fields == ("[5]", "whatever", "payload")
    assert unknown[0].apex_unit is None         # not crash, not fabricated


def test_continuation_attached_to_previous_event():
    r = _parsed()
    fatal = r.by_type("FATAL_ERROR")[0]
    assert "Class.Handler: line 44" in fatal.detail
    limit = r.by_type("LIMIT_USAGE_FOR_NS")[0]
    assert "Number of SOQL queries: 1 out of 100" in limit.detail


def test_soql_and_debug_payloads():
    r = _parsed()
    soql = r.by_type("SOQL_EXECUTE_BEGIN")[0]
    assert soql.fields[-1] == "SELECT Id FROM Account LIMIT 1"
    dbg = r.by_type("USER_DEBUG")[0]
    assert dbg.fields[-1] == "hello world"
    assert dbg.code_line == 1


def test_exception_has_line_no_unit():
    r = _parsed()
    exc = r.by_type("EXCEPTION_THROWN")[0]
    assert exc.code_line == 20
    assert exc.apex_unit is None                # message isn't a class name
