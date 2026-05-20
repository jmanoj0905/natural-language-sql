"""Schema introspection utility for PostgreSQL and MySQL databases."""

import glob
import os
import re
import hashlib
from pathlib import Path
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

        # Acquire embedder lazily; fall back to None if sentence-transformers not installed.
        from app.core.database.retrieval.hybrid import HybridRetriever
        from app.core.ai.schema_embedder import get_schema_embedder, EmbedderUnavailableError

        embedder = None
        if settings.HYBRID_RETRIEVAL_ENABLED:
            try:
                embedder = get_schema_embedder()
            except EmbedderUnavailableError as e:
                logger.warning("embedder_unavailable_falling_back_to_bm25", error=str(e))
                embedder = None

        self._hybrid = HybridRetriever(
            embedder=embedder,
            index_dir=Path(settings.EMBEDDING_INDEX_DIR).expanduser(),
            max_seed_tables=settings.MAX_SEED_TABLES,
            max_tables=settings.MAX_TABLES,
            max_cols_per_table=settings.MAX_COLS_PER_TABLE,
            col_score_threshold=settings.COLUMN_SCORE_THRESHOLD,
            rrf_k=settings.RRF_K,
            include_sample_rows=settings.INCLUDE_SAMPLE_ROWS_COMPACT,
            hybrid_enabled=settings.HYBRID_RETRIEVAL_ENABLED,
        )

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
        foreign key relationships, and sample data using the formatter.
        """
        cache = self._get_cache(db_id)
        cache_key = f"schema_full_{sample_rows}"

        if cache is not None and cache_key in cache:
            return cache[cache_key]

        try:
            db_type, _ = self._get_db_info(db_id)
            tables_info = await self._get_all_tables_info(connection, max_tables, db_id)
            foreign_keys = await self._get_foreign_keys(connection, db_id)

            samples = None
            if include_sample_data:
                samples = {}
                for table in tables_info:
                    rows = await self._get_sample_rows(connection, table["name"], sample_rows, db_type)
                    if rows:
                        samples[table["name"]] = rows

            from app.core.database.retrieval.formatter import format_schema_context
            summary = format_schema_context(
                selected_tables=tables_info,
                foreign_keys=foreign_keys,
                sample_rows_by_table=samples,
                fallback_used=False,
            )

            if cache is not None:
                cache[cache_key] = summary

            return summary

        except Exception as e:
            logger.error("schema_introspection_failed", database_id=db_id, error=str(e))
            raise SchemaIntrospectionError(f"Failed to introspect schema: {str(e)}")

    async def get_relevant_schema_summary(
        self,
        connection: AsyncConnection,
        question: str,
        db_id: str = "default",
        max_tables: int = 12,
        progress=None,
    ) -> str:
        """
        Build a compact schema summary via the HybridRetriever pipeline
        (BM25 → vector → RRF fuse → FK expand → column prune → sample rows).
        """
        cache = self._get_cache(db_id)
        question_hash = hashlib.md5(question.strip().lower().encode()).hexdigest()[:12]
        cache_key = f"schema_relevant_{max_tables}_{question_hash}"

        if cache is not None and cache_key in cache:
            return cache[cache_key]

        try:
            db_type, _ = self._get_db_info(db_id)
            tables_info = await self._get_all_tables_info(connection, 50, db_id)
            foreign_keys = await self._get_foreign_keys(connection, db_id)
            schema_hash = await self.get_schema_version(connection, db_id)

            async def fetch_sample(table_name: str) -> list[dict]:
                return await self._get_sample_rows(
                    connection, table_name, get_settings().SAMPLE_ROWS_COMPACT, db_type
                )

            summary = await self._hybrid.build_context(
                question=question,
                db_id=db_id,
                schema_hash=schema_hash,
                tables_info=tables_info,
                foreign_keys=foreign_keys,
                sample_row_fetcher=fetch_sample,
                progress=progress,
            )

            if cache is not None:
                cache[cache_key] = summary

            logger.info(
                "schema_retrieval_complete",
                db_id=db_id,
                selected_table_count=summary.count("CREATE TABLE"),
            )
            return summary

        except Exception as e:
            logger.error("schema_retrieval_failed", database_id=db_id, error=str(e))
            raise SchemaIntrospectionError(f"Failed to retrieve schema context: {str(e)}")

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

    async def _get_primary_keys(
        self,
        connection: AsyncConnection,
        db_id: str = "default"
    ) -> Dict[str, set]:
        """Fetch primary key columns for each table, keyed by table name."""
        db_type, schema_name = self._get_db_info(db_id)

        if db_type == "mysql":
            query = text("""
                SELECT TABLE_NAME, COLUMN_NAME
                FROM information_schema.KEY_COLUMN_USAGE
                WHERE TABLE_SCHEMA = :schema_name
                  AND CONSTRAINT_NAME = 'PRIMARY'
            """)
        else:
            query = text("""
                SELECT tc.table_name, kcu.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                  ON tc.constraint_name = kcu.constraint_name
                 AND tc.table_schema = kcu.table_schema
                WHERE tc.constraint_type = 'PRIMARY KEY'
                  AND tc.table_schema = :schema_name
            """)

        try:
            result = await connection.execute(query, {"schema_name": schema_name})
            pks: Dict[str, set] = {}
            for row in result.fetchall():
                pks.setdefault(row[0], set()).add(row[1])
            return pks
        except Exception as e:
            logger.warning("primary_key_fetch_failed", error=str(e))
            return {}

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

        # Fetch PK and FK info to annotate columns
        pks = await self._get_primary_keys(connection, db_id)
        fks = await self._get_foreign_keys(connection, db_id)
        fk_cols_per_table: Dict[str, set] = {}
        for fk in fks:
            fk_cols_per_table.setdefault(fk["table"], set()).add(fk["column"])

        tables_dict: Dict[str, List[Dict[str, Any]]] = {}
        for row in rows:
            table_name = row[0]
            column_info = {
                "name": row[1],
                "type": row[2],
                "nullable": row[3] == "YES",
                "default": row[4],
                "is_generated": bool(row[5]) and row[5] != "NEVER",
                "is_pk": row[1] in pks.get(table_name, set()),
                "is_fk": row[1] in fk_cols_per_table.get(table_name, set()),
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
        """Clear TTL cache entries and any on-disk vector index files for this db_id."""
        if db_id in self._caches:
            self._caches[db_id].clear()

        # Delete vector index files for this db_id
        settings = get_settings()
        index_dir = Path(settings.EMBEDDING_INDEX_DIR).expanduser()
        pattern = str(index_dir / f"{db_id}__*.npz")
        for path in glob.glob(pattern):
            try:
                os.remove(path)
            except OSError as e:
                logger.warning("failed_to_delete_index", path=path, error=str(e))

    def clear_all_caches(self) -> None:
        for cache in self._caches.values():
            cache.clear()

    def clear_cache(self) -> None:
        self.clear_all_caches()
