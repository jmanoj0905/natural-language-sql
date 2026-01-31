"""Query validation and sanitization module."""

import re
import sqlparse
from sqlparse.sql import Statement
from sqlparse.tokens import Keyword, DML

from app.config import get_settings
from app.exceptions import (
    QueryValidationError,
    ReadOnlyViolation,
    QuerySyntaxError,
    SQLInjectionAttempt
)
from app.core.security.sql_sanitizer import SQLSanitizer
from app.utils.logger import get_logger

logger = get_logger(__name__)


class QueryValidator:
    """
    Validates SQL queries for safety and compliance.

    Validation rules:
    1. Only SELECT statements allowed (read-only mode)
    2. No SQL injection patterns
    3. Valid SQL syntax
    4. Enforced LIMIT clause (max results)
    """

    def __init__(self):
        """Initialize query validator."""
        self.settings = get_settings()
        self.sanitizer = SQLSanitizer()

    def validate(self, sql: str, read_only: bool = True) -> str:
        """
        Validate and sanitize SQL query.

        Args:
            sql: SQL query to validate
            read_only: If True, only allow SELECT queries. If False, allow write operations.

        Returns:
            str: Validated and potentially modified SQL

        Raises:
            QueryValidationError: If validation fails
            ReadOnlyViolation: If non-SELECT query detected in read-only mode
            SQLInjectionAttempt: If SQL injection detected
            QuerySyntaxError: If SQL syntax is invalid
        """
        # Step 1: Basic checks
        if not sql or not sql.strip():
            raise QueryValidationError("SQL query cannot be empty")

        sql = sql.strip()

        # Step 2: Check for SQL injection patterns (allow write operations if not in read-only mode)
        self.sanitizer.validate_and_raise(sql, allow_write=not read_only)

        # Step 3: Parse SQL
        try:
            parsed = sqlparse.parse(sql)
        except Exception as e:
            logger.error("sql_parse_failed", error=str(e), sql=sql[:200])
            raise QuerySyntaxError(
                f"Failed to parse SQL: {str(e)}",
                sql=sql
            )

        if not parsed:
            raise QuerySyntaxError("Invalid SQL syntax", sql=sql)

        # Step 4: Allow all statement types
        statement = parsed[0]

        # Log if write operation is being allowed
        if not read_only and not self._is_select_statement(statement):
            detected_op = self._get_statement_type(statement)
            logger.warning(
                "write_operation_allowed",
                operation=detected_op,
                sql=sql[:200]
            )

        # Step 5: Check for multiple statements
        if len(parsed) > 1:
            raise QueryValidationError(
                "Multiple SQL statements are not allowed. Only one SELECT query permitted.",
                details={"statement_count": len(parsed)}
            )

        # Step 6: Enforce LIMIT clause (only for SELECT queries)
        if self._is_select_statement(statement):
            sql = self._enforce_limit(sql)

        logger.info("query_validated", sql=sql[:200], read_only=read_only)

        return sql

    def _is_select_statement(self, statement: Statement) -> bool:
        """
        Check if statement is a SELECT query.

        Args:
            statement: Parsed SQL statement

        Returns:
            bool: True if SELECT statement
        """
        # Get first significant token
        for token in statement.tokens:
            if token.ttype is Keyword.DML:
                return token.value.upper() == 'SELECT'
            elif not token.is_whitespace and token.ttype is not None:
                # If first significant token is not a keyword, might be CTE
                if token.value.upper() == 'WITH':
                    # Common Table Expression - check if it ends with SELECT
                    return 'SELECT' in statement.value.upper()
                return False

        # Check if statement contains SELECT
        return statement.get_type() == 'SELECT'

    def _get_statement_type(self, statement: Statement) -> str:
        """
        Get the type of SQL statement.

        Args:
            statement: Parsed SQL statement

        Returns:
            str: Statement type (SELECT, INSERT, UPDATE, etc.)
        """
        for token in statement.tokens:
            if token.ttype is Keyword.DML or token.ttype is Keyword.DDL:
                return token.value.upper()

        return "UNKNOWN"

    def _enforce_limit(self, sql: str) -> str:
        """
        Ensure query has a LIMIT clause.

        Args:
            sql: SQL query

        Returns:
            str: SQL with LIMIT clause
        """
        sql_upper = sql.upper()

        # Check if LIMIT already exists
        if 'LIMIT' in sql_upper:
            # Extract existing limit value
            match = re.search(r'LIMIT\s+(\d+)', sql_upper)
            if match:
                existing_limit = int(match.group(1))
                # Enforce maximum limit
                if existing_limit > self.settings.MAX_QUERY_RESULTS:
                    logger.warning(
                        "limit_exceeded_modified",
                        requested_limit=existing_limit,
                        max_limit=self.settings.MAX_QUERY_RESULTS
                    )
                    # Replace with max limit
                    sql = re.sub(
                        r'LIMIT\s+\d+',
                        f'LIMIT {self.settings.MAX_QUERY_RESULTS}',
                        sql,
                        flags=re.IGNORECASE
                    )
            return sql

        # Add default LIMIT if not present
        sql = sql.rstrip(';')  # Remove trailing semicolon if present
        sql = f"{sql} LIMIT {self.settings.DEFAULT_QUERY_LIMIT}"

        logger.debug("limit_added", limit=self.settings.DEFAULT_QUERY_LIMIT)

        return sql

    def validate_syntax_only(self, sql: str) -> bool:
        """
        Validate SQL syntax without other checks.

        Args:
            sql: SQL query

        Returns:
            bool: True if syntax is valid
        """
        try:
            parsed = sqlparse.parse(sql)
            return len(parsed) > 0 and parsed[0].get_type() is not None
        except Exception:
            return False
