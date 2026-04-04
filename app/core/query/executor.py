"""Safe query execution module."""

import time
import asyncio
import sqlparse
from typing import List, Dict, Any, Tuple, Optional
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection
from decimal import Decimal
from datetime import date, datetime

from app.config import get_settings
from app.exceptions import QueryExecutionError, QueryTimeoutError
from app.core.query.error_humanizer import humanize_query_execution_error
from app.utils.logger import get_logger

logger = get_logger(__name__)


class QueryExecutor:
    """
    Executes validated SQL queries safely with timeout protection.
    """

    def __init__(self):
        """Initialize query executor."""
        self.settings = get_settings()

    async def execute(
        self,
        connection: AsyncConnection,
        sql: str,
        timeout_seconds: Optional[int] = None,
        pagination: Optional[Dict[str, int]] = None,
    ) -> Tuple[List[Dict[str, Any]], float, Optional[int]]:
        """
        Execute SQL query with timeout protection and optional pagination.

        Args:
            connection: Database connection
            sql: Validated SQL query
            timeout_seconds: Query timeout (uses config default if not specified)
            pagination: Optional dict with 'offset' and 'limit' keys

        Returns:
            Tuple of (results, execution_time_ms, total_rows)

        Raises:
            QueryTimeoutError: If query exceeds timeout
            QueryExecutionError: If query execution fails
        """
        if timeout_seconds is None:
            timeout_seconds = self.settings.QUERY_TIMEOUT_SECONDS

        start_time = time.time()

        try:
            result, total_rows = await asyncio.wait_for(
                self._execute_query(connection, sql, pagination),
                timeout=timeout_seconds,
            )

            execution_time_ms = (time.time() - start_time) * 1000

            log = logger.warning if execution_time_ms > 5000 else logger.info
            log(
                "query_executed",
                execution_time_ms=round(execution_time_ms, 2),
                row_count=len(result),
                total_rows=total_rows,
                sql=sql[:200],
            )

            return result, execution_time_ms, total_rows

        except asyncio.TimeoutError:
            execution_time = time.time() - start_time
            logger.error(
                "query_timeout",
                timeout_seconds=timeout_seconds,
                execution_time_seconds=round(execution_time, 2),
                sql=sql[:200],
            )
            raise QueryTimeoutError(timeout_seconds)

        except Exception as e:
            execution_time_ms = (time.time() - start_time) * 1000
            logger.error(
                "query_execution_failed",
                error=str(e),
                error_type=type(e).__name__,
                execution_time_ms=round(execution_time_ms, 2),
                sql=sql[:200],
            )
            human_message = humanize_query_execution_error(e, sql)
            raise QueryExecutionError(
                human_message,
                details={
                    "error_type": type(e).__name__,
                    "raw_error": str(e),
                    "sql": sql[:200],
                },
            )

    async def execute_explain(
        self, connection: AsyncConnection, sql: str
    ) -> List[Dict[str, Any]]:
        """
        Get query execution plan (EXPLAIN) for debugging slow queries.

        Args:
            connection: Database connection
            sql: SQL query to explain

        Returns:
            List of EXPLAIN output rows
        """
        explain_sql = f"EXPLAIN (FORMAT JSON) {sql}"
        result = await connection.execute(text(explain_sql))
        rows = result.mappings().all()

        return [
            {col: self._serialize_value(val) for col, val in row.items()}
            for row in rows
        ]

    async def _execute_query(
        self,
        connection: AsyncConnection,
        sql: str,
        pagination: Optional[Dict[str, int]] = None,
    ) -> Tuple[List[Dict[str, Any]], Optional[int]]:
        """
        Execute SQL query and fetch results.

        Args:
            connection: Database connection
            sql: SQL query
            pagination: Optional pagination dict with 'offset' and 'limit'

        Returns:
            Tuple of (result rows, total count if paginated else None)
        """
        parsed = sqlparse.parse(sql.strip())

        if len(parsed) == 2:
            stmt1_sql = str(parsed[0]).strip()
            stmt2_sql = str(parsed[1]).strip()
            if any(
                stmt1_sql.upper().startswith(op)
                for op in ("UPDATE", "INSERT", "DELETE")
            ):
                write_result = await connection.execute(text(stmt1_sql))
                affected = write_result.rowcount
                logger.info("compound_write_select", affected_rows=affected)
                select_result = await connection.execute(text(stmt2_sql))
                rows = select_result.mappings().all()
                return (
                    [
                        {col: self._serialize_value(val) for col, val in row.items()}
                        for row in rows
                    ],
                    None,
                )

        result = await connection.execute(text(sql))

        sql_upper = sql.strip().upper()
        is_write_operation = any(
            sql_upper.startswith(op) for op in ["DELETE", "UPDATE", "INSERT"]
        )

        if is_write_operation:
            affected_rows = result.rowcount
            return (
                [
                    {
                        "operation": "write",
                        "affected_rows": affected_rows,
                        "message": f"Successfully affected {affected_rows} row(s)",
                    }
                ],
                None,
            )

        rows = result.mappings().all()
        total_rows = len(rows)

        if pagination and pagination.get("limit"):
            offset = pagination.get("offset", 0)
            limit = pagination["limit"]
            rows = rows[offset : offset + limit]
            total_rows = len(rows)

        results = [
            {col: self._serialize_value(val) for col, val in row.items()}
            for row in rows
        ]

        total_count = None
        if pagination:
            total_count = (
                len(rows)
                if not isinstance(rows, list)
                else len(result.mappings().all())
            )

        return results, total_rows

    def _serialize_value(self, value: Any) -> Any:
        """
        Convert database value to JSON-serializable type.

        Args:
            value: Database value

        Returns:
            JSON-serializable value
        """
        if value is None:
            return None

        # Handle Decimal (common for NUMERIC/DECIMAL columns)
        if isinstance(value, Decimal):
            return float(value)

        # Handle datetime/date
        if isinstance(value, datetime):
            return value.isoformat()

        if isinstance(value, date):
            return value.isoformat()

        # Handle bytes
        if isinstance(value, bytes):
            try:
                return value.decode("utf-8")
            except UnicodeDecodeError:
                return str(value)

        # Already serializable types (str, int, float, bool, list, dict)
        return value
