"""Safe query execution module."""

import time
import asyncio
from typing import List, Dict, Any, Tuple
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection
from decimal import Decimal
from datetime import date, datetime

from app.config import get_settings
from app.exceptions import QueryExecutionError, QueryTimeoutError
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
        timeout_seconds: int = None
    ) -> Tuple[List[Dict[str, Any]], float]:
        """
        Execute SQL query with timeout protection.

        Args:
            connection: Database connection
            sql: Validated SQL query
            timeout_seconds: Query timeout (uses config default if not specified)

        Returns:
            Tuple of (results, execution_time_ms)

        Raises:
            QueryTimeoutError: If query exceeds timeout
            QueryExecutionError: If query execution fails
        """
        if timeout_seconds is None:
            timeout_seconds = self.settings.QUERY_TIMEOUT_SECONDS

        start_time = time.time()

        try:
            # Execute query with timeout
            result = await asyncio.wait_for(
                self._execute_query(connection, sql),
                timeout=timeout_seconds
            )

            execution_time_ms = (time.time() - start_time) * 1000

            logger.info(
                "query_executed",
                execution_time_ms=round(execution_time_ms, 2),
                row_count=len(result),
                sql=sql[:200]
            )

            return result, execution_time_ms

        except asyncio.TimeoutError:
            execution_time = time.time() - start_time
            logger.error(
                "query_timeout",
                timeout_seconds=timeout_seconds,
                execution_time_seconds=round(execution_time, 2),
                sql=sql[:200]
            )
            raise QueryTimeoutError(timeout_seconds)

        except Exception as e:
            execution_time_ms = (time.time() - start_time) * 1000
            logger.error(
                "query_execution_failed",
                error=str(e),
                error_type=type(e).__name__,
                execution_time_ms=round(execution_time_ms, 2),
                sql=sql[:200]
            )
            raise QueryExecutionError(
                f"Query execution failed: {str(e)}",
                details={
                    "error_type": type(e).__name__,
                    "sql": sql[:200]
                }
            )

    async def _execute_query(
        self,
        connection: AsyncConnection,
        sql: str
    ) -> List[Dict[str, Any]]:
        """
        Execute SQL query and fetch results.

        Args:
            connection: Database connection
            sql: SQL query

        Returns:
            List of result rows as dictionaries (or affected row info for write operations)
        """
        # Execute query
        result = await connection.execute(text(sql))

        # Check if this is a write operation (DELETE, UPDATE, INSERT)
        sql_upper = sql.strip().upper()
        is_write_operation = any(sql_upper.startswith(op) for op in ['DELETE', 'UPDATE', 'INSERT'])

        if is_write_operation:
            # For write operations, return the affected row count
            affected_rows = result.rowcount
            return [{
                "operation": "write",
                "affected_rows": affected_rows,
                "message": f"Successfully affected {affected_rows} row(s)"
            }]

        # For SELECT queries, fetch all rows
        rows = result.fetchall()

        # Get column names
        columns = result.keys()

        # Convert rows to dictionaries with serializable values
        results = []
        for row in rows:
            row_dict = {}
            for col_name, value in zip(columns, row):
                # Convert non-JSON-serializable types
                row_dict[col_name] = self._serialize_value(value)
            results.append(row_dict)

        return results

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
                return value.decode('utf-8')
            except UnicodeDecodeError:
                return str(value)

        # Already serializable types (str, int, float, bool, list, dict)
        return value
