"""FastAPI dependency injection functions."""

from app.core.database.connection_manager import get_db_manager
# Using Ollama (Local, FREE, No API keys!)
from app.core.ai.ollama_sql_generator import SQLGenerator
from app.core.query.validator import QueryValidator
from app.core.query.executor import QueryExecutor

# Module-level singletons — same pattern as get_db_manager / get_ollama_client.
_sql_generator: SQLGenerator = None
_query_validator: QueryValidator = None
_query_executor: QueryExecutor = None


def get_sql_generator() -> SQLGenerator:
    """Get SQL generator instance (using Ollama - FREE!)."""
    global _sql_generator
    if _sql_generator is None:
        _sql_generator = SQLGenerator()
    return _sql_generator


def get_query_validator() -> QueryValidator:
    """Get query validator instance."""
    global _query_validator
    if _query_validator is None:
        _query_validator = QueryValidator()
    return _query_validator


def get_query_executor() -> QueryExecutor:
    """Get query executor instance."""
    global _query_executor
    if _query_executor is None:
        _query_executor = QueryExecutor()
    return _query_executor
