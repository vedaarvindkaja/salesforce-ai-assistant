"""Account-related API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.dependencies import get_sf_client
from app.models.salesforce import Account
from app.salesforce.mocks.rest_mock import MockSalesforceClient

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.get("/", response_model=list[Account])
async def list_accounts(
    limit: int = Query(10, ge=1, le=100, description="Number of records to return"),
    client: MockSalesforceClient = Depends(get_sf_client),
) -> list[Account]:
    """List accounts (currently using mock data).

    Args:
        limit: Maximum number of records to return (1-100, default: 10)
    """
    result = await client.query(f"SELECT Id, Name FROM Account LIMIT {limit}")
    return result.records


@router.get("/search/", response_model=list[Account])
async def search_accounts(
    industry: str | None = Query(None, description="Filter by industry (e.g., Electronics)"),
    min_revenue: float | None = Query(None, ge=0, description="Minimum annual revenue"),
    client: MockSalesforceClient = Depends(get_sf_client),
) -> list[Account]:
    """Search accounts by industry and/or minimum revenue.

    Both parameters are optional. If neither is provided, returns all accounts.
    """
    result = await client.query("SELECT Id, Name FROM Account")
    records = result.records

    if industry:
        records = [r for r in records if r.Industry == industry]

    if min_revenue is not None:
        records = [r for r in records if (r.AnnualRevenue or 0) >= min_revenue]

    return records


@router.get("/{account_id}", response_model=Account)
async def get_account(
    account_id: str,
    client: MockSalesforceClient = Depends(get_sf_client),
) -> Account:
    """Get a single account by ID.

    Raises:
        404 if no account with that ID exists.
    """
    result = await client.query(
        f"SELECT Id, Name FROM Account WHERE Id = '{account_id}'"
    )

    # In mock mode, the client returns all 3 accounts regardless of WHERE clause.
    # Manually filter to simulate proper behavior.
    matching = [r for r in result.records if r.Id == account_id]
    if not matching:
        raise HTTPException(
            status_code=404,
            detail=f"Account not found: {account_id}",
        )
    return matching[0]


# ============================================================
# Batch queries — demonstrates async concurrency
# ============================================================


class BatchQueryRequest(BaseModel):
    """A list of SOQL queries to run concurrently."""
    queries: list[str]


class BatchQueryResult(BaseModel):
    """Result of running a batch of queries."""
    total_queries: int
    total_records: int
    results: list[list[Account]]


@router.post("/batch", response_model=BatchQueryResult)
async def run_batch_queries(
    request: BatchQueryRequest,
    client: MockSalesforceClient = Depends(get_sf_client),
) -> BatchQueryResult:
    """Run multiple SOQL queries concurrently.

    Demonstrates async benefits — N queries run in the time of ~1
    instead of running sequentially.
    """
    responses = await client.query_all(*request.queries)
    return BatchQueryResult(
        total_queries=len(responses),
        total_records=sum(r.totalSize for r in responses),
        results=[r.records for r in responses],
    )