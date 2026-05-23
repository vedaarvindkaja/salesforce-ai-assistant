"""Pydantic models for Salesforce API responses.

These models give us type-safe access to Salesforce REST API data.
Created during Week 1 (Pydantic learning); will be expanded as the project grows.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel

class SalesforceAttributes(BaseModel):
    """Metadata Salesforce includes on every record (type + URL)."""
    type: str
    url: str


class Account(BaseModel):
    """A Salesforce Account record."""
    attributes: SalesforceAttributes
    Id: str
    Name: str
    Industry: Optional[str] = None
    AnnualRevenue: Optional[float] = None
    Phone: Optional[str] = None
    Website: Optional[str] = None
    CreatedDate: Optional[datetime] = None


class SalesforceQueryResponse(BaseModel):
    """Wrapper around any SOQL query response."""
    totalSize: int
    done: bool
    records: list[Account]


class SalesforceAuthResponse(BaseModel):
    """Response from the Salesforce OAuth token endpoint."""
    access_token: str
    instance_url: str
    id: str
    token_type: str
    issued_at: str
    signature: str