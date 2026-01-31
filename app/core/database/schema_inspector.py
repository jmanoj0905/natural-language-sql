"""Schema introspection utility for PostgreSQL databases."""

from typing import List, Dict, Any, Optional
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncConnection
from cachetools import TTLCache

from app.config import get_settings
from app.exceptions import SchemaIntrospectionError, TableNotFoundError
from app.utils.logger import get_logger

logger = get_logger(__name__)


class SchemaInspector:
    """
    Inspects database schema to provide context for SQL generation.

    Features:
    - Extract table and column information
    - Cache schema data per database to reduce database queries
    - Generate concise schema summaries for AI context
    """

    def __init__(self):
        """Initialize schema inspector with per-database caching."""
        settings = get_settings()
        self._caches: Dict[str, TTLCache] = {}
        self._cache_enabled = settings.ENABLE_SCHEMA_CACHE
        self._cache_ttl = settings.SCHEMA_CACHE_TTL_SECONDS

    def _get_cache(self, db_id: str) -> Optional[TTLCache]:
        """
        Get or create cache for specific database.

        Args:
            db_id: Database ID

        Returns:
            TTLCache for the database, or None if caching disabled
        """
        if not self._cache_enabled:
            return None

        if db_id not in self._caches:
            self._caches[db_id] = TTLCache(
                maxsize=100,
                ttl=self._cache_ttl
            )

        return self._caches[db_id]

    async def get_schema_summary(
        self,
        connection: AsyncConnection,
        db_id: str = "default",
        max_tables: int = 20,
        include_sample_data: bool = True,
        sample_rows: int = 3
    ) -> str:
        """
        Get a concise schema summary for AI context with sample data.

        Args:
            connection: Database connection
            db_id: Database ID for cache lookup
            max_tables: Maximum number of tables to include
            include_sample_data: Whether to include sample rows from each table
            sample_rows: Number of sample rows to fetch per table

        Returns:
            str: Formatted schema summary with sample data
        """
        cache = self._get_cache(db_id)
        cache_key = f"schema_summary_samples_{sample_rows}" if include_sample_data else "schema_summary"

        # Check cache
        if cache is not None and cache_key in cache:
            logger.debug("schema_cache_hit", database_id=db_id, key=cache_key)
            return cache[cache_key]

        try:
            # Get all tables
            tables_info = await self._get_all_tables_info(connection, max_tables)

            # Format as concise text
            summary_lines = ["Database Schema:"]

            for table in tables_info:
                table_name = table["name"]
                columns = table["columns"]

                # Format: table_name (col1 type1, col2 type2, ...)
                col_str = ", ".join(
                    f"{col['name']} {col['type']}"
                    for col in columns[:10]  # Limit columns per table
                )

                if len(columns) > 10:
                    col_str += f", ... ({len(columns)} total columns)"

                summary_lines.append(f"\n  Table: {table_name}")
                summary_lines.append(f"  Columns: {col_str}")

                # Add sample data if requested
                if include_sample_data:
                    sample_data = await self._get_sample_rows(connection, table_name, sample_rows)
                    if sample_data:
                        summary_lines.append(f"  Sample data ({len(sample_data)} rows):")
                        for i, row in enumerate(sample_data, 1):
                            # Format row as key=value pairs
                            row_str = ", ".join(f"{k}={repr(v)}" for k, v in list(row.items())[:5])
                            if len(row) > 5:
                                row_str += f", ... ({len(row)} columns total)"
                            summary_lines.append(f"    Row {i}: {row_str}")

            if len(tables_info) >= max_tables:
                summary_lines.append(f"\n  ... (showing first {max_tables} tables)")

            summary = "\n".join(summary_lines)

            # Cache the result
            if cache is not None:
                cache[cache_key] = summary
                logger.debug("schema_cached", database_id=db_id, key=cache_key)

            return summary

        except Exception as e:
            logger.error(
                "schema_introspection_failed",
                database_id=db_id,
                error=str(e)
            )
            raise SchemaIntrospectionError(
                f"Failed to introspect schema: {str(e)}"
            )

    async def get_schema_for_database(
        self,
        connection: AsyncConnection,
        db_id: str,
        max_tables: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Get schema with database-aware caching.

        Args:
            connection: Database connection
            db_id: Database ID for cache lookup
            max_tables: Maximum number of tables to retrieve

        Returns:
            List of table information dictionaries
        """
        cache = self._get_cache(db_id)
        cache_key = f"{db_id}:schema"

        # Check cache
        if cache is not None and cache_key in cache:
            logger.debug("schema_cache_hit", database_id=db_id)
            return cache[cache_key]

        # Fetch schema from database
        tables_info = await self._get_all_tables_info(connection, max_tables)

        # Store in database-specific cache
        if cache is not None:
            cache[cache_key] = tables_info
            logger.debug("schema_cached", database_id=db_id)

        return tables_info

    async def _get_all_tables_info(
        self,
        connection: AsyncConnection,
        max_tables: int
    ) -> List[Dict[str, Any]]:
        """
        Get information about all tables in the database.

        Args:
            connection: Database connection
            max_tables: Maximum number of tables to retrieve

        Returns:
            List of table information dictionaries
        """
        # Query to get table and column information from PostgreSQL
        query = text("""
            SELECT
                table_name,
                column_name,
                data_type,
                is_nullable,
                column_default
            FROM information_schema.columns
            WHERE table_schema = 'public'
            ORDER BY table_name, ordinal_position
            LIMIT :max_cols
        """)

        result = await connection.execute(
            query,
            {"max_cols": max_tables * 50}  # Assume ~50 columns per table max
        )

        rows = result.fetchall()

        # Group columns by table
        tables_dict: Dict[str, List[Dict[str, Any]]] = {}

        for row in rows:
            table_name = row[0]
            column_info = {
                "name": row[1],
                "type": row[2],
                "nullable": row[3] == "YES",
                "default": row[4]
            }

            if table_name not in tables_dict:
                tables_dict[table_name] = []

            tables_dict[table_name].append(column_info)

            # Stop if we've reached max tables
            if len(tables_dict) >= max_tables:
                break

        # Convert to list format
        tables_info = [
            {"name": table_name, "columns": columns}
            for table_name, columns in list(tables_dict.items())[:max_tables]
        ]

        logger.info(
            "schema_introspection_complete",
            table_count=len(tables_info),
            total_columns=sum(len(t["columns"]) for t in tables_info)
        )

        return tables_info

    async def _get_sample_rows(
        self,
        connection: AsyncConnection,
        table_name: str,
        limit: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Get sample rows from a table for context.

        Args:
            connection: Database connection
            table_name: Name of the table
            limit: Number of sample rows to fetch

        Returns:
            List of sample rows as dictionaries
        """
        try:
            # Use parameterized query safely - table name needs special handling
            # Since we can't parameterize table names, validate it first
            if not table_name.replace('_', '').isalnum():
                logger.warning("invalid_table_name_for_sampling", table_name=table_name)
                return []

            query = text(f"SELECT * FROM {table_name} LIMIT :limit")
            result = await connection.execute(query, {"limit": limit})
            rows = result.fetchall()
            columns = result.keys()

            # Convert to dictionaries
            sample_data = []
            for row in rows:
                row_dict = {}
                for col_name, value in zip(columns, row):
                    # Convert to string representation for display
                    if value is None:
                        row_dict[col_name] = None
                    elif isinstance(value, (str, int, float, bool)):
                        row_dict[col_name] = value
                    else:
                        row_dict[col_name] = str(value)
                sample_data.append(row_dict)

            return sample_data

        except Exception as e:
            logger.debug(
                "failed_to_get_sample_rows",
                table_name=table_name,
                error=str(e)
            )
            return []

    async def get_table_info(
        self,
        connection: AsyncConnection,
        table_name: str
    ) -> Dict[str, Any]:
        """
        Get detailed information about a specific table.

        Args:
            connection: Database connection
            table_name: Name of the table

        Returns:
            Dictionary with table information

        Raises:
            TableNotFoundError: If table doesn't exist
        """
        query = text("""
            SELECT
                column_name,
                data_type,
                is_nullable,
                column_default,
                character_maximum_length
            FROM information_schema.columns
            WHERE table_schema = 'public'
                AND table_name = :table_name
            ORDER BY ordinal_position
        """)

        result = await connection.execute(query, {"table_name": table_name})
        rows = result.fetchall()

        if not rows:
            raise TableNotFoundError(table_name, "main_database")

        columns = [
            {
                "name": row[0],
                "type": row[1],
                "nullable": row[2] == "YES",
                "default": row[3],
                "max_length": row[4]
            }
            for row in rows
        ]

        return {
            "name": table_name,
            "columns": columns,
            "column_count": len(columns)
        }

    def clear_cache_for_database(self, db_id: str) -> None:
        """
        Clear cache for specific database.

        Args:
            db_id: Database ID
        """
        if db_id in self._caches:
            self._caches[db_id].clear()
            logger.info("schema_cache_cleared", database_id=db_id)

    def clear_all_caches(self) -> None:
        """Clear caches for all databases."""
        for db_id, cache in self._caches.items():
            cache.clear()
        logger.info("all_schema_caches_cleared")

    def clear_cache(self) -> None:
        """Clear all schema caches (backwards compatible)."""
        self.clear_all_caches()
