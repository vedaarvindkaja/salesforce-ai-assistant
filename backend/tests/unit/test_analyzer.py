# No direct Apex equivalent — pytest test module (cf. Apex @isTest classes)
"""Hermetic tests for ReferenceAnalyzer. Synthetic Apex bodies, throwaway
DB via tmp_path — no real org."""
import pytest
from pydantic import BaseModel

from app.intelligence.graph.storage import MetadataCache
from app.intelligence.analyzer import ReferenceAnalyzer


class _FakeApex(BaseModel):
    Id: str
    Name: str
    Body: str | None = None


async def _seed(tmp_path, classes):
    cache = MetadataCache(tmp_path / "a.db")
    await cache.init_schema()
    await cache.put(org_key="org1", metadata_type="ApexClass", records=classes)
    return ReferenceAnalyzer(cache)


@pytest.mark.asyncio
async def test_finds_referencing_class(tmp_path):
    analyzer = await _seed(tmp_path, [
        _FakeApex(Id="01p1", Name="AccountService",
                  Body="public class AccountService {\n  Account a = new Account();\n}"),
        _FakeApex(Id="01p2", Name="ContactService",
                  Body="public class ContactService {\n  Contact c;\n}"),
    ])
    report = analyzer_result = await analyzer.find_references(org_key="org1", identifier="Account")
    assert report.referencing_class_count == 1
    assert report.references[0].class_name == "AccountService"
    assert report.references[0].line_numbers == [2]
    assert report.classes_scanned == 2


@pytest.mark.asyncio
async def test_word_boundary_no_false_substring(tmp_path):
    # 'Account' must NOT match inside 'AccountTeamMember'
    analyzer = await _seed(tmp_path, [
        _FakeApex(Id="01p1", Name="TeamSvc",
                  Body="AccountTeamMember atm = new AccountTeamMember();"),
    ])
    report = await analyzer.find_references(org_key="org1", identifier="Account")
    assert report.referencing_class_count == 0


@pytest.mark.asyncio
async def test_sorted_by_match_count_desc(tmp_path):
    analyzer = await _seed(tmp_path, [
        _FakeApex(Id="01p1", Name="Few", Body="Account a;"),
        _FakeApex(Id="01p2", Name="Many",
                  Body="Account a;\nAccount b;\nAccount c;"),
    ])
    report = await analyzer.find_references(org_key="org1", identifier="Account")
    assert [r.class_name for r in report.references] == ["Many", "Few"]
    assert report.references[0].match_count == 3


@pytest.mark.asyncio
async def test_handles_null_body(tmp_path):
    analyzer = await _seed(tmp_path, [
        _FakeApex(Id="01p1", Name="NoBody", Body=None),
    ])
    report = await analyzer.find_references(org_key="org1", identifier="Account")
    assert report.referencing_class_count == 0
    assert report.classes_scanned == 1


@pytest.mark.asyncio
async def test_no_matches_returns_empty(tmp_path):
    analyzer = await _seed(tmp_path, [
        _FakeApex(Id="01p1", Name="Svc", Body="Contact c;"),
    ])
    report = await analyzer.find_references(org_key="org1", identifier="Opportunity")
    assert report.references == []
    assert report.referencing_class_count == 0