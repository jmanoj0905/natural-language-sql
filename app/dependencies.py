"""FastAPI dependency injection functions."""

from app.core.database.connection_manager import get_db_manager
# Using Ollama (Local, FREE, No API keys!)
from app.core.ai.ollama_sql_generator import SQLGenerator
from app.core.query.validator import QueryValidator
from app.core.query.executor import QueryExecutor


def get_sql_generator() -> SQLGenerator:
    """Get SQL generator instance (using Ollama - FREE!)."""
    return SQLGenerator()


def get_query_validator() -> QueryValidator:
    """Get query validator instance."""
    return QueryValidator()


def get_query_executor() -> QueryExecutor:
    """Get query executor instance."""
    return QueryExecutor()
