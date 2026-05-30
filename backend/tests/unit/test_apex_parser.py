"""Hermetic tests for the Apex pattern parser (Week 7, Day 2).

All tests use synthetic Apex bodies — no cache, no I/O, no network.
Each test targets one extraction category in isolation, then combined.
Fix 1: comment stripping tests
Fix 2: lowercase qualifier filter for class refs
Fix 3: DML 'new' keyword skip
"""
import pytest

from app.intelligence.code.apex_parser import (
    ClassReference,
    DmlReference,
    FieldReference,
    ParseResult,
    SoqlReference,
    _strip_comments,
    parse_apex_body,
)


# ------------------------------------------------------------------
# Empty / trivial bodies
# ------------------------------------------------------------------

def test_empty_body_returns_empty_result():
    result = parse_apex_body("")
    assert result == ParseResult()


def test_whitespace_body_returns_empty_result():
    result = parse_apex_body("   \n\t  ")
    assert result == ParseResult()


def test_class_declaration_only_no_refs():
    body = "public class MyService { }"
    result = parse_apex_body(body)
    assert result.soql_references == []
    assert result.dml_references == []
    assert result.field_references == []
    assert result.class_references == []


# ------------------------------------------------------------------
# Fix 1: comment stripping
# ------------------------------------------------------------------

def test_strip_line_comment():
    body = "// FROM Account\nString x = 'real';"
    stripped = _strip_comments(body)
    assert "FROM Account" not in stripped
    assert "real" in stripped


def test_strip_block_comment():
    body = "/* SELECT Id FROM Contact */ String x;"
    stripped = _strip_comments(body)
    assert "FROM Contact" not in stripped


def test_strip_multiline_block_comment():
    body = """
    /**
     * @see www.apache.org/licenses
     * FROM the base class
     */
    public void run() {}
    """
    stripped = _strip_comments(body)
    assert "www.apache" not in stripped
    assert "FROM" not in stripped


def test_comment_noise_not_in_soql_results():
    # 'the' and 'a' appear only in comments in real org — should not be SOQL hits
    body = """
    // inherited FROM the base class
    /* query FROM a record */
    List<Account> accs = [SELECT Id FROM Account];
    """
    result = parse_apex_body(body)
    obj_names = {r.object_name for r in result.soql_references}
    assert "Account" in obj_names
    assert "the" not in obj_names
    assert "a" not in obj_names


def test_pmd_annotation_not_in_field_refs():
    # PMD.ApexDoc appears in @SuppressWarnings annotations inside comments
    body = """
    // PMD.ApexDoc
    /* PMD.CognitiveComplexity */
    String name = acc.Name;
    """
    result = parse_apex_body(body)
    pmd_refs = [r for r in result.field_references if r.qualifier == "PMD"]
    assert pmd_refs == []
    assert FieldReference(qualifier="acc", field_name="Name") in result.field_references


def test_url_not_in_field_refs():
    body = """
    // @see www.apache.org/licenses
    String val = acc.Industry__c;
    """
    result = parse_apex_body(body)
    www_refs = [r for r in result.field_references if r.qualifier == "www"]
    assert www_refs == []


# ------------------------------------------------------------------
# Fix 2: lowercase qualifier filter (variable names vs class names)
# ------------------------------------------------------------------

def test_lowercase_qualifier_excluded_from_class_refs():
    # 'result.add()' — lowercase qualifier is a variable, not a class
    body = "result.add(item);"
    result = parse_apex_body(body)
    assert result.class_references == []


def test_this_excluded_from_class_refs():
    body = "this.run();"
    result = parse_apex_body(body)
    assert result.class_references == []


def test_pascalcase_qualifier_included_in_class_refs():
    body = "TriggerBase.run();"
    result = parse_apex_body(body)
    assert ClassReference(class_name="TriggerBase", method_name="run") in result.class_references


def test_mixed_case_qualifiers_filtered_correctly():
    body = """
    TriggerBase.run();
    handler.execute();
    MetadataTriggerHandler.bypass();
    myException.getMessage();
    """
    result = parse_apex_body(body)
    class_names = {r.class_name for r in result.class_references}
    assert "TriggerBase" in class_names
    assert "MetadataTriggerHandler" in class_names
    assert "handler" not in class_names
    assert "myException" not in class_names


# ------------------------------------------------------------------
# Fix 3: DML 'new' keyword skip
# ------------------------------------------------------------------

def test_dml_insert_new_captures_class_not_new():
    body = "insert new Account();"
    result = parse_apex_body(body)
    dml_objects = {r.object_name for r in result.dml_references}
    assert "Account" in dml_objects
    assert "new" not in dml_objects


def test_dml_insert_variable_still_captured():
    # 'insert records' (no 'new') — variable name captured as-is
    body = "insert records;"
    result = parse_apex_body(body)
    assert DmlReference(operation="insert", object_name="records") in result.dml_references


def test_dml_upsert_new_skips_new():
    body = "upsert new Contact();"
    result = parse_apex_body(body)
    dml_objects = {r.object_name for r in result.dml_references}
    assert "Contact" in dml_objects
    assert "new" not in dml_objects


# ------------------------------------------------------------------
# SOQL extraction
# ------------------------------------------------------------------

def test_soql_standard_object():
    body = "List<Account> accs = [SELECT Id, Name FROM Account];"
    result = parse_apex_body(body)
    assert SoqlReference(object_name="Account") in result.soql_references


def test_soql_custom_object():
    body = "List<Invoice__c> inv = [SELECT Id FROM Invoice__c WHERE Status__c = 'Open'];"
    result = parse_apex_body(body)
    assert SoqlReference(object_name="Invoice__c") in result.soql_references


def test_soql_multiline():
    body = """
    List<Contact> contacts = [
        SELECT Id, FirstName, LastName
        FROM Contact
        WHERE AccountId = :accId
    ];
    """
    result = parse_apex_body(body)
    assert SoqlReference(object_name="Contact") in result.soql_references


def test_soql_multiple_objects():
    body = """
    List<Account> accs = [SELECT Id FROM Account];
    List<Contact> cons = [SELECT Id FROM Contact];
    """
    result = parse_apex_body(body)
    obj_names = {r.object_name for r in result.soql_references}
    assert "Account" in obj_names
    assert "Contact" in obj_names


def test_soql_deduplicates():
    body = """
    [SELECT Id FROM Account WHERE Id = :id1];
    [SELECT Name FROM Account WHERE Id = :id2];
    """
    result = parse_apex_body(body)
    account_refs = [r for r in result.soql_references if r.object_name == "Account"]
    assert len(account_refs) == 1


def test_soql_case_insensitive_from():
    body = "List<Account> a = [SELECT Id from Account];"
    result = parse_apex_body(body)
    assert SoqlReference(object_name="Account") in result.soql_references


# ------------------------------------------------------------------
# DML extraction
# ------------------------------------------------------------------

def test_dml_insert():
    body = "insert newAccount;"
    result = parse_apex_body(body)
    assert DmlReference(operation="insert", object_name="newAccount") in result.dml_references


def test_dml_update():
    body = "update existingContact;"
    result = parse_apex_body(body)
    assert DmlReference(operation="update", object_name="existingContact") in result.dml_references


def test_dml_delete():
    body = "delete oldRecord;"
    result = parse_apex_body(body)
    assert DmlReference(operation="delete", object_name="oldRecord") in result.dml_references


def test_dml_upsert():
    body = "upsert accountList;"
    result = parse_apex_body(body)
    assert DmlReference(operation="upsert", object_name="accountList") in result.dml_references


def test_dml_multiple_operations():
    body = """
    insert newAccount;
    update existingContact;
    delete oldRecord;
    """
    result = parse_apex_body(body)
    ops = {(r.operation, r.object_name) for r in result.dml_references}
    assert ("insert", "newAccount") in ops
    assert ("update", "existingContact") in ops
    assert ("delete", "oldRecord") in ops


def test_dml_case_insensitive_keyword():
    body = "INSERT newAccount;"
    result = parse_apex_body(body)
    assert DmlReference(operation="insert", object_name="newAccount") in result.dml_references


def test_dml_deduplicates():
    body = """
    insert rec;
    insert rec;
    """
    result = parse_apex_body(body)
    insert_refs = [r for r in result.dml_references if r.operation == "insert"]
    assert len(insert_refs) == 1


# ------------------------------------------------------------------
# Field reference extraction
# ------------------------------------------------------------------

def test_field_ref_custom_field():
    body = "String val = acc.Industry__c;"
    result = parse_apex_body(body)
    assert FieldReference(qualifier="acc", field_name="Industry__c") in result.field_references


def test_field_ref_standard_field():
    body = "String name = acc.Name;"
    result = parse_apex_body(body)
    assert FieldReference(qualifier="acc", field_name="Name") in result.field_references


def test_field_ref_multiple():
    body = """
    String name = acc.Name;
    String industry = acc.Industry;
    """
    result = parse_apex_body(body)
    fields = {r.field_name for r in result.field_references}
    assert "Name" in fields
    assert "Industry" in fields


def test_field_ref_deduplicates():
    body = """
    String a = acc.Name;
    String b = acc.Name;
    """
    result = parse_apex_body(body)
    name_refs = [r for r in result.field_references
                 if r.qualifier == "acc" and r.field_name == "Name"]
    assert len(name_refs) == 1


def test_system_namespace_excluded_from_field_refs():
    body = "system.debug('hello');"
    result = parse_apex_body(body)
    sys_refs = [r for r in result.field_references if r.qualifier.lower() == "system"]
    assert sys_refs == []


# ------------------------------------------------------------------
# Class reference extraction
# ------------------------------------------------------------------

def test_class_ref_static_call():
    body = "TriggerBase.run();"
    result = parse_apex_body(body)
    assert ClassReference(class_name="TriggerBase", method_name="run") in result.class_references


def test_class_ref_multiple():
    body = """
    TriggerBase.run();
    FormulaFilter.evaluate(records);
    """
    result = parse_apex_body(body)
    class_names = {r.class_name for r in result.class_references}
    assert "TriggerBase" in class_names
    assert "FormulaFilter" in class_names


def test_class_ref_deduplicates():
    body = """
    TriggerBase.run();
    TriggerBase.run();
    """
    result = parse_apex_body(body)
    tbase_refs = [r for r in result.class_references if r.class_name == "TriggerBase"]
    assert len(tbase_refs) == 1


def test_class_ref_system_namespace_excluded():
    body = "System.debug('test');"
    result = parse_apex_body(body)
    sys_refs = [r for r in result.class_references if r.class_name.lower() == "system"]
    assert sys_refs == []


def test_method_call_not_in_field_refs():
    body = "TriggerBase.run();"
    result = parse_apex_body(body)
    tbase_field_refs = [r for r in result.field_references if r.qualifier == "TriggerBase"]
    assert tbase_field_refs == []


# ------------------------------------------------------------------
# referenced_objects and referenced_classes convenience properties
# ------------------------------------------------------------------

def test_referenced_objects_combines_soql_and_dml():
    body = """
    List<Account> accs = [SELECT Id FROM Account];
    insert newContact;
    """
    result = parse_apex_body(body)
    assert "Account" in result.referenced_objects
    assert "newContact" in result.referenced_objects


def test_referenced_classes_from_method_calls():
    body = "TriggerBase.run();"
    result = parse_apex_body(body)
    assert "TriggerBase" in result.referenced_classes


# ------------------------------------------------------------------
# Combined realistic Apex body
# ------------------------------------------------------------------

def test_realistic_trigger_handler_body():
    body = """
    /**
     * Handles Account trigger logic.
     * @see www.apache.org/licenses
     * Inherited FROM the base TriggerBase class.
     */
    public class AccountTriggerHandler {
        // PMD.CognitiveComplexity
        public void beforeInsert(List<Account> newRecords) {
            for (Account acc : newRecords) {
                acc.Industry = 'Technology';
                acc.Rating = FormulaFilter.evaluate(acc);
            }
            List<Contact> contacts = [SELECT Id FROM Contact WHERE AccountId IN :ids];
            insert new Task();
            TriggerBase.run();
        }
    }
    """
    result = parse_apex_body(body)

    # SOQL — Contact yes, comment noise gone
    soql_objs = {r.object_name for r in result.soql_references}
    assert "Contact" in soql_objs
    assert "the" not in soql_objs

    # DML — Task captured, not 'new'
    dml_objects = {r.object_name for r in result.dml_references}
    assert "Task" in dml_objects
    assert "new" not in dml_objects

    # Field refs — acc.Industry yes, PMD/www gone
    field_qualifiers = {r.qualifier for r in result.field_references}
    assert "acc" in field_qualifiers
    pmd_refs = [r for r in result.field_references if r.qualifier == "PMD"]
    assert pmd_refs == []

    # Class refs — PascalCase only
    class_names = {r.class_name for r in result.class_references}
    assert "FormulaFilter" in class_names
    assert "TriggerBase" in class_names
