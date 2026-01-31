"""Health check endpoints."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.database.connection_manager import get_db_manager, DatabaseConnectionManager
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


@router.get("/health", response_model=HealthResponse)
async def health_check(
    settings: Settings = Depends(get_settings)
) -> HealthResponse:
    """
    Basic health check endpoint.

    Returns application status and version information.
    """
    return HealthResponse(
        status="healthy",
        version=settings.API_VERSION,
        environment=settings.ENVIRONMENT
    )


@router.get("/health/database", response_model=DatabaseHealthResponse)
async def database_health_check(
    db_manager: DatabaseConnectionManager = Depends(get_db_manager)
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
        database_configured=is_configured,
        database_connected=is_connected
    )
