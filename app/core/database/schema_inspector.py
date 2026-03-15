"""Schema introspection utility for PostgreSQL and MySQL databases."""

import re
import hashlib
from typing import List, Dict, Any, Optional
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection
from cachetools import TTLCache

from app.config import get_settings
from app.exceptions import SchemaIntrospectionError, TableNotFoundError
from app.utils.logger import get_logger

logger = get_logger(__name__)

VALID_IDENTIFIER_PATTERN = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')


class SchemaInspector:
    """Inspects database schema including tables, columns, foreign keys, and sample data."""

    def __init__(self):
        settings = get_settings()
        self._caches: Dict[str, TTLCache] = {}
        self._cache_enabled = settings.ENABLE_SCHEMA_CACHE
        self._cache_ttl = settings.SCHEMA_CACHE_TTL_SECONDS

    @staticmethod
    def _validate_identifier(name: str, identifier_type: str = "identifier") -> None:
        if not name:
            raise ValueError(f"Invalid {identifier_type} name: cannot be empty")
        if len(name) > 63:
            raise ValueError(f"Invalid {identifier_type} name: exceeds 63 characters")
        if not VALID_IDENTIFIER_PATTERN.match(name):
            raise ValueError(f"Invalid {identifier_type} name '{name}'")

    def _get_cache(self, db_id: str) -> Optional[TTLCache]:
        if not self._cache_enabled:
            return None
        if db_id not in self._caches:
            self._caches[db_id] = TTLCache(maxsize=100, ttl=self._cache_ttl)
        return self._caches[db_id]

    def _get_db_info(self, db_id: str) -> tuple:
        from app.core.database.connection_manager import get_db_manager
        try:
            config = get_db_manager().get_database_config(db_id)
            db_type = config.db_type.lower()
            schema_name = config.database if db_type == "mysql" else "public"
            return db_type, schema_name
        except Exception:
            return "postgresql", "public"

    async def get_schema_version(self, connection: AsyncConnection, db_id: str = "default") -> int:
        _, schema_name = self._get_db_info(db_id)
        query = text("""
            SELECT table_name, column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = :schema_name
            ORDER BY table_name, ordinal_position
        """)
        result = await connection.execute(query, {"schema_name": schema_name})
        rows = result.fetchall()
        schema_str = "".join([f"{r[0]}{r[1]}{r[2]}" for r in rows])
        return int(hashlib.md5(schema_str.encode()).hexdigest()[:8], 16)

    async def get_schema_summary(
        self,
        connection: AsyncConnection,
        db_id: str = "default",
        max_tables: int = 50,
        include_sample_data: bool = True,
        sample_rows: int = 3,
        for_ai_prompt: bool = False
    ) -> str:
        """
        Build a rich schema summary with CREATE TABLE statements,
        foreign key relationships, and sample data.
        """
        cache = self._get_cache(db_id)
        cache_key = f"schema_full_{sample_rows}"

        if cache is not None and cache_key in cache:
            return cache[cache_key]

        try:
            db_type, schema_name = self._get_db_info(db_id)

            # Fetch tables + columns
            tables_info = await self._get_all_tables_info(connection, max_tables, db_id)

            # Fetch foreign keys
            foreign_keys = await self._get_foreign_keys(connection, db_id)

            # Build FK lookup: table_name -> list of FK dicts
            fk_by_table: Dict[str, List[Dict]] = {}
            for fk in foreign_keys:
                fk_by_table.setdefault(fk["table"], []).append(fk)

            lines = []

            for table in tables_info:
                table_name = table["name"]
                columns = table["columns"]

                # CREATE TABLE block
                lines.append(f"CREATE TABLE {table_name} (")
                col_lines = []
                for col in columns:
                    parts = [f"  {col['name']} {col['type']}"]
                    if not col.get("nullable", True):
                        parts.append("NOT NULL")
                    if col.get("default"):
                        parts.append(f"DEFAULT {col['default']}")
                    col_lines.append(" ".join(parts))

                # Add FK constraints inline
                table_fks = fk_by_table.get(table_name, [])
                for fk in table_fks:
                    col_lines.append(
                        f"  FOREIGN KEY ({fk['column']}) REFERENCES {fk['ref_table']}({fk['ref_column']})"
                    )

                lines.append(",\n".join(col_lines))
                lines.append(");")

                # Sample data
                if include_sample_data:
                    sample_data = await self._get_sample_rows(connection, table_name, sample_rows, db_type)
                    if sample_data:
                        lines.append(f"-- Sample rows from {table_name}:")
                        for i, row in enumerate(sample_data, 1):
                            row_str = ", ".join(f"{k}={repr(v)}" for k, v in row.items())
                            lines.append(f"--   {row_str}")

                lines.append("")  # blank line between tables

            # Relationship summary at the end
            if foreign_keys:
                lines.append("-- Relationships:")
                for fk in foreign_keys:
                    lines.append(
                        f"-- {fk['table']}.{fk['column']} -> {fk['ref_table']}.{fk['ref_column']}"
                    )

            summary = "\n".join(lines)

            if cache is not None:
                cache[cache_key] = summary

            return summary

        except Exception as e:
            logger.error("schema_introspection_failed", database_id=db_id, error=str(e))
            raise SchemaIntrospectionError(f"Failed to introspect schema: {str(e)}")

    async def _get_foreign_keys(
        self,
        connection: AsyncConnection,
        db_id: str = "default"
    ) -> List[Dict[str, str]]:
        """Fetch all foreign key relationships in the database."""
        db_type, schema_name = self._get_db_info(db_id)

        if db_type == "mysql":
            query = text("""
                SELECT
                    TABLE_NAME,
                    COLUMN_NAME,
                    REFERENCED_TABLE_NAME,
                    REFERENCED_COLUMN_NAME
                FROM information_schema.KEY_COLUMN_USAGE
                WHERE TABLE_SCHEMA = :schema_name
                    AND REFERENCED_TABLE_NAME IS NOT NULL
                ORDER BY TABLE_NAME, COLUMN_NAME
            """)
        else:
            # PostgreSQL
            query = text("""
                SELECT
                    tc.table_name,
                    kcu.column_name,
                    ccu.table_name AS ref_table,
                    ccu.column_name AS ref_column
                FROM information_schema.table_constraints AS tc
                JOIN information_schema.key_column_usage AS kcu
                    ON tc.constraint_name = kcu.constraint_name
                    AND tc.table_schema = kcu.table_schema
                JOIN information_schema.constraint_column_usage AS ccu
                    ON ccu.constraint_name = tc.constraint_name
                    AND ccu.table_schema = tc.table_schema
                WHERE tc.constraint_type = 'FOREIGN KEY'
                    AND tc.table_schema = :schema_name
                ORDER BY tc.table_name, kcu.column_name
            """)

        try:
            result = await connection.execute(query, {"schema_name": schema_name})
            rows = result.fetchall()
            return [
                {
                    "table": row[0],
                    "column": row[1],
                    "ref_table": row[2],
                    "ref_column": row[3]
                }
                for row in rows
            ]
        except Exception as e:
            logger.warning("foreign_key_fetch_failed", error=str(e))
            return []

    async def get_schema_for_database(
        self,
        connection: AsyncConnection,
        db_id: str,
        max_tables: int = 50
    ) -> List[Dict[str, Any]]:
        cache = self._get_cache(db_id)
        cache_key = f"{db_id}:schema"

        if cache is not None and cache_key in cache:
            return cache[cache_key]

        tables_info = await self._get_all_tables_info(connection, max_tables, db_id)

        if cache is not None:
            cache[cache_key] = tables_info

        return tables_info

    async def _get_all_tables_info(
        self,
        connection: AsyncConnection,
        max_tables: int,
        db_id: str = "default"
    ) -> List[Dict[str, Any]]:
        db_type, schema_name = self._get_db_info(db_id)
        generated_col = "GENERATION_EXPRESSION" if db_type == "mysql" else "is_generated"
        query = text(f"""
            SELECT
                table_name,
                column_name,
                data_type,
                is_nullable,
                column_default,
                {generated_col}
            FROM information_schema.columns
            WHERE table_schema = :schema_name
            ORDER BY table_name, ordinal_position
        """)

        result = await connection.execute(query, {"schema_name": schema_name})
        rows = result.fetchall()

        tables_dict: Dict[str, List[Dict[str, Any]]] = {}
        for row in rows:
            table_name = row[0]
            column_info = {
                "name": row[1],
                "type": row[2],
                "nullable": row[3] == "YES",
                "default": row[4],
                "is_generated": bool(row[5]) and row[5] != "NEVER"
            }
            if table_name not in tables_dict:
                tables_dict[table_name] = []
            tables_dict[table_name].append(column_info)
            if len(tables_dict) > max_tables:
                logger.warning("schema_truncated", db_id=db_id, max_tables=max_tables)
                break

        tables_info = [
            {"name": name, "columns": cols}
            for name, cols in list(tables_dict.items())[:max_tables]
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
        limit: int = 3,
        db_type: str = "postgresql"
    ) -> List[Dict[str, Any]]:
        try:
            self._validate_identifier(table_name, "table")
            quote = '`' if db_type == "mysql" else '"'
            quoted_table = f'{quote}{table_name}{quote}'
            query = text(f"SELECT * FROM {quoted_table} LIMIT :limit")
            result = await connection.execute(query, {"limit": limit})
            rows = result.fetchall()
            columns = result.keys()

            sample_data = []
            for row in rows:
                row_dict = {}
                for col_name, value in zip(columns, row):
                    if value is None:
                        row_dict[col_name] = None
                    elif isinstance(value, (str, int, float, bool)):
                        row_dict[col_name] = value
                    else:
                        row_dict[col_name] = str(value)
                sample_data.append(row_dict)
            return sample_data
        except ValueError:
            return []
        except Exception as e:
            logger.debug("failed_to_get_sample_rows", table_name=table_name, error=str(e))
            return []

    async def get_table_info(
        self,
        connection: AsyncConnection,
        table_name: str,
        db_id: str = "default"
    ) -> Dict[str, Any]:
        db_type, schema_name = self._get_db_info(db_id)
        generated_col = "GENERATION_EXPRESSION" if db_type == "mysql" else "is_generated"
        query = text(f"""
            SELECT
                column_name, data_type, is_nullable,
                column_default, character_maximum_length, {generated_col}
            FROM information_schema.columns
            WHERE table_schema = :schema_name AND table_name = :table_name
            ORDER BY ordinal_position
        """)
        result = await connection.execute(query, {"table_name": table_name, "schema_name": schema_name})
        rows = result.fetchall()

        if not rows:
            raise TableNotFoundError(table_name, "main_database")

        columns = [
            {
                "name": row[0], "type": row[1], "nullable": row[2] == "YES",
                "default": row[3], "max_length": row[4],
                "is_generated": bool(row[5]) and row[5] != "NEVER"
            }
            for row in rows
        ]
        return {"name": table_name, "columns": columns, "column_count": len(columns)}

    def clear_cache_for_database(self, db_id: str) -> None:
        if db_id in self._caches:
            self._caches[db_id].clear()

    def clear_all_caches(self) -> None:
        for cache in self._caches.values():
            cache.clear()

    def clear_cache(self) -> None:
        self.clear_all_caches()
