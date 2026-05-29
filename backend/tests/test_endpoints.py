"""Integration tests for all FastAPI endpoints.

Uses TestClient to call endpoints without running a real server.
Each test verifies a specific behavior — together they cover the full API surface.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app


# ============================================================
# Fixture: test client that runs lifespan (startup/shutdown)
# ============================================================

@pytest.fixture
def client(monkeypatch):
    """Create a TestClient that properly runs FastAPI's lifespan.
    
    Forces USE_MOCK_DATA=true so the test suite is deterministic regardless
    of what's in .env. Tests assert against the mock client's fixed responses
    (Edge Communications, Burlington Textiles, GenePoint).
    
    Using `with TestClient(app)` ensures the lifespan startup runs
    (which initializes the shared Salesforce client) and shutdown
    runs (which cleans it up).
    """
    monkeypatch.setenv("USE_MOCK_DATA", "true")
    with TestClient(app) as test_client:
        yield test_client


# ============================================================
# Health endpoint
# ============================================================

def test_health(client):
    """GET /health returns 200 OK with status message."""
    response = client.get("/health")
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "alive" in data["message"]


# ============================================================
# List accounts endpoint
# ============================================================

def test_list_accounts_default(client):
    """GET /accounts/ returns the list of accounts."""
    response = client.get("/accounts/")
    
    assert response.status_code == 200
    accounts = response.json()
    assert isinstance(accounts, list)
    assert len(accounts) == 3
    
    # Verify first account has expected structure
    first = accounts[0]
    assert first["Name"] == "Edge Communications"
    assert first["Industry"] == "Electronics"


def test_list_accounts_with_limit(client):
    """GET /accounts/?limit=5 accepts the limit query parameter."""
    response = client.get("/accounts/?limit=5")
    
    assert response.status_code == 200
    assert len(response.json()) == 3   # mock returns 3 regardless


def test_list_accounts_limit_too_low(client):
    """GET /accounts/?limit=0 returns 422 validation error."""
    response = client.get("/accounts/?limit=0")
    
    assert response.status_code == 422
    error = response.json()
    assert "detail" in error


def test_list_accounts_limit_too_high(client):
    """GET /accounts/?limit=999 returns 422 validation error."""
    response = client.get("/accounts/?limit=999")
    
    assert response.status_code == 422


# ============================================================
# Get account by ID endpoint
# ============================================================

def test_get_account_by_id(client):
    """GET /accounts/{id} returns the matching account."""
    response = client.get("/accounts/0015g00000Abc1AAB")
    
    assert response.status_code == 200
    account = response.json()
    assert account["Id"] == "0015g00000Abc1AAB"
    assert account["Name"] == "Edge Communications"


def test_get_account_not_found(client):
    """GET /accounts/{bad_id} returns 404."""
    response = client.get("/accounts/INVALID_ID")
    
    assert response.status_code == 404
    error = response.json()
    assert "not found" in error["detail"].lower()


# ============================================================
# Search accounts endpoint
# ============================================================

def test_search_no_filters(client):
    """GET /accounts/search/ with no filters returns all accounts."""
    response = client.get("/accounts/search/")
    
    assert response.status_code == 200
    assert len(response.json()) == 3


def test_search_by_industry(client):
    """GET /accounts/search/?industry=X filters by industry."""
    response = client.get("/accounts/search/?industry=Electronics")
    
    assert response.status_code == 200
    results = response.json()
    assert len(results) == 1
    assert results[0]["Industry"] == "Electronics"


def test_search_industry_no_match(client):
    """Search for industry with no matches returns empty list."""
    response = client.get("/accounts/search/?industry=NonExistent")
    
    assert response.status_code == 200
    assert response.json() == []


def test_search_by_min_revenue(client):
    """Filter by minimum revenue returns matching accounts."""
    response = client.get("/accounts/search/?min_revenue=200000000")
    
    assert response.status_code == 200
    results = response.json()
    assert len(results) == 1
    assert results[0]["Name"] == "Burlington Textiles Corp"


def test_search_negative_revenue_invalid(client):
    """Negative revenue should be rejected with 422."""
    response = client.get("/accounts/search/?min_revenue=-100")
    
    assert response.status_code == 422


# ============================================================
# Batch endpoint
# ============================================================

def test_batch_queries(client):
    """POST /accounts/batch runs multiple queries."""
    response = client.post(
        "/accounts/batch",
        json={
            "queries": [
                "SELECT Id FROM Account",
                "SELECT Id FROM Account",
            ],
        },
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["total_queries"] == 2
    assert data["total_records"] == 6   # 2 queries × 3 records each
    assert len(data["results"]) == 2


def test_batch_empty_queries(client):
    """POST /accounts/batch with empty list returns zero results."""
    response = client.post(
        "/accounts/batch",
        json={"queries": []},
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["total_queries"] == 0
    assert data["total_records"] == 0