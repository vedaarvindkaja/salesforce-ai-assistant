"""Hermetic tests for the shared graph loader (ADR-015).

No network, no Claude API, no real org — just SQLite + the in-memory graph.
Covers the three GraphLoadError preconditions and one happy-path build, so the
loader's contract is pinned before REST (and later MCP/CLI) depend on it.

load_graph() calls load_tokens() as imported into the bootstrap module's
namespace, so we monkeypatch `bootstrap.load_tokens` (not the original module).
"""
from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from app.intelligence.graph import bootstrap
from app.intelligence.graph.bootstrap import GraphLoadError, load_graph
from app.intelligence.graph.query import QueryEngine
from app.intelligence.graph.storage import MetadataCache

ORG = "https://example-dev-ed.develop.my.salesforce.com"


def _fake_tokens(instance_url: str = ORG):
    # load_graph only ever reads `tokens.instance_url`.
    return SimpleNamespace(instance_url=instance_url)


class _Rec(BaseModel):
    Id: str
    Name: str
    Body: str | None = None


@pytest.mark.asyncio
async def test_missing_tokens_raises(monkeypatch, tmp_path):
    monkeypatch.setattr(bootstrap, "load_tokens", lambda: None)
    with pytest.raises(GraphLoadError, match="No OAuth tokens"):
        await load_graph(cache_path=tmp_path / "nope.db")


@pytest.mark.asyncio
async def test_missing_cache_raises(monkeypatch, tmp_path):
    monkeypatch.setattr(bootstrap, "load_tokens", lambda: _fake_tokens())
    with pytest.raises(GraphLoadError, match="Cache not found"):
        await load_graph(cache_path=tmp_path / "absent.db")


@pytest.mark.asyncio
async def test_empty_cache_raises(monkeypatch, tmp_path):
    monkeypatch.setattr(bootstrap, "load_tokens", lambda: _fake_tokens())
    db = tmp_path / "empty.db"
    cache = MetadataCache(db)
    await cache.init_schema()  # schema present, zero records → empty graph
    with pytest.raises(GraphLoadError, match="empty"):
        await load_graph(cache_path=db)


@pytest.mark.asyncio
async def test_happy_path_returns_bundle(monkeypatch, tmp_path):
    monkeypatch.setattr(bootstrap, "load_tokens", lambda: _fake_tokens())
    db = tmp_path / "seeded.db"
    cache = MetadataCache(db)
    await cache.init_schema()
    # One Apex record so GraphBuilder yields >=1 node (mirrors test_tool_definitions).
    await cache.put(
        org_key=ORG,
        metadata_type="ApexClass",
        records=[
            _Rec(
                Id="01p000000000001",
                Name="Helper",
                Body="public class Helper { public static void run() {} }",
            )
        ],
    )

    engine, graph, returned_cache, org_key = await load_graph(cache_path=db)

    assert isinstance(engine, QueryEngine)
    assert org_key == ORG
    assert graph.stats().node_count >= 1
    assert returned_cache is not None


@pytest.mark.asyncio
async def test_env_override_is_respected(monkeypatch, tmp_path):
    # SF_CACHE_PATH should win over the file-relative default. Point it at an
    # absent file and confirm the "Cache not found" path fires for that path.
    monkeypatch.setattr(bootstrap, "load_tokens", lambda: _fake_tokens())
    missing = tmp_path / "via_env.db"
    monkeypatch.setenv("SF_CACHE_PATH", str(missing))
    with pytest.raises(GraphLoadError, match="Cache not found"):
        await load_graph()  # no explicit cache_path → resolves via env
