"""Query validation module."""

import re
import sqlparse
from sqlparse.sql import Statement
from sqlparse.tokens import Keyword

from app.config import get_settings
from app.exceptions import (
    QueryValidationError,
    ReadOnlyViolation,
    QuerySyntaxError,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)


class QueryValidator:
    """
    Validates SQL queries.

    Only enforces two things:
    1. In read-only mode: block non-SELECT queries
    2. In read-only mode: enforce LIMIT clause
    """

    def __init__(self):
        self.settings = get_settings()

    def validate(self, sql: str, read_only: bool = True, original_question: str = None) -> str:
        """
        Validate SQL query.

        In read-only mode: only SELECT allowed, LIMIT enforced.
        In write mode: any valid SQL passes through.

        Args:
            sql: SQL query to validate
            read_only: If True, only allow SELECT queries
            original_question: Unused, kept for API compat

        Returns:
            str: Validated (and possibly LIMIT-amended) SQL
        """
        if not sql or not sql.strip():
            raise QueryValidationError("SQL query cannot be empty")

        sql = sql.strip()

        # Parse SQL
        try:
            parsed = sqlparse.parse(sql)
        except Exception as e:
            raise QuerySyntaxError(f"Failed to parse SQL: {str(e)}", sql=sql)

        if not parsed:
            raise QuerySyntaxError("Invalid SQL syntax", sql=sql)

        statement = parsed[0]

        # Read-only mode: block non-SELECT
        if read_only and not self._is_select_statement(statement):
            detected_op = self._get_statement_type(statement)
            raise ReadOnlyViolation(
                f"Only SELECT queries are allowed in read-only mode. Detected: {detected_op}",
                details={"detected_operation": detected_op}
            )

        # Block multiple statements (basic safety)
        if len(parsed) > 1:
            raise QueryValidationError(
                "Multiple SQL statements are not allowed.",
                details={"statement_count": len(parsed)}
            )

        # Enforce LIMIT only for SELECT in read-only mode
        if read_only and self._is_select_statement(statement):
            sql = self._enforce_limit(sql)

        logger.info("query_validated", sql=sql[:200], read_only=read_only)
        return sql

    def _is_select_statement(self, statement: Statement) -> bool:
        for token in statement.tokens:
            if token.ttype is Keyword.DML:
                return token.value.upper() == 'SELECT'
            elif not token.is_whitespace and token.ttype is not None:
                if token.value.upper() == 'WITH':
                    return 'SELECT' in statement.value.upper()
                return False
        return statement.get_type() == 'SELECT'

    def _get_statement_type(self, statement: Statement) -> str:
        for token in statement.tokens:
            if token.ttype in (Keyword.DML, Keyword.DDL):
                return token.value.upper()
        return "UNKNOWN"

    def _enforce_limit(self, sql: str) -> str:
        sql_upper = sql.upper()

        if 'LIMIT' in sql_upper:
            match = re.search(r'LIMIT\s+(\d+)', sql_upper)
            if match:
                existing_limit = int(match.group(1))
                if existing_limit > self.settings.MAX_QUERY_RESULTS:
                    sql = re.sub(
                        r'LIMIT\s+\d+',
                        f'LIMIT {self.settings.MAX_QUERY_RESULTS}',
                        sql,
                        flags=re.IGNORECASE
                    )
            return sql

        sql = sql.rstrip(';')
        sql = f"{sql} LIMIT {self.settings.DEFAULT_QUERY_LIMIT}"
        return sql
