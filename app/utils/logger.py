"""Structured logging configuration using structlog."""

import logging
import sys
from pathlib import Path
from typing import Any
import structlog
from structlog.types import FilteringBoundLogger

from app.config import get_settings


def configure_logging() -> FilteringBoundLogger:
    """
    Configure structured logging with structlog.

    Returns:
        FilteringBoundLogger: Configured logger instance
    """
    settings = get_settings()

    # Ensure log directory exists
    log_file_path = Path(settings.LOG_FILE)
    log_file_path.parent.mkdir(parents=True, exist_ok=True)

    # Set log level
    log_level = getattr(logging, settings.LOG_LEVEL, logging.INFO)

    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        level=log_level,
        stream=sys.stdout,
    )

    # Determine processors based on format
    if settings.LOG_FORMAT == "json":
        processors = [
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer(),
        ]
    else:
        # Console-friendly format for development
        processors = [
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S"),
            structlog.dev.ConsoleRenderer(),
        ]

    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Get logger instance
    logger = structlog.get_logger()

    return logger


def get_logger(name: str = __name__) -> FilteringBoundLogger:
    """
    Get a logger instance with the specified name.

    Args:
        name: Logger name (typically __name__ of the module)

    Returns:
        FilteringBoundLogger: Logger instance
    """
    return structlog.get_logger(name)


def log_query_execution(
    logger: FilteringBoundLogger,
    query_id: str,
    database_id: str,
    sql: str,
    execution_time_ms: float,
    row_count: int,
    success: bool = True,
    error: str = None,
    **kwargs: Any
) -> None:
    """
    Log query execution with standardized format.

    Args:
        logger: Logger instance
        query_id: Unique query identifier
        database_id: Database identifier
        sql: SQL query (will be truncated if too long)
        execution_time_ms: Execution time in milliseconds
        row_count: Number of rows returned
        success: Whether query succeeded
        error: Error message if failed
        **kwargs: Additional context to log
    """
    log_data = {
        "event": "query_executed" if success else "query_failed",
        "query_id": query_id,
        "database_id": database_id,
        "sql": sql[:200] + "..." if len(sql) > 200 else sql,
        "execution_time_ms": round(execution_time_ms, 2),
        "row_count": row_count,
        "success": success,
        **kwargs
    }

    if error:
        log_data["error"] = error

    if success:
        logger.info(**log_data)
    else:
        logger.error(**log_data)


def log_ai_request(
    logger: FilteringBoundLogger,
    question: str,
    model: str,
    tokens: int = None,
    success: bool = True,
    error: str = None,
    **kwargs: Any
) -> None:
    """
    Log AI API request with standardized format.

    Args:
        logger: Logger instance
        question: Natural language question
        model: AI model used (e.g., llama3.2)
        tokens: Number of tokens used
        success: Whether request succeeded
        error: Error message if failed
        **kwargs: Additional context to log
    """
    log_data = {
        "event": "ai_request" if success else "ai_request_failed",
        "question": question[:100] + "..." if len(question) > 100 else question,
        "model": model,
        "success": success,
        **kwargs
    }

    if tokens:
        log_data["tokens"] = tokens

    if error:
        log_data["error"] = error

    if success:
        logger.info(**log_data)
    else:
        logger.error(**log_data)


def log_security_event(
    logger: FilteringBoundLogger,
    event_type: str,
    severity: str,
    message: str,
    **kwargs: Any
) -> None:
    """
    Log security-related events.

    Args:
        logger: Logger instance
        event_type: Type of security event (e.g., "sql_injection_attempt")
        severity: Severity level (info, warning, error, critical)
        message: Event message
        **kwargs: Additional context to log
    """
    log_data = {
        "event": "security_event",
        "security_event_type": event_type,
        "message": message,
        **kwargs
    }

    log_method = getattr(logger, severity.lower(), logger.warning)
    log_method(**log_data)


# Initialize logger on module import
logger = configure_logging()
