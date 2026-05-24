"""Account-related API endpoints."""

from fastapi import APIRouter, HTTPException, Query
from app.models.salesforce import Account
from app.services.salesforce_mock import MockSalesforceClient

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.get("/", response_model=list[Account])
async def list_accounts(
    limit: int = Query(10, ge=1, le=100, description="Number of records to return"),
) -> list[Account]:
    """List accounts (currently using mock data).
    
    Args:
        limit: Maximum number of records to return (1-100, default: 10)
    """
    async with MockSalesforceClient() as client:
        await client.authenticate()
        result = await client.query(f"SELECT Id, Name FROM Account LIMIT {limit}")
        return result.records


@router.get("/search/", response_model=list[Account])
async def search_accounts(
    industry: str | None = Query(None, description="Filter by industry (e.g., Electronics)"),
    min_revenue: float | None = Query(None, ge=0, description="Minimum annual revenue"),
) -> list[Account]:
    """Search accounts by industry and/or minimum revenue.
    
    Both parameters are optional. If neither is provided, returns all accounts.
    """
    async with MockSalesforceClient() as client:
        await client.authenticate()
        result = await client.query("SELECT Id, Name FROM Account")
        
        records = result.records
        
        if industry:
            records = [r for r in records if r.Industry == industry]
        
        if min_revenue is not None:
            records = [r for r in records if (r.AnnualRevenue or 0) >= min_revenue]
        
        return records


@router.get("/{account_id}", response_model=Account)
async def get_account(account_id: str) -> Account:
    """Get a single account by ID.
    
    Args:
        account_id: Salesforce Account ID (e.g., 0015g00000Abc1AAB)
    
    Raises:
        404 if no account with that ID exists.
    """
    async with MockSalesforceClient() as client:
        await client.authenticate()
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