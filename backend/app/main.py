"""FastAPI application entry point."""

from fastapi import FastAPI

from app.routes import accounts

app = FastAPI(
    title="Salesforce AI Assistant API",
    description="Backend API for the Salesforce AI Assistant project.",
    version="0.1.0",
)

# Include routers for each logical group of endpoints
app.include_router(accounts.router)


@app.get("/health")
async def health_check() -> dict:
    """Simple endpoint to verify the server is running."""
    return {"status": "ok", "message": "Salesforce AI Assistant is alive"}