"""Hermetic tests for the read-only /api/v1/graph route (Week 12).

Builds a real (tiny) MetadataGraph in-process so stats() serialization is
exercised for real — no Claude, no network, no tokens/cache dependency.
"""
import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_graph_engine
from app.intelligence.graph.bootstrap import GraphLoadError
from app.intelligence.graph.models import MetadataGraph, Node, NodeType
from app.main import app


async def _boom(*args, **kwargs):
    raise GraphLoadError("test: forced unloaded")


@pytest.fixture(autouse=True)
def _mock_env(monkeypatch):
    monkeypatch.setenv("USE_MOCK_DATA", "true")
    monkeypatch.setattr("app.main.load_graph", _boom)


def test_graph_summary_503_when_absent():
    with TestClient(app) as client:
        resp = client.get("/api/v1/graph")
    assert resp.status_code == 503


def test_graph_summary_returns_counts():
    org = "https://org.example"
    g = MetadataGraph()
    g.add_node(Node(id="001", name="A", node_type=NodeType.APEX_CLASS, org_key=org))
    g.add_node(Node(id="002", name="B", node_type=NodeType.APEX_CLASS, org_key=org))
    g.add_node(Node(id="003", name="T", node_type=NodeType.APEX_TRIGGER, org_key=org))

    app.dependency_overrides[get_graph_engine] = lambda: ("engine", g, "cache", org)
    try:
        with TestClient(app) as client:
            resp = client.get("/api/v1/graph")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()
    assert data["org_key"] == org
    assert data["node_count"] == 3
    assert data["edge_count"] == 0
    assert data["node_type_counts"]["ApexClass"] == 2
    assert data["node_type_counts"]["ApexTrigger"] == 1
