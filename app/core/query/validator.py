"""Query validation module."""

import re
import sqlparse
from sqlparse.sql import Statement
from sqlparse.tokens import Keyword

from app.config import get_settings
from app.exceptions import (
    QueryValidationError,
    QuerySyntaxError,
)
from app.core.security.sql_sanitizer import SQLSanitizer
from app.utils.logger import get_logger

logger = get_logger(__name__)

WRITE_STATEMENT_TYPES = {"UPDATE", "INSERT", "DELETE"}


class QueryValidator:
    """
    Validates SQL queries.

    Enforces:
    1. Non-empty SQL
    2. Single statement only
    3. LIMIT on SELECT queries
    """

    def __init__(self):
        self.settings = get_settings()

    def validate(self, sql: str) -> str:
        """
        Validate SQL query. All operation types (SELECT, INSERT, UPDATE, DELETE, etc.) are allowed.
        SELECT queries get a LIMIT enforced if not already present.

        Args:
            sql: SQL query to validate

        Returns:
            str: Validated (and possibly LIMIT-amended) SQL
        """
        if not sql or not sql.strip():
            raise QueryValidationError("SQL query cannot be empty")

        sql = sql.strip()

        try:
            parsed = sqlparse.parse(sql)
        except Exception as e:
            raise QuerySyntaxError(f"Failed to parse SQL: {str(e)}", sql=sql)

        if not parsed:
            raise QuerySyntaxError("Invalid SQL syntax", sql=sql)

        statement = parsed[0]

        # Block multiple statements — except exactly write + SELECT.
        if len(parsed) > 1:
            if len(parsed) == 2:
                first_type = self._get_statement_type(parsed[0])
                second_type = self._get_statement_type(parsed[1])
                if first_type in WRITE_STATEMENT_TYPES and second_type == "SELECT":
                    self._ensure_allowed_statement(parsed[0])
                    self._ensure_allowed_statement(parsed[1])
                    logger.info("compound_write_read_query", first=first_type)
                    first_sql = str(parsed[0]).strip()
                    second_sql = self._enforce_limit(str(parsed[1]).strip())
                    self._validate_strict_mode(first_sql)
                    self._validate_strict_mode(second_sql)
                    return f"{first_sql} {second_sql}"
            raise QueryValidationError(
                "Multiple SQL statements are not allowed.",
                details={"statement_count": len(parsed)}
            )

        self._ensure_allowed_statement(statement)
        self._validate_strict_mode(sql)

        # Enforce LIMIT on SELECT queries
        if self._is_select_statement(statement):
            sql = self._enforce_limit(sql)

        logger.info("query_validated", sql=sql[:200])
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

    def _ensure_allowed_statement(self, statement: Statement) -> None:
        statement_type = self._get_statement_type(statement)
        if statement_type in WRITE_STATEMENT_TYPES or self._is_select_statement(statement):
            return

        raise QueryValidationError(
            "Only SELECT, INSERT, UPDATE, and DELETE statements are allowed.",
            details={"statement_type": statement_type},
        )

    def _validate_strict_mode(self, sql: str) -> None:
        strict_mode = getattr(self.settings, "STRICT_SQL_VALIDATION", False)
        if strict_mode is not True:
            return

        SQLSanitizer.validate_and_raise(
            sql,
            allow_write=True,
            strict_mode=True,
        )

    def _enforce_limit(self, sql: str) -> str:
        sql_upper = sql.upper()

        if "LIMIT" in sql_upper:
            match = re.search(r"LIMIT\s+(\d+)", sql_upper)
            if match:
                existing_limit = int(match.group(1))
                if existing_limit > self.settings.MAX_QUERY_RESULTS:
                    sql = re.sub(
                        r"LIMIT\s+\d+",
                        f"LIMIT {self.settings.MAX_QUERY_RESULTS}",
                        sql,
                        flags=re.IGNORECASE
                    )
            return sql

        default_limit = min(
            self.settings.DEFAULT_QUERY_LIMIT,
            self.settings.MAX_QUERY_RESULTS,
        )
        if sql.endswith(";"):
            return f"{sql[:-1].rstrip()} LIMIT {default_limit};"
        return f"{sql} LIMIT {default_limit};"
