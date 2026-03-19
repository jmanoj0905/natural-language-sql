"""Tests for app.exceptions — exception hierarchy and attributes."""

from app.exceptions import (
    NLSQLException,
    DatabaseConnectionError,
    DatabaseNotFoundError,
    QueryValidationError,
    SQLInjectionAttempt,
    QuerySyntaxError,
    QueryExecutionError,
    QueryTimeoutError,
    ResultLimitExceededError,
    AIAPIError,
    AIParseError,
)


class TestNLSQLException:
    def test_message_and_code(self):
        e = NLSQLException("boom", code="CUSTOM")
        assert e.message == "boom"
        assert e.code == "CUSTOM"
        assert str(e) == "boom"

    def test_defaults(self):
        e = NLSQLException("x")
        assert e.code == "INTERNAL_ERROR"
        assert e.details == {}

    def test_details(self):
        e = NLSQLException("x", details={"key": "val"})
        assert e.details["key"] == "val"


class TestDatabaseExceptions:
    def test_connection_error(self):
        e = DatabaseConnectionError("can't connect")
        assert e.code == "DATABASE_CONNECTION_ERROR"

    def test_not_found(self):
        e = DatabaseNotFoundError("db-123")
        assert "db-123" in e.message
        assert e.code == "DATABASE_NOT_FOUND"


class TestQueryExceptions:
    def test_validation_error(self):
        e = QueryValidationError("bad sql")
        assert e.code == "QUERY_VALIDATION_ERROR"

    def test_injection_attempt(self):
        e = SQLInjectionAttempt("DROP detected", pattern="DDL operation")
        assert e.code == "SQL_INJECTION_ATTEMPT"
        assert "DDL" in str(e.details)

    def test_syntax_error(self):
        e = QuerySyntaxError("parse fail", sql="SELECTT *")
        assert e.code == "QUERY_SYNTAX_ERROR"
        assert "SELECTT" in str(e.details)

    def test_timeout(self):
        e = QueryTimeoutError(30)
        assert e.code == "QUERY_TIMEOUT"
        assert "30" in e.message

    def test_limit_exceeded(self):
        e = ResultLimitExceededError(5000, 1000)
        assert e.code == "RESULT_LIMIT_EXCEEDED"
        assert "5000" in e.message


class TestAIExceptions:
    def test_api_error(self):
        e = AIAPIError("ollama down")
        assert e.code == "AI_API_ERROR"

    def test_parse_error(self):
        e = AIParseError("no sql", response="garbage text")
        assert e.code == "AI_PARSE_ERROR"
        assert e.details["response"] == "garbage text"

    def test_parse_error_truncates(self):
        e = AIParseError("no sql", response="x" * 600)
        assert len(e.details["response"]) == 500


class TestInheritance:
    def test_all_inherit_from_base(self):
        for exc_cls in [
            DatabaseConnectionError, QueryValidationError, SQLInjectionAttempt,
            QueryExecutionError, QueryTimeoutError, AIAPIError, AIParseError,
        ]:
            assert issubclass(exc_cls, NLSQLException)

    def test_injection_is_validation_error(self):
        assert issubclass(SQLInjectionAttempt, QueryValidationError)

    def test_timeout_is_execution_error(self):
        assert issubclass(QueryTimeoutError, QueryExecutionError)

    def test_parse_is_ai_error(self):
        assert issubclass(AIParseError, AIAPIError)
