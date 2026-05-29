# ============================================================
# PYTHON CODE
# ============================================================
"""Reference analyzer — insight A: "what references this identifier?"

Reads cached Apex bodies (classes AND triggers) and finds records
referencing a given identifier (an sObject or field name). The first
piece of the platform that produces an *answer*, not a report.

SCOPE (ADR-006): v1 is a word-boundary string scan, NOT an AST parse.
Known limitations, by design:
  - False positives: matches inside comments and string literals.
  - False negatives: misses dynamic refs (obj.get('Field'), dynamic SOQL).
  - Triggers: the declaration line (`trigger X on Account`) is caught, but
    field access via Trigger.new that never names the object/field is not.
The AST-based Apex parser (Week 7) eliminates these. v1 ships the useful
80% answer now.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.intelligence.graph.storage import MetadataCache

# Body-bearing Apex metadata types scanned by default.
# A TUPLE, not a list — so it's safe as a default argument. A mutable list
# default would be shared across every call (the same trap that
# field(default_factory=list) guards against in the dataclasses below).
DEFAULT_SCAN_TYPES: tuple[str, ...] = ("ApexClass", "ApexTrigger")


@dataclass
class Reference:
    """One metadata record that references the searched identifier."""

    metadata_type: str   # "ApexClass" | "ApexTrigger"
    record_id: str
    name: str
    line_numbers: list[int] = field(default_factory=list)

    @property
    def match_count(self) -> int:
        return len(self.line_numbers)


@dataclass
class ReferenceReport:
    """The answer to 'what references X?'"""

    identifier: str
    org_key: str
    references: list[Reference]
    records_scanned: int

    @property
    def referencing_count(self) -> int:
        return len(self.references)


def _find_lines(body: str, identifier: str) -> list[int]:
    """1-indexed line numbers where identifier appears on a word boundary.

    Word-boundary match so 'Account' doesn't match 'AccountTeamMember'.
    re.escape guards against regex metacharacters in the identifier.
    """
    pattern = re.compile(rf"\b{re.escape(identifier)}\b")
    return [
        lineno
        for lineno, line in enumerate(body.splitlines(), start=1)
        if pattern.search(line)
    ]


class ReferenceAnalyzer:
    def __init__(self, cache: MetadataCache) -> None:
        self._cache = cache

    async def find_references(
        self,
        *,
        org_key: str,
        identifier: str,
        metadata_types: tuple[str, ...] = DEFAULT_SCAN_TYPES,
    ) -> ReferenceReport:
        """Find all cached Apex records (across metadata_types) referencing
        `identifier`, ranked by match count descending."""
        references: list[Reference] = []
        records_scanned = 0

        for metadata_type in metadata_types:
            records = await self._cache.get(
                org_key=org_key, metadata_type=metadata_type
            )
            records_scanned += len(records)
            for rec in records:
                body = rec.get("Body") or ""
                lines = _find_lines(body, identifier)
                if lines:
                    references.append(
                        Reference(
                            metadata_type=metadata_type,
                            record_id=rec["Id"],
                            name=rec.get("Name", "<unknown>"),
                            line_numbers=lines,
                        )
                    )

        # Most-referenced first. NOTE (Week 6 parked): raw match-count
        # over-weights test classes and ignores that a trigger reference is
        # higher-stakes than a class reference. Weighting is a deliberate
        # later refinement, not Day 5 scope.
        references.sort(key=lambda r: r.match_count, reverse=True)

        return ReferenceReport(
            identifier=identifier,
            org_key=org_key,
            references=references,
            records_scanned=records_scanned,
        )


# ============================================================
# APEX EQUIVALENT (for comparison)
# ============================================================
# In Apex you'd iterate cached bodies of BOTH ApexClass and ApexTrigger
# and pattern-match line by line:
#
#    public class ReferenceAnalyzer {
#        public class Reference {
#            public String metadataType;   // 'ApexClass' | 'ApexTrigger'
#            public Id recordId;
#            public String name;
#            public List<Integer> lineNumbers = new List<Integer>();
#        }
#
#        public List<Reference> findReferences(
#                String identifier, List<String> metadataTypes) {
#            Pattern p = Pattern.compile('\\b' + Pattern.quote(identifier) + '\\b');
#            List<Reference> refs = new List<Reference>();
#            for (Metadata_Cache__c row : [
#                SELECT Record_Id__c, Display_Name__c, Metadata_Type__c, Payload__c
#                FROM Metadata_Cache__c
#                WHERE Metadata_Type__c IN :metadataTypes
#            ]) {
#                // ... split Payload__c body on '\n', test each line ...
#            }
#            return refs;
#        }
#    }
#
# Concept mapping:
# - metadata_types tuple + for-loop      → SOQL WHERE Metadata_Type__c IN :list
# - tuple default (immutable)            → no parallel; Apex has no default args
# - Reference.metadata_type tag          → Metadata_Type__c column on the row
# - sort(key=lambda, reverse=True)       → List.sort() w/ Comparable wrapper
# ============================================================