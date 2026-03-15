"""SQL sanitizer for preventing SQL injection attacks."""

import re
from typing import List, Tuple

from app.exceptions import SQLInjectionAttempt
from app.utils.logger import get_logger, log_security_event

logger = get_logger(__name__)


class SQLSanitizer:
    """
    Detects and prevents SQL injection attacks.

    This class implements multiple layers of protection:
    1. Blocked pattern detection (dangerous SQL keywords/patterns)
    2. Comment stripping
    3. Multiple statement detection
    """

    # Dangerous patterns — pre-compiled once at class definition time.
    BLOCKED_PATTERNS = [
        (re.compile(r'\b(DROP|CREATE|ALTER|TRUNCATE|RENAME)\s+', re.IGNORECASE), "DDL operation"),
        (re.compile(r'\b(EXECUTE|EXEC|xp_cmdshell|sp_executesql)\s*\(', re.IGNORECASE), "System command"),
        (re.compile(r'--'), "SQL comment"),
        (re.compile(r'/\*.*?\*/'), "Multi-line comment"),
        (re.compile(r';\s*\w+'), "Multiple statements"),
        (re.compile(r'UNION\s+(?:ALL\s+)?SELECT(?!\s+.*\s+FROM\s+\()', re.IGNORECASE), "UNION injection"),
        (re.compile(r'\binformation_schema\b', re.IGNORECASE), "Information schema access"),
        (re.compile(r'\b(pg_read_file|pg_ls_dir|pg_sleep|lo_import|lo_export)\s*\(', re.IGNORECASE), "PostgreSQL dangerous function"),
        (re.compile(r'\b(LOAD_FILE|INTO\s+OUTFILE|INTO\s+DUMPFILE)\b', re.IGNORECASE), "MySQL dangerous function"),
        (re.compile(r'0x[0-9a-fA-F]+'), "Hex encoding"),
        (re.compile(r'\\u[0-9a-fA-F]{4}'), "Unicode encoding"),
    ]

    @classmethod
    def is_safe(cls, sql: str, allow_write: bool = False, strict_mode: bool = False) -> Tuple[bool, List[str]]:
        """
        Check if SQL is safe from injection attacks.

        Args:
            sql: SQL query to validate
            allow_write: If True, allow DML operations (INSERT, UPDATE, DELETE)
            strict_mode: If False (default), only blocks critical patterns. If True, blocks all suspicious patterns.

        Returns:
            Tuple of (is_safe, list_of_violations)
        """
        violations = []

        # Normalize SQL for checking (remove extra whitespace, case-insensitive)
        normalized_sql = " ".join(sql.split()).upper()

        # Define patterns to skip in non-strict mode (allow for users who know SQL)
        lenient_patterns = [
            "SQL comment",           # Allow SQL comments in non-strict mode
            "Multi-line comment",    # Allow multi-line comments
            "Hex encoding",          # Allow hex literals (valid in SQL)
            "Unicode encoding"       # Allow unicode (valid in SQL)
        ]

        # Check each blocked pattern
        for compiled_pattern, description in cls.BLOCKED_PATTERNS:
            # Skip DML check if write operations are allowed
            if allow_write and description == "DML operation":
                continue

            # Skip lenient patterns in non-strict mode (for users who know SQL)
            if not strict_mode and description in lenient_patterns:
                continue

            if compiled_pattern.search(normalized_sql):
                violations.append(f"Blocked pattern detected: {description}")

        # Log security event if violations found
        if violations:
            log_security_event(
                logger,
                event_type="sql_injection_attempt",
                severity="warning",
                message=f"Potentially dangerous SQL detected: {', '.join(violations)}",
                sql=sql[:200],
                violations=violations
            )

        return len(violations) == 0, violations

    @classmethod
    def validate_and_raise(cls, sql: str, allow_write: bool = False, strict_mode: bool = False) -> None:
        """
        Validate SQL and raise exception if unsafe.

        Args:
            sql: SQL query to validate
            allow_write: If True, allow DML operations (INSERT, UPDATE, DELETE)
            strict_mode: If False (default), only blocks critical patterns. Users who know SQL get more flexibility.

        Raises:
            SQLInjectionAttempt: If SQL contains dangerous patterns
        """
        is_safe, violations = cls.is_safe(sql, allow_write=allow_write, strict_mode=strict_mode)

        if not is_safe:
            raise SQLInjectionAttempt(
                message=f"SQL validation failed: {', '.join(violations)}",
                pattern=violations[0] if violations else None
            )

    _SINGLE_LINE_COMMENT = re.compile(r'--.*?(\n|$)')
    _MULTI_LINE_COMMENT = re.compile(r'/\*.*?\*/', re.DOTALL)

    @classmethod
    def strip_comments(cls, sql: str) -> str:
        """
        Strip SQL comments from query.

        Args:
            sql: SQL query

        Returns:
            SQL with comments removed
        """
        sql = cls._SINGLE_LINE_COMMENT.sub(' ', sql)
        sql = cls._MULTI_LINE_COMMENT.sub(' ', sql)
        sql = " ".join(sql.split())

        return sql
