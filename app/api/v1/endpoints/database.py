"""Database connection management endpoints."""

from fastapi import APIRouter, HTTPException, status
from typing import List, Dict, Any
from pydantic import BaseModel, Field

from app.core.database.connection_manager import get_db_manager
from app.core.database.adapters import get_adapter
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

        # Reject empty database_id — would poison the persisted config
        if not config.database_id or not config.database_id.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "message": "Database ID cannot be empty",
                    "code": "INVALID_DATABASE_ID"
                }
            )

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
            db_type=config.db_type,
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
                    schema_name = get_adapter(config.db_type).get_schema_name(config)
                    async with db_manager.get_connection(db_id) as conn:
                        result = await conn.execute(text(
                            "SELECT COUNT(*) FROM information_schema.tables "
                            "WHERE table_schema = :schema_name"
                        ), {"schema_name": schema_name})
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
        default_database_id=None
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
        default_id = db_manager._default_db_id
        if not default_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "message": "No default database is set",
                    "code": "DATABASE_NOT_CONFIGURED"
                }
            )
        config = db_manager.get_database_config(default_id)

        # Test connection
        is_connected = False
        try:
            async with db_manager.get_connection(default_id) as conn:
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
                "db_type": config.db_type,
                "is_connected": is_connected
            }
        }

    except HTTPException:
        raise
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
        default_id = db_manager._default_db_id
        if not default_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "message": "No default database is set",
                    "code": "DATABASE_NOT_CONFIGURED"
                }
            )
        await db_manager.disconnect_database(default_id)

        logger.info("database_disconnected", database_id=default_id)

        return {
            "success": True,
            "message": f"Database '{default_id}' disconnected successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("database_disconnect_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "message": f"Failed to disconnect database: {str(e)}",
                "code": "DATABASE_DISCONNECT_FAILED"
            }
        )


def _humanize_connection_error(error: Exception, host: str, port: int, database: str, username: str) -> str:
    """Translate raw driver exceptions into plain-English messages."""
    err = str(error).lower()

    if "connection refused" in err or "connect call failed" in err:
        return f"Can't reach the server. Is the database running on {host}:{port}?"
    if "could not translate host" in err or "name or service not known" in err or "nodename nor servname" in err or "getaddrinfo failed" in err:
        return f"Hostname '{host}' not found. Double-check the host address."
    if "timeout" in err or "timed out" in err:
        return f"Connection timed out. The server at {host}:{port} is not responding."
    if "password authentication failed" in err:
        return f"Wrong password for user '{username}'."
    if "access denied" in err:
        return f"Access denied — wrong username or password for '{username}'."
    if "role" in err and "does not exist" in err:
        return f"User '{username}' does not exist on this server."
    if "database" in err and "does not exist" in err:
        return f"Database '{database}' does not exist on this server."
    if "unknown database" in err:
        return f"Database '{database}' does not exist on this server."
    if "ssl" in err:
        return "SSL connection error. Try setting SSL Mode to 'Disable' for a local server."
    if "too many connections" in err:
        return "The server has too many open connections. Try again shortly."
    # Fallback — still clean up noise
    first_line = str(error).split('\n')[0].strip()
    return f"Connection failed: {first_line}"


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
        from sqlalchemy.ext.asyncio import create_async_engine

        # Build a DatabaseConfig so the adapter can work with it.
        # database_id is required by the model but never persisted here.
        db_config = DatabaseConfig(
            database_id="__test__",
            db_type=config.db_type or "postgresql",
            host=config.host,
            port=config.port,
            database=config.database,
            username=config.username,
            password=config.password,
            ssl_mode=config.ssl_mode
        )

        adapter = get_adapter(db_config.db_type)
        connection_url = adapter.build_connection_url(db_config)

        engine = create_async_engine(
            connection_url,
            pool_pre_ping=True,
            pool_size=1,
            max_overflow=0
        )

        try:
            async with engine.connect() as conn:
                # version() is standard SQL on both PostgreSQL and MySQL
                result = await conn.execute(text("SELECT version()"))
                version_info = result.fetchone()

                # Engine-specific size query via adapter
                size_query, size_params = adapter.get_size_query(db_config)
                size_result = await conn.execute(text(size_query), size_params)
                db_size = size_result.fetchone()[0] or "0 MB"

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
        human_msg = _humanize_connection_error(e, config.host, config.port, config.database, config.username)
        logger.error(
            "database_connection_test_failed",
            host=config.host,
            database=config.database,
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": human_msg,
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
        default_id = db_manager._default_db_id
        if not default_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "message": "No default database is set",
                    "code": "DATABASE_NOT_CONFIGURED"
                }
            )
        config = db_manager.get_database_config(default_id)
        adapter = get_adapter(config.db_type)
        schema_name = adapter.get_schema_name(config)

        async with db_manager.get_connection(default_id) as conn:
            # Table count — information_schema works on both engines;
            # only the schema name differs (handled by adapter above).
            table_count_result = await conn.execute(
                text("""
                    SELECT COUNT(*)
                    FROM information_schema.tables
                    WHERE table_schema = :schema_name
                """),
                {"schema_name": schema_name}
            )
            table_count = table_count_result.fetchone()[0]

            # Database size — engine-specific query via adapter
            size_query, size_params = adapter.get_size_query(config)
            db_size_result = await conn.execute(text(size_query), size_params)
            db_size = db_size_result.fetchone()[0] or "0 MB"

            # Active connection count — engine-specific via adapter
            conn_count_result = await conn.execute(
                text(adapter.get_connection_count_query())
            )
            active_connections = conn_count_result.fetchone()[0]

        # Get pool stats from the actual engine for this database
        pool_info = {}
        engine = db_manager._engines.get(default_id)
        if engine:
            try:
                overflow_fn = getattr(engine.pool, 'overflow', None)
                pool_info = {
                    "pool_size": engine.pool.size(),
                    "pool_overflow": overflow_fn() if callable(overflow_fn) else -1,
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

    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_database_stats_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "message": f"Failed to get database stats: {str(e)}",
                "code": "DATABASE_STATS_FAILED"
            }
        )


# ---------------------------------------------------------------------------
# Parameterised routes — MUST come after /current, /stats, /test so that
# FastAPI does not swallow those literal paths as {database_id}.
# ---------------------------------------------------------------------------

@router.get("/{database_id}", response_model=Dict[str, Any])
async def get_database_info(database_id: str):
    """Get detailed information about a specific database."""
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

        table_count = None
        if is_connected:
            try:
                schema_name = get_adapter(config.db_type).get_schema_name(config)
                async with db_manager.get_connection(database_id) as conn:
                    result = await conn.execute(text(
                        "SELECT COUNT(*) FROM information_schema.tables "
                        "WHERE table_schema = :schema_name"
                    ), {"schema_name": schema_name})
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


@router.put("/{database_id}", response_model=Dict[str, Any])
async def update_database(database_id: str, config: DatabaseConfigRequest):
    """
    Update an existing database connection.

    Disconnects the current engine, re-registers with the new config,
    and verifies the connection.  If the password field is empty the
    existing (encrypted) password is preserved.
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
        # If password is empty, keep the existing one (it stays encrypted on disk)
        password = config.password
        if not password:
            existing_config = db_manager.get_database_config(database_id)
            password = existing_config.password

        # Tear down the old engine
        await db_manager.disconnect_database(database_id)

        # Build updated config
        db_config = DatabaseConfig(
            database_id=database_id,
            nickname=config.nickname,
            db_type=config.db_type,
            host=config.host,
            port=config.port,
            database=config.database,
            username=config.username,
            password=password,
            ssl_mode=config.ssl_mode
        )

        # Re-register (creates engine + saves to disk)
        db_manager.register_database(database_id, db_config)

        # Verify the new connection works
        async with db_manager.get_connection(database_id) as conn:
            await conn.execute(text("SELECT 1"))

        logger.info("database_updated", database_id=database_id)

        return {
            "success": True,
            "message": f"Database '{database_id}' updated successfully",
            "database_id": database_id
        }

    except Exception as e:
        logger.error("database_update_failed", database_id=database_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": f"Failed to update database: {str(e)}",
                "code": "DATABASE_UPDATE_FAILED"
            }
        )


@router.delete("/{database_id}")
async def remove_database(database_id: str):
    """Remove a database connection."""
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
    """Set the default database for queries.

    Deprecated: the frontend no longer uses a default database concept.
    Kept for backwards compatibility with existing API consumers.
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
