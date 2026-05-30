# ============================================================
# PYTHON CODE
# ============================================================
"""Apex metadata classifiers — derive semantic attributes from raw metadata.

A classifier takes a raw cache record (dict) and returns a bool or a
category string. Results are stored as node attributes at build time so
every downstream query can filter without re-reading bodies.

Week 7: test-class classifier only.
Future: handler classifier, utility classifier, framework-base classifier.

Kept as module-level functions (not a class) because classifiers are
stateless transforms: input → bool. A class would add indirection with
no benefit here.
"""
from __future__ import annotations

import re

# Matches class names ending in 'Test' or 'Tests' (case-insensitive).
# \b is a word boundary — prevents 'ContestHelper' from matching.
_TEST_NAME_PATTERN = re.compile(r"Tests?\b\s*$", re.IGNORECASE)

# Matches the @isTest annotation anywhere in the body.
# Apex allows @isTest and @IsTest — the IGNORECASE flag covers both.
_IS_TEST_ANNOTATION = re.compile(r"@isTest\b", re.IGNORECASE)


def is_test_class(record: dict) -> bool:
    """Return True if this cache record is an Apex test class.

    Two signals, OR'd — either is sufficient:
      1. Name ends in 'Test' or 'Tests' (catches 99% of org conventions).
      2. Body contains @isTest annotation (authoritative Salesforce signal).

    Args:
        record: A raw cache record dict with at least 'Name' and optionally
                'Body' keys (the shape returned by MetadataCache.get()).

    Returns:
        True if the record is a test class by either signal.
    """
    name: str = record.get("Name") or record.get("DeveloperName") or ""
    body: str = record.get("Body") or ""

    if _TEST_NAME_PATTERN.search(name):
        return True
    if _IS_TEST_ANNOTATION.search(body):
        return True
    return False


# ============================================================
# APEX EQUIVALENT (for comparison)
# ============================================================
#
# In Apex, you'd write this as a utility method on a helper class,
# called before inserting a Metadata_Cache__c record or as part of
# a classification batch.
#
#    public class ApexClassifier {
#
#        // Signal 1: name ends in 'Test' or 'Tests'
#        private static final Pattern TEST_NAME =
#            Pattern.compile('Tests?$', Pattern.CASE_INSENSITIVE);
#
#        // Signal 2: body contains @isTest annotation
#        private static final Pattern IS_TEST_BODY =
#            Pattern.compile('@isTest\\b', Pattern.CASE_INSENSITIVE);
#
#        public static Boolean isTestClass(String name, String body) {
#            if (name == null) name = '';
#            if (body == null) body = '';
#            if (TEST_NAME.matcher(name).find())  return true;
#            if (IS_TEST_BODY.matcher(body).find()) return true;
#            return false;
#        }
#    }
#
# Concept mapping:
# - re.compile(pattern, re.IGNORECASE)  → Pattern.compile(pattern, Pattern.CASE_INSENSITIVE)
# - pattern.search(string)              → pattern.matcher(string).find()
# - record.get("Name") or ""           → name != null ? name : ''
# - Module-level functions              → static methods on a utility class
#   (Python has no class requirement for stateless logic; Apex always needs a class)
# ============================================================