"""Database connection manager for PostgreSQL with async support."""

import asyncio
import json
from pathlib import Path
from typing import Optional, Dict, List
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine, AsyncConnection
from sqlalchemy.pool import NullPool, QueuePool
from sqlalchemy import text

from app.config import get_settings
from app.models.database import DatabaseConfig
from app.exceptions import DatabaseConnectionError, DatabaseConfigurationError
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Path to store database configurations
DB_CONFIG_FILE = Path.home() / ".nlsql" / "databases.json"


class DatabaseConnectionManager:
    """
    Manages PostgreSQL database connections with async support.

    Supports multiple database connections with unique identifiers.
    """

    def __init__(self):
        """Initialize the connection manager."""
        self._engines: Dict[str, AsyncEngine] = {}
        self._configs: Dict[str, DatabaseConfig] = {}
        self._default_db_id: Optional[str] = None
        self.settings = get_settings()

        # Load saved database configurations on startup
        self._load_saved_databases()

    def configure(self, config: DatabaseConfig) -> None:
        """
        Configure database connection (backwards compatible).

        If database_id is not provided in config, uses 'default' as ID.

        Args:
            config: Database configuration

        Raises:
            DatabaseConfigurationError: If configuration is invalid
        """
        # Backwards compatibility - use database_id from config
        db_id = config.database_id
        self.register_database(db_id, config)

    def register_database(self, db_id: str, config: DatabaseConfig, save_to_disk: bool = True) -> None:
        """
        Register a new database connection.

        Args:
            db_id: Unique database identifier
            config: Database configuration
            save_to_disk: Whether to save configurations to disk after registration

        Raises:
            DatabaseConfigurationError: If configuration is invalid or db_id exists
        """
        if db_id in self._engines:
            raise DatabaseConfigurationError(
                f"Database '{db_id}' is already registered",
                details={"database_id": db_id}
            )

        try:
            # Build PostgreSQL connection string
            connection_string = self._build_connection_string(config)

            # Create async engine with connection pooling
            engine = create_async_engine(
                connection_string,
                pool_size=self.settings.DB_POOL_SIZE,
                max_overflow=self.settings.DB_MAX_OVERFLOW,
                pool_recycle=self.settings.DB_POOL_RECYCLE,
                pool_pre_ping=True,  # Verify connections before using
                echo=self.settings.DEBUG,  # Log SQL in debug mode
            )

            self._engines[db_id] = engine
            self._configs[db_id] = config

            # Set as default if first database
            if self._default_db_id is None:
                self._default_db_id = db_id

            logger.info(
                "database_registered",
                database_id=db_id,
                host=config.host,
                port=config.port,
                database=config.database,
            )

            # Save to disk if requested
            if save_to_disk:
                self._save_databases()

        except Exception as e:
            logger.error(
                "database_registration_failed",
                database_id=db_id,
                error=str(e),
                host=config.host,
                port=config.port,
            )
            raise DatabaseConfigurationError(
                f"Failed to register database '{db_id}': {str(e)}",
                details={"database_id": db_id, "host": config.host, "port": config.port}
            )

    def _build_connection_string(self, config: DatabaseConfig) -> str:
        """
        Build database connection string for asyncpg (PostgreSQL) or aiomysql (MySQL).

        Args:
            config: Database configuration

        Returns:
            str: Connection string in appropriate format
        """
        db_type = config.db_type.lower()

        if db_type == "mysql":
            # MySQL connection string
            conn_str = (
                f"mysql+aiomysql://{config.username}:{config.password}"
                f"@{config.host}:{config.port}/{config.database}"
            )
            # MySQL doesn't use ssl_mode the same way, but we can add charset
            conn_str += "?charset=utf8mb4"
        else:
            # PostgreSQL connection string (default)
            conn_str = (
                f"postgresql+asyncpg://{config.username}:{config.password}"
                f"@{config.host}:{config.port}/{config.database}"
            )
            if config.ssl_mode:
                conn_str += f"?ssl={config.ssl_mode}"

        return conn_str

    @asynccontextmanager
    async def get_connection(self, db_id: Optional[str] = None) -> AsyncConnection:
        """
        Get an async database connection from the pool.

        Args:
            db_id: Database ID (uses default if not specified)

        Yields:
            AsyncConnection: Database connection

        Raises:
            DatabaseConnectionError: If connection cannot be established
        """
        # Determine which database to use
        target_db_id = db_id or self._default_db_id

        if not target_db_id:
            raise DatabaseConnectionError(
                "No database specified and no default database is set."
            )

        if target_db_id not in self._engines:
            raise DatabaseConnectionError(
                f"Database '{target_db_id}' not found. Available databases: {list(self._engines.keys())}",
                details={"database_id": target_db_id}
            )

        try:
            engine = self._engines[target_db_id]
            async with engine.begin() as connection:
                logger.debug("database_connection_acquired", database_id=target_db_id)
                yield connection
                # Transaction auto-commits on successful exit, rolls back on exception
                logger.debug("database_connection_released", database_id=target_db_id)

        except Exception as e:
            logger.error(
                "database_connection_failed",
                database_id=target_db_id,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise DatabaseConnectionError(
                f"Failed to connect to database '{target_db_id}': {str(e)}",
                details={"database_id": target_db_id, "error_type": type(e).__name__}
            )

    def list_databases(self) -> List[str]:
        """
        List all registered database IDs.

        Returns:
            List[str]: List of database IDs
        """
        return list(self._engines.keys())

    def get_database_config(self, db_id: str) -> DatabaseConfig:
        """
        Get configuration for a specific database.

        Args:
            db_id: Database ID

        Returns:
            DatabaseConfig: Database configuration

        Raises:
            DatabaseConnectionError: If database not found
        """
        if db_id not in self._configs:
            raise DatabaseConnectionError(
                f"Database '{db_id}' not found",
                details={"database_id": db_id}
            )
        return self._configs[db_id]

    async def disconnect_database(self, db_id: str) -> None:
        """
        Disconnect and remove a database.

        Args:
            db_id: Database ID to remove

        Raises:
            DatabaseConnectionError: If database not found
        """
        if db_id not in self._engines:
            raise DatabaseConnectionError(
                f"Database '{db_id}' not found",
                details={"database_id": db_id}
            )

        # Close engine
        engine = self._engines[db_id]
        await engine.dispose()

        # Remove from storage
        del self._engines[db_id]
        del self._configs[db_id]

        # Update default if needed
        if self._default_db_id == db_id:
            # Set new default to first available, or None
            self._default_db_id = next(iter(self._engines.keys()), None)

        logger.info("database_disconnected", database_id=db_id)

        # Save to disk
        self._save_databases()

    def set_default_database(self, db_id: str) -> None:
        """
        Set the default database for queries.

        Args:
            db_id: Database ID to set as default

        Raises:
            DatabaseConnectionError: If database not found
        """
        if db_id not in self._engines:
            raise DatabaseConnectionError(
                f"Database '{db_id}' not found",
                details={"database_id": db_id}
            )

        self._default_db_id = db_id
        logger.info("default_database_set", database_id=db_id)

        # Save to disk
        self._save_databases()

    async def is_database_connected(self, db_id: str) -> bool:
        """
        Check if a database is connected and responsive.

        Args:
            db_id: Database ID to test

        Returns:
            bool: True if connected, False otherwise
        """
        if db_id not in self._engines:
            return False

        try:
            async with self.get_connection(db_id) as conn:
                await conn.execute(text("SELECT 1"))
                return True
        except Exception as e:
            logger.debug("database_health_check_failed", database_id=db_id, error=str(e))
            return False

    async def test_connection(self, db_id: Optional[str] = None) -> bool:
        """
        Test database connection.

        Args:
            db_id: Database ID to test (uses default if not specified)

        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            async with self.get_connection(db_id) as conn:
                await conn.execute(text("SELECT 1"))
                logger.info("database_connection_test_successful", database_id=db_id or self._default_db_id)
                return True

        except Exception as e:
            logger.error(
                "database_connection_test_failed",
                database_id=db_id or self._default_db_id,
                error=str(e)
            )
            return False

    async def close(self) -> None:
        """Close all database connection pools."""
        for db_id, engine in list(self._engines.items()):
            await engine.dispose()
            logger.info("database_connection_pool_closed", database_id=db_id)

        self._engines.clear()
        self._configs.clear()
        self._default_db_id = None

    @property
    def is_configured(self) -> bool:
        """Check if at least one database is configured."""
        return len(self._engines) > 0

    def _save_databases(self) -> None:
        """Save all database configurations to disk."""
        try:
            # Create directory if it doesn't exist
            DB_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)

            # Prepare data to save
            data = {
                "default_db_id": self._default_db_id,
                "databases": {}
            }

            for db_id, config in self._configs.items():
                data["databases"][db_id] = {
                    "database_id": config.database_id,
                    "nickname": config.nickname,
                    "host": config.host,
                    "port": config.port,
                    "database": config.database,
                    "username": config.username,
                    "password": config.password,  # Note: In production, encrypt this!
                    "ssl_mode": config.ssl_mode,
                    "db_type": config.db_type
                }

            # Write to file
            with open(DB_CONFIG_FILE, 'w') as f:
                json.dump(data, f, indent=2)

            logger.info("databases_saved_to_disk", count=len(self._configs), path=str(DB_CONFIG_FILE))

        except Exception as e:
            logger.error("failed_to_save_databases", error=str(e))

    def _load_saved_databases(self) -> None:
        """Load database configurations from disk on startup."""
        if not DB_CONFIG_FILE.exists():
            logger.info("no_saved_databases_found", path=str(DB_CONFIG_FILE))
            return

        try:
            logger.info("loading_saved_databases", path=str(DB_CONFIG_FILE))

            with open(DB_CONFIG_FILE, 'r') as f:
                data = json.load(f)

            default_db_id = data.get("default_db_id")
            databases = data.get("databases", {})

            logger.info("found_saved_databases", count=len(databases), default_db=default_db_id)

            # Register each saved database (don't save back to disk during load)
            loaded_count = 0
            for db_id, config_data in databases.items():
                try:
                    logger.info("loading_database", database_id=db_id, config=config_data)
                    config = DatabaseConfig(**config_data)
                    self.register_database(db_id, config, save_to_disk=False)
                    loaded_count += 1
                    logger.info("database_loaded_from_disk", database_id=db_id)
                except Exception as e:
                    logger.error("failed_to_load_database", database_id=db_id, error=str(e), error_type=type(e).__name__)
                    import traceback
                    logger.error("database_load_traceback", traceback=traceback.format_exc())

            # Restore default database
            if default_db_id and default_db_id in self._engines:
                self._default_db_id = default_db_id
                logger.info("default_database_restored", database_id=default_db_id)

            logger.info("databases_loaded_from_disk", loaded=loaded_count, total=len(databases))

        except Exception as e:
            logger.error("failed_to_load_saved_databases", error=str(e), error_type=type(e).__name__)
            import traceback
            logger.error("load_databases_traceback", traceback=traceback.format_exc())


# Global instance for dependency injection
_db_manager: Optional[DatabaseConnectionManager] = None


def get_db_manager() -> DatabaseConnectionManager:
    """
    Get the global database manager instance.

    Returns:
        DatabaseConnectionManager: Database manager instance
    """
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseConnectionManager()
    return _db_manager
