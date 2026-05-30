"""Tests for Apex metadata classifiers (Week 7, Day 1)."""
import pytest
from app.intelligence.graph.classifier import is_test_class


# ------------------------------------------------------------------
# Helpers — build minimal records matching MetadataCache shape
# ------------------------------------------------------------------

def _record(name: str, body: str = "") -> dict:
    return {"Name": name, "Body": body}


# ------------------------------------------------------------------
# Signal 1: name-based detection
# ------------------------------------------------------------------

def test_name_ends_in_test():
    assert is_test_class(_record("AccountServiceTest")) is True


def test_name_ends_in_tests():
    assert is_test_class(_record("AccountServiceTests")) is True


def test_name_case_insensitive_upper():
    assert is_test_class(_record("AccountServiceTEST")) is True


def test_name_ends_in_test_not_mid_word():
    # 'Contest' ends the name but 'test' is mid-word — should NOT match
    assert is_test_class(_record("ContestHelper")) is False


def test_name_no_test_suffix():
    assert is_test_class(_record("AccountService")) is False


def test_name_test_substring_not_suffix():
    # 'TestUtils' starts with Test but doesn't end with it
    assert is_test_class(_record("TestUtils")) is False


# ------------------------------------------------------------------
# Signal 2: @isTest annotation in body
# ------------------------------------------------------------------

def test_body_has_istest_annotation():
    body = "@isTest\npublic class MyHelper { }"
    assert is_test_class(_record("MyHelper", body)) is True


def test_body_istest_case_insensitive():
    body = "@IsTest\npublic class MyHelper { }"
    assert is_test_class(_record("MyHelper", body)) is True


def test_body_istest_with_parentheses():
    # @isTest(SeeAllData=true) is valid Apex — \b still matches
    body = "@isTest(SeeAllData=true)\npublic class MyHelper { }"
    assert is_test_class(_record("MyHelper", body)) is True


def test_body_no_annotation():
    body = "public class AccountService { }"
    assert is_test_class(_record("AccountService", body)) is False


# ------------------------------------------------------------------
# OR logic — either signal is sufficient
# ------------------------------------------------------------------

def test_both_signals_present():
    body = "@isTest\npublic class MyHelperTest { }"
    assert is_test_class(_record("MyHelperTest", body)) is True


def test_name_signal_only_no_body():
    # Body is empty — name alone must trigger
    assert is_test_class(_record("AccountServiceTest", "")) is True


def test_annotation_signal_only_plain_name():
    # Name has no Test suffix — annotation alone must trigger
    body = "@isTest\npublic class AccountServiceHelper { }"
    assert is_test_class(_record("AccountServiceHelper", body)) is True


# ------------------------------------------------------------------
# Edge cases — missing / None fields
# ------------------------------------------------------------------

def test_empty_record():
    assert is_test_class({}) is False


def test_none_name_field():
    assert is_test_class({"Name": None, "Body": ""}) is False


def test_none_body_field():
    # Name matches — None body shouldn't crash
    assert is_test_class({"Name": "MyClassTest", "Body": None}) is True


def test_developername_field_fallback():
    # Some cache records use DeveloperName not Name (e.g. CustomObject)
    assert is_test_class({"DeveloperName": "MyClassTest", "Body": ""}) is True