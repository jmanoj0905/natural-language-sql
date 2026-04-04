"""Health check endpoints."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.database.connection_manager import (
    get_db_manager,
    DatabaseConnectionManager,
)
from app.core.ai.ollama_client import get_ollama_client
from app.config import get_settings, Settings

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    version: str
    environment: str


class DatabaseHealthResponse(BaseModel):
    """Database health check response."""

    database_configured: bool
    database_connected: bool


class OllamaHealthResponse(BaseModel):
    """Ollama health check response."""

    status: str
    models: list[str]
    configured_model: str
    model_available: bool


@router.get("/health", response_model=HealthResponse)
async def health_check(settings: Settings = Depends(get_settings)) -> HealthResponse:
    """
    Basic health check endpoint.

    Returns application status and version information.
    """
    return HealthResponse(
        status="healthy", version=settings.API_VERSION, environment=settings.ENVIRONMENT
    )


@router.get("/health/database", response_model=DatabaseHealthResponse)
async def database_health_check(
    db_manager: DatabaseConnectionManager = Depends(get_db_manager),
) -> DatabaseHealthResponse:
    """
    Check database connection health.

    Returns database configuration and connection status.
    """
    is_configured = db_manager.is_configured
    is_connected = False

    if is_configured:
        is_connected = await db_manager.test_connection()

    return DatabaseHealthResponse(
        database_configured=is_configured, database_connected=is_connected
    )


@router.get("/health/ollama", response_model=OllamaHealthResponse)
async def ollama_health_check() -> OllamaHealthResponse:
    """
    Check Ollama service health.

    Returns Ollama availability, loaded models, and whether the configured model is available.
    """
    client = get_ollama_client()
    health = await client.check_health()

    return OllamaHealthResponse(
        status=health["status"],
        models=health.get("models", []),
        configured_model=health.get("configured_model", ""),
        model_available=health.get("model_available", False),
    )
