"""Hermetic tests for the REST capability routes (ADR-016).

No live Claude API and no dependence on this machine's tokens/cache:
  - app.main.load_graph is patched so the lifespan lands graph_bundle in a known
    state (and stays offline).
  - build_capability_client is patched so the agentic loop is a canned async
    generator instead of a real (paid, non-deterministic) Claude call.
  - get_graph_engine is overridden via FastAPI dependency_overrides to inject a
    dummy bundle when we want to bypass the 503 gate.

Parametrized across all four routes so every capability proves the same
contract: 503 when the graph is absent, and a clean SSE stream (with the correct
mode routed into build_capability_client) when it's present.
"""
import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_graph_engine
from app.intelligence.graph.bootstrap import GraphLoadError
from app.main import app

# (route path, capability mode the route must request)
ROUTES = [
    ("/api/v1/metadata-qa", "qa"),
    ("/api/v1/apex-explain", "apex"),
    ("/api/v1/soql-generate", "soql"),
    ("/api/v1/deployment-impact", "impact"),
]

_FAKE_BUNDLE = ("engine", "graph", "cache", "https://org.example")


async def _boom(*args, **kwargs):
    # Force the eager graph load to fail so graph_bundle is None regardless of
    # whatever tokens/cache happen to exist on the host running the tests.
    raise GraphLoadError("test: forced unloaded")


@pytest.fixture(autouse=True)
def _mock_env(monkeypatch):
    # Keep the lifespan's Salesforce client on the mock path.
    monkeypatch.setenv("USE_MOCK_DATA", "true")
    # Keep the eager graph load offline + deterministic for every test.
    monkeypatch.setattr("app.main.load_graph", _boom)


@pytest.mark.parametrize("path", [p for p, _ in ROUTES])
def test_capability_503_when_graph_absent(path):
    with TestClient(app) as client:
        resp = client.post(path, json={"question": "hi"})
    assert resp.status_code == 503
    assert "metadata graph not loaded" in resp.json()["detail"]


@pytest.mark.parametrize("path,mode", ROUTES)
def test_capability_streams_chunks(monkeypatch, path, mode):
    app.dependency_overrides[get_graph_engine] = lambda: _FAKE_BUNDLE
    captured = {}

    class _FakeClient:
        async def ask(self, question, tools=None):
            yield "Hello "
            yield "world."

    def _fake_build(m, engine, graph, cache, org_key, *, handler_wrapper=None):
        captured["mode"] = m
        return _FakeClient(), []

    monkeypatch.setattr(
        "app.interfaces.rest_api.routes.capabilities.build_capability_client",
        _fake_build,
    )

    try:
        with TestClient(app) as client:
            resp = client.post(path, json={"question": "hi"})
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert captured["mode"] == mode  # route routed the correct capability mode
    assert "Hello " in resp.text
    assert "world." in resp.text
    assert "done" in resp.text  # terminal 'done' event present


def test_metadata_qa_rejects_empty_question():
    # Inject a bundle so the ONLY possible failure is body validation (422),
    # not the 503 gate.
    app.dependency_overrides[get_graph_engine] = lambda: _FAKE_BUNDLE
    try:
        with TestClient(app) as client:
            resp = client.post("/api/v1/metadata-qa", json={"question": ""})
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 422  # Pydantic min_length=1
