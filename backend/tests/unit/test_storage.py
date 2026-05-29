# No direct Apex equivalent — pytest test module (cf. Apex @isTest classes)
"""Hermetic tests for MetadataCache. Uses pytest's tmp_path so each test
gets a throwaway DB file — no real org, no shared state."""
import pytest
from pydantic import BaseModel

from app.intelligence.graph.storage import MetadataCache


class _FakeRecord(BaseModel):
    Id: str
    DeveloperName: str
    Body: str | None = None


async def _make_cache(tmp_path):
    cache = MetadataCache(tmp_path / "test_cache.db")
    await cache.init_schema()
    return cache


@pytest.mark.asyncio
async def test_put_and_get_roundtrip(tmp_path):
    cache = await _make_cache(tmp_path)
    written = await cache.put(
        org_key="org1",
        metadata_type="ApexClass",
        records=[
            _FakeRecord(Id="01p001", DeveloperName="Alpha"),
            _FakeRecord(Id="01p002", DeveloperName="Beta"),
        ],
    )
    assert written == 2
    rows = await cache.get(org_key="org1", metadata_type="ApexClass")
    assert {r["DeveloperName"] for r in rows} == {"Alpha", "Beta"}


@pytest.mark.asyncio
async def test_get_by_display_name(tmp_path):
    cache = await _make_cache(tmp_path)
    await cache.put(org_key="org1", metadata_type="ApexClass",
                    records=[_FakeRecord(Id="01p001", DeveloperName="Alpha")])
    rows = await cache.get(org_key="org1", metadata_type="ApexClass", display_name="Alpha")
    assert len(rows) == 1 and rows[0]["Id"] == "01p001"


@pytest.mark.asyncio
async def test_upsert_overwrites_in_place(tmp_path):
    cache = await _make_cache(tmp_path)
    await cache.put(org_key="org1", metadata_type="ApexClass",
                    records=[_FakeRecord(Id="01p001", DeveloperName="Old")])
    await cache.put(org_key="org1", metadata_type="ApexClass",
                    records=[_FakeRecord(Id="01p001", DeveloperName="New")])
    rows = await cache.get(org_key="org1", metadata_type="ApexClass")
    assert len(rows) == 1 and rows[0]["DeveloperName"] == "New"


@pytest.mark.asyncio
async def test_get_one_hit_and_miss(tmp_path):
    cache = await _make_cache(tmp_path)
    await cache.put(org_key="org1", metadata_type="ApexClass",
                    records=[_FakeRecord(Id="01p001", DeveloperName="Alpha")])
    assert (await cache.get_one(org_key="org1", metadata_type="ApexClass", record_id="01p001"))["DeveloperName"] == "Alpha"
    assert await cache.get_one(org_key="org1", metadata_type="ApexClass", record_id="nope") is None


@pytest.mark.asyncio
async def test_clear_by_type(tmp_path):
    cache = await _make_cache(tmp_path)
    await cache.put(org_key="org1", metadata_type="ApexClass",
                    records=[_FakeRecord(Id="01p001", DeveloperName="Alpha")])
    assert await cache.clear(org_key="org1", metadata_type="ApexClass") == 1
    assert await cache.get(org_key="org1", metadata_type="ApexClass") == []


@pytest.mark.asyncio
async def test_stats_counts_by_type(tmp_path):
    cache = await _make_cache(tmp_path)
    await cache.put(org_key="org1", metadata_type="ApexClass",
                    records=[_FakeRecord(Id="01p001", DeveloperName="A")])
    await cache.put(org_key="org1", metadata_type="FlowDefinition",
                    records=[_FakeRecord(Id="301001", DeveloperName="F")])
    assert await cache.stats(org_key="org1") == {"ApexClass": 1, "FlowDefinition": 1}