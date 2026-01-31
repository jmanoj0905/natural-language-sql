"""FastAPI application entry point."""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.api.v1.router import api_router
from app.core.database.connection_manager import get_db_manager
from app.models.database import DatabaseConfig
from app.exceptions import NLSQLException
from app.utils.logger import get_logger, configure_logging

# Configure logging
configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler.

    Handles startup and shutdown events.
    """
    # Startup
    # Load environment variables from .env file
    from dotenv import load_dotenv
    load_dotenv()

    settings = get_settings()
    logger.info(
        "application_starting",
        version=settings.API_VERSION,
        environment=settings.ENVIRONMENT,
        debug=settings.DEBUG
    )

    # For MVP: Configure database from environment variables
    # In production, this could be done via API endpoint or config file
    try:
        # Check if database configuration is available in environment
        import os
        if all([
            os.getenv("DB_HOST"),
            os.getenv("DB_PORT"),
            os.getenv("DB_NAME"),
            os.getenv("DB_USER"),
            os.getenv("DB_PASSWORD")
        ]):
            db_config = DatabaseConfig(
                host=os.getenv("DB_HOST"),
                port=int(os.getenv("DB_PORT")),
                database=os.getenv("DB_NAME"),
                username=os.getenv("DB_USER"),
                password=os.getenv("DB_PASSWORD"),
                ssl_mode=os.getenv("DB_SSL_MODE", "prefer")
            )

            db_manager = get_db_manager()
            db_manager.configure(db_config)
            logger.info("database_configured_from_environment")
        else:
            logger.warning(
                "database_not_configured",
                message="Database environment variables not set. Configure via API or environment."
            )
    except Exception as e:
        logger.error(
            "database_configuration_failed_at_startup",
            error=str(e)
        )

    yield

    # Shutdown
    logger.info("application_shutting_down")
    db_manager = get_db_manager()
    await db_manager.close()
    logger.info("application_shutdown_complete")


# Create FastAPI application
settings = get_settings()
app = FastAPI(
    title=settings.API_TITLE,
    version=settings.API_VERSION,
    description="Transform natural language questions into optimized SQL queries using Ollama (Local AI)",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global exception handler for NLSQLException
@app.exception_handler(NLSQLException)
async def nlsql_exception_handler(request: Request, exc: NLSQLException):
    """Handle NLSQLException globally."""
    from datetime import datetime

    logger.error(
        "nlsql_exception_caught",
        error_code=exc.code,
        error_message=exc.message,
        path=request.url.path
    )

    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "success": False,
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
                "timestamp": datetime.now().isoformat()
            }
        }
    )


# Include API router
app.include_router(api_router, prefix="/api/v1")


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": settings.API_TITLE,
        "version": settings.API_VERSION,
        "status": "running",
        "docs": "/docs",
        "health": "/api/v1/health"
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.RELOAD or settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower()
    )
