# No direct Apex equivalent — pytest test module (cf. Apex @isTest classes)
"""Hermetic tests for ReferenceAnalyzer. Synthetic bodies, throwaway DB."""
import pytest
from pydantic import BaseModel

from app.intelligence.graph.storage import MetadataCache
from app.intelligence.analyzer import ReferenceAnalyzer


class _FakeRec(BaseModel):
    Id: str
    Name: str
    Body: str | None = None


async def _cache(tmp_path):
    c = MetadataCache(tmp_path / "a.db")
    await c.init_schema()
    return c


@pytest.mark.asyncio
async def test_finds_referencing_class(tmp_path):
    c = await _cache(tmp_path)
    await c.put(org_key="org1", metadata_type="ApexClass", records=[
        _FakeRec(Id="01p1", Name="AccountService",
                 Body="public class AccountService {\n  Account a = new Account();\n}"),
        _FakeRec(Id="01p2", Name="ContactService", Body="Contact c;"),
    ])
    report = await ReferenceAnalyzer(c).find_references(org_key="org1", identifier="Account")
    assert report.referencing_count == 1
    assert report.references[0].name == "AccountService"
    assert report.references[0].metadata_type == "ApexClass"
    assert report.references[0].line_numbers == [2]


@pytest.mark.asyncio
async def test_finds_referencing_trigger(tmp_path):
    c = await _cache(tmp_path)
    await c.put(org_key="org1", metadata_type="ApexTrigger", records=[
        _FakeRec(Id="01q1", Name="AccountTrigger",
                 Body="trigger AccountTrigger on Account (before insert) {}"),
    ])
    report = await ReferenceAnalyzer(c).find_references(org_key="org1", identifier="Account")
    assert report.referencing_count == 1
    assert report.references[0].metadata_type == "ApexTrigger"
    assert report.references[0].name == "AccountTrigger"


@pytest.mark.asyncio
async def test_scans_both_types(tmp_path):
    c = await _cache(tmp_path)
    await c.put(org_key="org1", metadata_type="ApexClass",
                records=[_FakeRec(Id="01p1", Name="AccSvc", Body="Account a;")])
    await c.put(org_key="org1", metadata_type="ApexTrigger",
                records=[_FakeRec(Id="01q1", Name="AccTrig",
                                  Body="trigger AccTrig on Account (before insert) {}")])
    report = await ReferenceAnalyzer(c).find_references(org_key="org1", identifier="Account")
    assert report.referencing_count == 2
    assert {r.metadata_type for r in report.references} == {"ApexClass", "ApexTrigger"}
    assert report.records_scanned == 2


@pytest.mark.asyncio
async def test_metadata_types_param_limits_scan(tmp_path):
    c = await _cache(tmp_path)
    await c.put(org_key="org1", metadata_type="ApexClass",
                records=[_FakeRec(Id="01p1", Name="AccSvc", Body="Account a;")])
    await c.put(org_key="org1", metadata_type="ApexTrigger",
                records=[_FakeRec(Id="01q1", Name="AccTrig", Body="Account x;")])
    # Restrict to classes only — trigger must be ignored.
    report = await ReferenceAnalyzer(c).find_references(
        org_key="org1", identifier="Account", metadata_types=("ApexClass",))
    assert report.referencing_count == 1
    assert report.references[0].metadata_type == "ApexClass"
    assert report.records_scanned == 1


@pytest.mark.asyncio
async def test_word_boundary_no_false_substring(tmp_path):
    c = await _cache(tmp_path)
    await c.put(org_key="org1", metadata_type="ApexClass", records=[
        _FakeRec(Id="01p1", Name="TeamSvc",
                 Body="AccountTeamMember atm = new AccountTeamMember();")])
    report = await ReferenceAnalyzer(c).find_references(org_key="org1", identifier="Account")
    assert report.referencing_count == 0


@pytest.mark.asyncio
async def test_sorted_by_match_count_desc(tmp_path):
    c = await _cache(tmp_path)
    await c.put(org_key="org1", metadata_type="ApexClass", records=[
        _FakeRec(Id="01p1", Name="Few", Body="Account a;"),
        _FakeRec(Id="01p2", Name="Many", Body="Account a;\nAccount b;\nAccount c;")])
    report = await ReferenceAnalyzer(c).find_references(org_key="org1", identifier="Account")
    assert [r.name for r in report.references] == ["Many", "Few"]
    assert report.references[0].match_count == 3


@pytest.mark.asyncio
async def test_handles_null_body(tmp_path):
    c = await _cache(tmp_path)
    await c.put(org_key="org1", metadata_type="ApexClass",
                records=[_FakeRec(Id="01p1", Name="NoBody", Body=None)])
    report = await ReferenceAnalyzer(c).find_references(org_key="org1", identifier="Account")
    assert report.referencing_count == 0
    assert report.records_scanned == 1


@pytest.mark.asyncio
async def test_no_matches_returns_empty(tmp_path):
    c = await _cache(tmp_path)
    await c.put(org_key="org1", metadata_type="ApexClass",
                records=[_FakeRec(Id="01p1", Name="Svc", Body="Contact c;")])
    report = await ReferenceAnalyzer(c).find_references(org_key="org1", identifier="Opportunity")
    assert report.references == []
    assert report.referencing_count == 0