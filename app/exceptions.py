"""Custom exception classes for the Natural Language SQL Engine."""

from typing import Optional, Dict, Any


class NLSQLException(Exception):
    """Base exception for all Natural Language SQL Engine errors."""

    def __init__(
        self,
        message: str,
        code: str = "INTERNAL_ERROR",
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.code = code
        self.details = details or {}
        super().__init__(self.message)


# Database Exceptions
class DatabaseConnectionError(NLSQLException):
    """Raised when database connection fails."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code="DATABASE_CONNECTION_ERROR", details=details)


class DatabaseNotFoundError(NLSQLException):
    """Raised when requested database is not found."""

    def __init__(self, database_id: str):
        super().__init__(
            f"Database with ID '{database_id}' not found",
            code="DATABASE_NOT_FOUND",
            details={"database_id": database_id}
        )


class DatabaseConfigurationError(NLSQLException):
    """Raised when database configuration is invalid."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code="DATABASE_CONFIGURATION_ERROR", details=details)


# Query Validation Exceptions
class QueryValidationError(NLSQLException):
    """Base exception for query validation errors."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code="QUERY_VALIDATION_ERROR", details=details)


class SQLInjectionAttempt(QueryValidationError):
    """Raised when SQL injection is detected."""

    def __init__(self, message: str, pattern: Optional[str] = None):
        details = {"pattern": pattern} if pattern else {}
        super().__init__(
            message,
            details={"code": "SQL_INJECTION_ATTEMPT", **details}
        )
        self.code = "SQL_INJECTION_ATTEMPT"


class ReadOnlyViolation(QueryValidationError):
    """Raised when non-SELECT query is attempted in read-only mode."""

    def __init__(self, detected_operation: str):
        super().__init__(
            f"Only SELECT queries are allowed. Detected: {detected_operation}",
            details={"detected_operation": detected_operation}
        )
        self.code = "READ_ONLY_VIOLATION"


class QuerySyntaxError(QueryValidationError):
    """Raised when SQL syntax is invalid."""

    def __init__(self, message: str, sql: Optional[str] = None):
        details = {"sql": sql[:200] if sql else None}
        super().__init__(message, details=details)
        self.code = "QUERY_SYNTAX_ERROR"


# Query Execution Exceptions
class QueryExecutionError(NLSQLException):
    """Base exception for query execution errors."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code="QUERY_EXECUTION_ERROR", details=details)


class QueryTimeoutError(QueryExecutionError):
    """Raised when query execution exceeds timeout."""

    def __init__(self, timeout_seconds: int):
        super().__init__(
            f"Query execution exceeded timeout of {timeout_seconds} seconds",
            details={"timeout_seconds": timeout_seconds}
        )
        self.code = "QUERY_TIMEOUT"


class ResultLimitExceededError(QueryExecutionError):
    """Raised when query results exceed maximum limit."""

    def __init__(self, row_count: int, max_limit: int):
        super().__init__(
            f"Query returned {row_count} rows, exceeding maximum limit of {max_limit}",
            details={"row_count": row_count, "max_limit": max_limit}
        )
        self.code = "RESULT_LIMIT_EXCEEDED"


# AI API Exceptions (Ollama)
class AIAPIError(NLSQLException):
    """Base exception for AI API errors."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code="AI_API_ERROR", details=details)


class AIAPIRateLimitError(AIAPIError):
    """Raised when AI API rate limit is exceeded."""

    def __init__(self, retry_after: Optional[int] = None):
        details = {"retry_after_seconds": retry_after} if retry_after else {}
        super().__init__(
            "AI API rate limit exceeded",
            details=details
        )
        self.code = "AI_RATE_LIMIT"


class AIParseError(AIAPIError):
    """Raised when AI response cannot be parsed."""

    def __init__(self, message: str, response: Optional[str] = None):
        details = {"response": response[:500] if response else None}
        super().__init__(message, details=details)
        self.code = "AI_PARSE_ERROR"


# Schema Introspection Exceptions
class SchemaIntrospectionError(NLSQLException):
    """Base exception for schema introspection errors."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code="SCHEMA_INTROSPECTION_ERROR", details=details)


class TableNotFoundError(SchemaIntrospectionError):
    """Raised when requested table is not found."""

    def __init__(self, table_name: str, database_id: str):
        super().__init__(
            f"Table '{table_name}' not found in database '{database_id}'",
            details={"table_name": table_name, "database_id": database_id}
        )
        self.code = "TABLE_NOT_FOUND"


# Optimization Exceptions
class QueryOptimizationError(NLSQLException):
    """Raised when query optimization fails."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code="QUERY_OPTIMIZATION_ERROR", details=details)


# Cache Exceptions
class CacheError(NLSQLException):
    """Raised when cache operations fail."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code="CACHE_ERROR", details=details)


# Rate Limiting Exceptions
class RateLimitExceeded(NLSQLException):
    """Raised when API rate limit is exceeded."""

    def __init__(self, limit: int, window: str = "minute"):
        super().__init__(
            f"Rate limit of {limit} requests per {window} exceeded",
            details={"limit": limit, "window": window}
        )
        self.code = "RATE_LIMIT_EXCEEDED"
