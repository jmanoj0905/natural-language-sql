"""Database connection management endpoints."""

from fastapi import APIRouter, HTTPException, status
from typing import List, Dict, Any
from pydantic import BaseModel, Field

from app.core.database.connection_manager import get_db_manager
from app.models.database import DatabaseConfig, DatabaseInfo, DatabaseListResponse
from app.utils.logger import get_logger
from sqlalchemy import text

logger = get_logger(__name__)
router = APIRouter(prefix="/databases", tags=["databases"])


class DatabaseConfigRequest(BaseModel):
    """Request model for database configuration."""

    database_id: str = Field(..., description="Unique identifier for this database connection")
    nickname: str = Field(None, description="Friendly display name")
    db_type: str = Field(default="postgresql", description="Database type: postgresql or mysql")
    host: str = Field(..., description="Database host address")
    port: int = Field(..., description="Database port", ge=1, le=65535)
    database: str = Field(..., description="Database name")
    username: str = Field(..., description="Database username")
    password: str = Field(..., description="Database password")
    ssl_mode: str = Field(default="prefer", description="SSL mode (disable, prefer, require)")

    class Config:
        json_schema_extra = {
            "example": {
                "database_id": "prod-postgres-001",
                "host": "localhost",
                "port": 5432,
                "database": "myapp",
                "username": "readonly_user",
                "password": "secure_password",
                "ssl_mode": "prefer"
            }
        }


class DatabaseInfoResponse(BaseModel):
    """Response model for database information."""

    database_id: str
    host: str
    port: int
    database: str
    username: str
    ssl_mode: str
    is_connected: bool


@router.post("", response_model=Dict[str, Any])
async def register_database(config: DatabaseConfigRequest):
    """
    Register a new database connection.

    This endpoint allows you to configure a database connection that will be used
    for natural language query processing.

    **Security Note:** In production, consider encrypting passwords and using
    secure credential storage.
    """
    logger.info(
        "registering_database",
        database_id=config.database_id,
        host=config.host,
        database=config.database
    )

    try:
        db_manager = get_db_manager()

        # Check if database_id already exists
        if config.database_id in db_manager.list_databases():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "message": f"Database '{config.database_id}' already exists",
                    "code": "DATABASE_ALREADY_EXISTS"
                }
            )

        # Convert request to DatabaseConfig
        db_config = DatabaseConfig(
            database_id=config.database_id,
            nickname=config.nickname,
            host=config.host,
            port=config.port,
            database=config.database,
            username=config.username,
            password=config.password,
            ssl_mode=config.ssl_mode
        )

        # Register the database
        db_manager.register_database(config.database_id, db_config)

        # Test connection
        async with db_manager.get_connection(config.database_id) as conn:
            result = await conn.execute(text("SELECT 1"))
            result.fetchone()

        logger.info(
            "database_registered_successfully",
            database_id=config.database_id
        )

        return {
            "success": True,
            "message": "Database registered and connection verified",
            "database_id": config.database_id,
            "database": {
                "host": config.host,
                "port": config.port,
                "database": config.database,
                "username": config.username,
                "ssl_mode": config.ssl_mode
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "database_registration_failed",
            database_id=config.database_id,
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": f"Failed to register database: {str(e)}",
                "code": "DATABASE_REGISTRATION_FAILED"
            }
        )


@router.get("", response_model=DatabaseListResponse)
async def list_databases():
    """
    List all registered databases with their status.

    Returns information about all configured database connections including
    connection status and table counts.
    """
    db_manager = get_db_manager()
    db_ids = db_manager.list_databases()
    databases = []

    for db_id in db_ids:
        try:
            config = db_manager.get_database_config(db_id)
            is_connected = await db_manager.is_database_connected(db_id)

            # Get table count if connected
            table_count = None
            if is_connected:
                try:
                    async with db_manager.get_connection(db_id) as conn:
                        result = await conn.execute(text(
                            "SELECT COUNT(*) FROM information_schema.tables "
                            "WHERE table_schema = 'public'"
                        ))
                        table_count = result.fetchone()[0]
                except Exception as e:
                    logger.warning("failed_to_get_table_count", database_id=db_id, error=str(e))

            databases.append(DatabaseInfo(
                database_id=db_id,
                nickname=config.nickname,
                db_type=config.db_type,
                host=config.host,
                port=config.port,
                database=config.database,
                username=config.username,
                is_connected=is_connected,
                table_count=table_count,
                ssl_mode=config.ssl_mode
            ))
        except Exception as e:
            logger.error("failed_to_get_database_info", database_id=db_id, error=str(e))
            # Skip databases that fail to load
            continue

    return DatabaseListResponse(
        success=True,
        databases=databases,
        default_database_id=db_manager._default_db_id
    )


@router.get("/{database_id}", response_model=Dict[str, Any])
async def get_database_info(database_id: str):
    """
    Get detailed information about a specific database.

    Returns connection details, status, and whether it's the default database.
    """
    db_manager = get_db_manager()

    if database_id not in db_manager.list_databases():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "message": f"Database '{database_id}' not found",
                "code": "DATABASE_NOT_FOUND"
            }
        )

    try:
        config = db_manager.get_database_config(database_id)
        is_connected = await db_manager.is_database_connected(database_id)

        # Get table count if connected
        table_count = None
        if is_connected:
            try:
                async with db_manager.get_connection(database_id) as conn:
                    result = await conn.execute(text(
                        "SELECT COUNT(*) FROM information_schema.tables "
                        "WHERE table_schema = 'public'"
                    ))
                    table_count = result.fetchone()[0]
            except Exception as e:
                logger.warning("failed_to_get_table_count", database_id=database_id, error=str(e))

        database_info = DatabaseInfo(
            database_id=database_id,
            nickname=config.nickname,
            db_type=config.db_type,
            host=config.host,
            port=config.port,
            database=config.database,
            username=config.username,
            is_connected=is_connected,
            table_count=table_count,
            ssl_mode=config.ssl_mode
        )

        return {
            "success": True,
            "database": database_info,
            "is_default": database_id == db_manager._default_db_id
        }

    except Exception as e:
        logger.error("get_database_info_failed", database_id=database_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "message": f"Failed to get database info: {str(e)}",
                "code": "DATABASE_INFO_FAILED"
            }
        )


@router.delete("/{database_id}")
async def remove_database(database_id: str):
    """
    Remove a database connection.

    Disconnects and removes the specified database from the manager.
    """
    db_manager = get_db_manager()

    if database_id not in db_manager.list_databases():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "message": f"Database '{database_id}' not found",
                "code": "DATABASE_NOT_FOUND"
            }
        )

    try:
        await db_manager.disconnect_database(database_id)

        logger.info("database_removed", database_id=database_id)

        return {
            "success": True,
            "message": f"Database '{database_id}' disconnected and removed"
        }

    except Exception as e:
        logger.error("remove_database_failed", database_id=database_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "message": f"Failed to remove database: {str(e)}",
                "code": "DATABASE_REMOVE_FAILED"
            }
        )


@router.post("/{database_id}/set-default")
async def set_default_database(database_id: str):
    """
    Set the default database for queries.

    The default database is used when no database_id is specified in a query.
    """
    db_manager = get_db_manager()

    if database_id not in db_manager.list_databases():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "message": f"Database '{database_id}' not found",
                "code": "DATABASE_NOT_FOUND"
            }
        )

    try:
        db_manager.set_default_database(database_id)

        logger.info("default_database_set", database_id=database_id)

        return {
            "success": True,
            "default_database_id": database_id
        }

    except Exception as e:
        logger.error("set_default_database_failed", database_id=database_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "message": f"Failed to set default database: {str(e)}",
                "code": "SET_DEFAULT_FAILED"
            }
        )


@router.get("/current", response_model=Dict[str, Any])
async def get_current_database():
    """
    Get information about the currently configured database.

    Returns connection details (without password) and connection status.
    """
    db_manager = get_db_manager()

    if not db_manager.is_configured:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "message": "No database is currently configured",
                "code": "DATABASE_NOT_CONFIGURED"
            }
        )

    try:
        config = db_manager._config

        # Test connection
        is_connected = False
        try:
            async with db_manager.get_connection() as conn:
                from sqlalchemy import text
                await conn.execute(text("SELECT 1"))
                is_connected = True
        except Exception as e:
            logger.warning("database_connection_test_failed", error=str(e))

        return {
            "success": True,
            "database": {
                "host": config.host,
                "port": config.port,
                "database": config.database,
                "username": config.username,
                "ssl_mode": config.ssl_mode,
                "is_connected": is_connected
            }
        }

    except Exception as e:
        logger.error("get_current_database_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "message": f"Failed to get database info: {str(e)}",
                "code": "DATABASE_INFO_FAILED"
            }
        )


@router.delete("/current")
async def disconnect_database():
    """
    Disconnect from the currently configured database.

    This clears the database configuration and closes all connections.
    """
    db_manager = get_db_manager()

    if not db_manager.is_configured:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "message": "No database is currently configured",
                "code": "DATABASE_NOT_CONFIGURED"
            }
        )

    try:
        await db_manager.close()

        logger.info("database_disconnected")

        return {
            "success": True,
            "message": "Database disconnected successfully"
        }

    except Exception as e:
        logger.error("database_disconnect_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "message": f"Failed to disconnect database: {str(e)}",
                "code": "DATABASE_DISCONNECT_FAILED"
            }
        )


@router.post("/test", response_model=Dict[str, Any])
async def test_database_connection(config: DatabaseConfigRequest):
    """
    Test a database connection without registering it.

    This is useful for validating credentials before registering a database.
    """
    logger.info(
        "testing_database_connection",
        host=config.host,
        database=config.database
    )

    try:
        # Import required modules
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine
        from sqlalchemy import text
        import asyncpg

        # Build connection URL
        connection_url = (
            f"postgresql+asyncpg://{config.username}:{config.password}"
            f"@{config.host}:{config.port}/{config.database}"
        )

        # Add SSL mode
        if config.ssl_mode:
            connection_url += f"?ssl={config.ssl_mode}"

        # Create temporary engine
        engine: AsyncEngine = create_async_engine(
            connection_url,
            pool_pre_ping=True,
            pool_size=1,
            max_overflow=0
        )

        try:
            # Test connection
            async with engine.connect() as conn:
                result = await conn.execute(text("SELECT version()"))
                version_info = result.fetchone()

                # Get database size
                size_result = await conn.execute(
                    text("SELECT pg_size_pretty(pg_database_size(:dbname))"),
                    {"dbname": config.database}
                )
                db_size = size_result.fetchone()[0]

            logger.info(
                "database_connection_test_successful",
                host=config.host,
                database=config.database
            )

            return {
                "success": True,
                "message": "Connection successful",
                "database_info": {
                    "version": version_info[0] if version_info else "Unknown",
                    "size": db_size,
                    "host": config.host,
                    "port": config.port,
                    "database": config.database
                }
            }

        finally:
            await engine.dispose()

    except Exception as e:
        logger.error(
            "database_connection_test_failed",
            host=config.host,
            database=config.database,
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": f"Connection test failed: {str(e)}",
                "code": "CONNECTION_TEST_FAILED"
            }
        )


@router.get("/stats", response_model=Dict[str, Any])
async def get_database_stats():
    """
    Get statistics about the current database.

    Returns information like table count, database size, and connection pool status.
    """
    db_manager = get_db_manager()

    if not db_manager.is_configured:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "message": "No database is currently configured",
                "code": "DATABASE_NOT_CONFIGURED"
            }
        )

    try:
        async with db_manager.get_connection() as conn:
            from sqlalchemy import text

            # Get table count
            table_count_result = await conn.execute(
                text("""
                    SELECT COUNT(*)
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                """)
            )
            table_count = table_count_result.fetchone()[0]

            # Get database size
            db_size_result = await conn.execute(
                text("SELECT pg_size_pretty(pg_database_size(current_database()))")
            )
            db_size = db_size_result.fetchone()[0]

            # Get connection count
            conn_count_result = await conn.execute(
                text("""
                    SELECT count(*)
                    FROM pg_stat_activity
                    WHERE datname = current_database()
                """)
            )
            active_connections = conn_count_result.fetchone()[0]

        # Get pool stats
        pool_info = {}
        if db_manager._engine:
            try:
                pool_info = {
                    "pool_size": db_manager._engine.pool.size(),
                    "pool_overflow": getattr(db_manager._engine.pool, 'overflow', -1),
                }
            except Exception as e:
                logger.warning("failed_to_get_pool_stats", error=str(e))
                pool_info = {"pool_size": 0}

        return {
            "success": True,
            "stats": {
                "table_count": table_count,
                "database_size": db_size,
                "active_connections": active_connections,
                **pool_info
            }
        }

    except Exception as e:
        logger.error("get_database_stats_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "message": f"Failed to get database stats: {str(e)}",
                "code": "DATABASE_STATS_FAILED"
            }
        )
