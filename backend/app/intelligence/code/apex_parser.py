# ============================================================
# PYTHON CODE
# ============================================================
"""Apex pattern parser — extract structured facts from Apex source bodies.

Extracts four categories of reference from Apex class/trigger bodies using
regex patterns. This is intentionally NOT a full AST parse (ADR-006: ship
the useful 80% now; ANTLR is Phase 2).

Pre-processing: comments are stripped before any pattern runs (Fix 1).
This eliminates false positives from Javadoc, inline comments, and URLs
that happen to match field/class/SOQL patterns.

Extracted facts feed the graph builder (Day 3) to create Object/Field nodes
and edges. The parser is pure — it takes a string body and returns a
ParseResult dataclass. No I/O, no cache access, no graph dependency.

Known limitations (documented, not hidden):
  - False positives: patterns may still match inside string literals
    (e.g. Database.query('SELECT Id FROM Account')).
  - False negatives: misses dynamic field access (obj.get('Field__c')),
    dynamic SOQL (Database.query(soqlString)), variable names that shadow
    class names.
  - Field-ref pattern requires dot-notation — bare field names without a
    qualifier are not extracted.
  - DML pattern captures the first non-'new' token after the keyword; if
    that token is a variable name (not a class name), it's recorded as-is.

These are the same trade-offs as ADR-006/007 for the reference analyzer.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


# ------------------------------------------------------------------
# Comment stripping (Fix 1)
# ------------------------------------------------------------------

# Block comments: /* ... */ including multi-line (re.DOTALL)
_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)

# Line comments: // ... to end of line
_LINE_COMMENT = re.compile(r"//[^\n]*")


def _strip_comments(body: str) -> str:
    """Remove // line comments and /* */ block comments from Apex source.

    Processes block comments first (they can span lines), then line comments.
    Preserves line structure (newlines kept) so line-number-sensitive patterns
    still work if added later.
    """
    body = _BLOCK_COMMENT.sub("", body)
    body = _LINE_COMMENT.sub("", body)
    return body


# ------------------------------------------------------------------
# Compiled patterns (applied to comment-stripped body)
# ------------------------------------------------------------------

# SOQL: [SELECT ... FROM SomeObject WHERE ...]
# Captures the object name after FROM. Must appear inside square brackets
# (Apex inline SOQL syntax) to reduce false positives from prose.
# The \[ lookahead isn't feasible here since FROM may be lines away from [,
# so we match FROM + identifier and rely on comment stripping + system
# namespace filtering to remove most noise.
_SOQL_FROM = re.compile(
    r"\bFROM\s+([A-Za-z][A-Za-z0-9_]*)",
    re.IGNORECASE | re.MULTILINE,
)

# DML: insert/update/delete/upsert/merge, optionally followed by 'new',
# then the first identifier token.
# Fix 3: added optional (?:new\s+)? group to skip the 'new' keyword so
# 'insert new Account(...)' captures 'Account', not 'new'.
_DML_OP = re.compile(
    r"\b(insert|update|delete|upsert|merge)\s+(?:new\s+)?([A-Za-z][A-Za-z0-9_]*)",
    re.IGNORECASE,
)

# Field references: qualifier.member in dot-notation (not followed by '(').
_FIELD_REF = re.compile(
    r"\b([A-Za-z][A-Za-z0-9_]*)\.([A-Za-z][A-Za-z0-9_]*)\b",
)

# Method calls: qualifier.method( — same base pattern but followed by '('.
_METHOD_CALL = re.compile(
    r"\b([A-Za-z][A-Za-z0-9_]*)\.([A-Za-z][A-Za-z0-9_]*)\s*\(",
)

# Known Apex system namespaces — excluded from field/class refs and SOQL.
_SYSTEM_NAMESPACES = frozenset({
    "system", "schema", "database", "math", "string", "integer",
    "long", "double", "decimal", "boolean", "date", "datetime", "time",
    "blob", "id", "list", "map", "set", "type", "json", "limits",
    "userinfo", "url", "label", "trigger", "apexpages", "pagereference",
    "selectoption", "test", "exception", "dmlexception",
})

# DML tokens to skip as object names — keywords that appear after DML ops
# but are not sObject type names.
_DML_SKIP_TOKENS = frozenset({"new", "null", "this", "super"})


# ------------------------------------------------------------------
# Result types
# ------------------------------------------------------------------

@dataclass(frozen=True)
class SoqlReference:
    """An sObject name found in a SOQL FROM clause."""
    object_name: str


@dataclass(frozen=True)
class DmlReference:
    """A DML operation on an inferred sObject."""
    operation: str    # insert | update | delete | upsert | merge
    object_name: str  # first non-'new' token after the DML keyword


@dataclass(frozen=True)
class FieldReference:
    """A dot-notation field access: qualifier.field_name."""
    qualifier: str    # left side of dot (object name or variable name)
    field_name: str   # right side of dot


@dataclass(frozen=True)
class ClassReference:
    """A static or instance method call on another class."""
    class_name: str
    method_name: str


@dataclass
class ParseResult:
    """All structured facts extracted from one Apex body.

    Each list is deduplicated and sorted for deterministic output.
    The parser does not interpret results — it reports what it sees.
    Callers (graph builder) decide what to promote to nodes/edges.
    """
    soql_references: list[SoqlReference] = field(default_factory=list)
    dml_references: list[DmlReference] = field(default_factory=list)
    field_references: list[FieldReference] = field(default_factory=list)
    class_references: list[ClassReference] = field(default_factory=list)

    @property
    def referenced_objects(self) -> set[str]:
        """All unique object names seen (SOQL + DML)."""
        return (
            {r.object_name for r in self.soql_references}
            | {r.object_name for r in self.dml_references}
        )

    @property
    def referenced_classes(self) -> set[str]:
        """All unique class names seen in method calls."""
        return {r.class_name for r in self.class_references}


# ------------------------------------------------------------------
# Parser
# ------------------------------------------------------------------

def parse_apex_body(body: str) -> ParseResult:
    """Extract structured facts from one Apex class or trigger body.

    Strips comments first, then applies patterns to clean source.

    Args:
        body: Raw Apex source as a string. Empty string returns empty result.

    Returns:
        ParseResult with deduplicated, sorted lists of each reference type.
    """
    if not body or not body.strip():
        return ParseResult()

    clean = _strip_comments(body)

    return ParseResult(
        soql_references=_extract_soql(clean),
        dml_references=_extract_dml(clean),
        field_references=_extract_fields(clean),
        class_references=_extract_classes(clean),
    )


# ------------------------------------------------------------------
# Internal extractors
# ------------------------------------------------------------------

def _extract_soql(body: str) -> list[SoqlReference]:
    seen: set[str] = set()
    results: list[SoqlReference] = []
    for m in _SOQL_FROM.finditer(body):
        name = m.group(1)
        key = name.casefold()
        if key not in seen and key not in _SYSTEM_NAMESPACES:
            seen.add(key)
            results.append(SoqlReference(object_name=name))
    return sorted(results, key=lambda r: r.object_name.casefold())


def _extract_dml(body: str) -> list[DmlReference]:
    seen: set[tuple[str, str]] = set()
    results: list[DmlReference] = []
    for m in _DML_OP.finditer(body):
        op = m.group(1).lower()
        obj = m.group(2)
        obj_lower = obj.casefold()
        # Fix 3: skip residual keyword tokens and system namespaces.
        if obj_lower in _DML_SKIP_TOKENS or obj_lower in _SYSTEM_NAMESPACES:
            continue
        key = (op, obj_lower)
        if key not in seen:
            seen.add(key)
            results.append(DmlReference(operation=op, object_name=obj))
    return sorted(results, key=lambda r: (r.operation, r.object_name.casefold()))


def _extract_fields(body: str) -> list[FieldReference]:
    """Extract dot-notation field accesses (not followed by '(')."""
    method_positions: set[int] = {m.start() for m in _METHOD_CALL.finditer(body)}
    seen: set[tuple[str, str]] = set()
    results: list[FieldReference] = []

    for m in _FIELD_REF.finditer(body):
        if m.start() in method_positions:
            continue  # method call — handled by _extract_classes
        qualifier = m.group(1)
        member = m.group(2)
        q_lower = qualifier.casefold()
        m_lower = member.casefold()
        if q_lower in _SYSTEM_NAMESPACES or m_lower in _SYSTEM_NAMESPACES:
            continue
        key = (q_lower, m_lower)
        if key not in seen:
            seen.add(key)
            results.append(FieldReference(qualifier=qualifier, field_name=member))

    return sorted(results, key=lambda r: (r.qualifier.casefold(), r.field_name.casefold()))


def _extract_classes(body: str) -> list[ClassReference]:
    """Extract method calls where the qualifier looks like a class name.

    Fix 2: qualifiers that start with a lowercase letter are variable names
    (e.g. 'result', 'handler', 'this'), not class names. Drop them.
    Real Apex class names are PascalCase by convention.
    """
    seen: set[tuple[str, str]] = set()
    results: list[ClassReference] = []

    for m in _METHOD_CALL.finditer(body):
        qualifier = m.group(1)
        method = m.group(2)
        q_lower = qualifier.casefold()

        # Fix 2: skip lowercase-starting qualifiers — they're variable names.
        if qualifier[0].islower():
            continue
        if q_lower in _SYSTEM_NAMESPACES:
            continue

        key = (q_lower, method.casefold())
        if key not in seen:
            seen.add(key)
            results.append(ClassReference(class_name=qualifier, method_name=method))

    return sorted(results, key=lambda r: (r.class_name.casefold(), r.method_name.casefold()))


# ============================================================
# APEX EQUIVALENT (for comparison)
# ============================================================
#
#    public class ApexBodyParser {
#
#        // Fix 1 equivalent: strip comments before parsing.
#        // Apex has no built-in regex replace for block comments, but
#        // Pattern.compile works the same way.
#        private static final Pattern BLOCK_COMMENT =
#            Pattern.compile('/\\*.*?\\*/', Pattern.DOTALL);
#        private static final Pattern LINE_COMMENT =
#            Pattern.compile('//[^\\n]*');
#
#        private static String stripComments(String body) {
#            body = BLOCK_COMMENT.matcher(body).replaceAll('');
#            body = LINE_COMMENT.matcher(body).replaceAll('');
#            return body;
#        }
#
#        // Fix 3 equivalent: skip 'new' token in DML pattern.
#        // In regex: \b(insert|update|...)\s+(?:new\s+)?([A-Za-z]\w*)
#        // The (?:new\s+)? non-capturing group makes 'new' optional.
#
#        // Fix 2 equivalent: PascalCase filter for class refs.
#        // In Apex: qualifier.substring(0,1).isUpperCase() equivalent is
#        // Character.isUpperCase(qualifier.charAt(0))
#        private static Boolean isPascalCase(String name) {
#            return name != null && name.length() > 0
#                && Character.isUpperCase(name.charAt(0));
#        }
#    }
#
# Concept mapping:
# - re.compile(r"...", re.DOTALL)    → Pattern.compile("...", Pattern.DOTALL)
# - _BLOCK_COMMENT.sub("", body)    → matcher.replaceAll("")
# - qualifier[0].islower()           → Character.isLowerCase(qualifier.charAt(0))
# - frozenset({...})                 → static final Set<String> (static initializer)
# - module-level functions           → static methods on a utility class
# ============================================================
