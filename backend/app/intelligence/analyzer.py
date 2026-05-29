# ============================================================
# PYTHON CODE
# ============================================================
"""Reference analyzer — insight A: "what references this identifier?"

Reads cached Apex bodies and finds classes referencing a given
identifier (an sObject or field name). This is the first piece of the
platform that produces an *answer*, not a report.

SCOPE (ADR-006): v1 is a word-boundary string scan, NOT an AST parse.
Known limitations, by design:
  - False positives: matches inside comments and string literals.
  - False negatives: misses dynamic refs (obj.get('Field'), dynamic SOQL).
The AST-based Apex parser (Week 7) eliminates both. v1 ships the useful
80% answer now.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.intelligence.graph.storage import MetadataCache


@dataclass
class Reference:
    """One class that references the searched identifier."""

    class_id: str
    class_name: str
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
    classes_scanned: int

    @property
    def referencing_class_count(self) -> int:
        return len(self.references)


def _find_lines(body: str, identifier: str) -> list[int]:
    """1-indexed line numbers where identifier appears on a word boundary.

    Word-boundary match so 'Account' doesn't match 'AccountTeamMember'
    and 'Industry' doesn't match 'IndustryCode__c'. re.escape guards
    against identifiers containing regex metacharacters (e.g. '__c' is
    fine, but defensive anyway).
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
    ) -> ReferenceReport:
        """Find all cached Apex classes referencing `identifier`."""
        classes = await self._cache.get(org_key=org_key, metadata_type="ApexClass")

        references: list[Reference] = []
        for cls in classes:
            body = cls.get("Body") or ""
            lines = _find_lines(body, identifier)
            if lines:
                references.append(
                    Reference(
                        class_id=cls["Id"],
                        class_name=cls.get("Name", "<unknown>"),
                        line_numbers=lines,
                    )
                )

        # Most-referenced first — the classes most affected by a change
        # to `identifier` surface at the top. That ordering IS the insight.
        references.sort(key=lambda r: r.match_count, reverse=True)

        return ReferenceReport(
            identifier=identifier,
            org_key=org_key,
            references=references,
            classes_scanned=len(classes),
        )


# ============================================================
# APEX EQUIVALENT (for comparison)
# ============================================================
# In Apex you'd rarely scan source like this, but the parallel is
# iterating cached ApexClass bodies and pattern-matching:
#
#    public class ReferenceAnalyzer {
#        public class Reference {
#            public Id classId;
#            public String className;
#            public List<Integer> lineNumbers = new List<Integer>();
#        }
#
#        public List<Reference> findReferences(String identifier) {
#            // \b word boundary via Pattern; Apex regex is java.util.regex
#            Pattern p = Pattern.compile('\\b' + Pattern.quote(identifier) + '\\b');
#            List<Reference> refs = new List<Reference>();
#            for (Metadata_Cache__c row : [
#                SELECT Record_Id__c, Display_Name__c, Payload__c
#                FROM Metadata_Cache__c WHERE Metadata_Type__c = 'ApexClass'
#            ]) {
#                // ... split Payload__c body on '\n', test each line ...
#            }
#            return refs;
#        }
#    }
#
# Concept mapping:
# - @dataclass                      → Apex inner class (public fields, no boilerplate)
# - re.compile(r"\b..\b")           → Pattern.compile('\\b..\\b')
# - re.escape(identifier)           → Pattern.quote(identifier)
# - list comprehension + enumerate  → for loop with manual index
# - sort(key=lambda, reverse=True)  → List.sort() w/ Comparable wrapper class
# ============================================================