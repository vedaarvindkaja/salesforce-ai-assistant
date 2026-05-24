"""FastAPI application entry point."""

from fastapi import FastAPI

app = FastAPI(
    title="Salesforce AI Assistant API",
    description="Backend API for the Salesforce AI Assistant project.",
    version="0.1.0",
)


@app.get("/health")
async def health_check() -> dict:
    """Simple endpoint to verify the server is running."""
    return {"status": "ok", "message": "Salesforce AI Assistant is alive"}