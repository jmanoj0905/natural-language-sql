"""Natural language query endpoints."""

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.models.query import (
    NaturalLanguageQueryRequest,
    DirectSQLRequest,
    QueryResponse,
    ExecutionResult,
)
from app.core.database.connection_manager import get_db_manager, DatabaseConnectionManager
from app.core.ai.ollama_sql_generator import SQLGenerator
from app.core.query.validator import QueryValidator
from app.core.query.executor import QueryExecutor
from app.dependencies import (
    get_sql_generator,
    get_query_validator,
    get_query_executor
)
from app.exceptions import NLSQLException
from app.utils.logger import get_logger
from app.config import get_settings

logger = get_logger(__name__)
router = APIRouter(prefix="/query", tags=["query"])


@router.post("/natural", response_model=QueryResponse)
async def natural_language_query(
    request: NaturalLanguageQueryRequest,
    database_id: Optional[str] = Query(None, description="Database ID to query"),
    db_manager: DatabaseConnectionManager = Depends(get_db_manager),
    sql_generator: SQLGenerator = Depends(get_sql_generator),
    validator: QueryValidator = Depends(get_query_validator),
    executor: QueryExecutor = Depends(get_query_executor),
    settings = Depends(get_settings)
) -> QueryResponse:
    """
    Convert natural language to SQL and optionally execute it.

    Flow: question → schema → Ollama → SQL → validate → execute → results
    """
    target_db_id = database_id or db_manager._default_db_id

    if not db_manager.is_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "DATABASE_NOT_CONFIGURED",
                "message": "No database configured. Please add a database connection first.",
                "timestamp": datetime.now().isoformat()
            }
        )

    if not target_db_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "NO_DATABASE_SPECIFIED",
                "message": "No database specified and no default database is set",
                "timestamp": datetime.now().isoformat()
            }
        )

    if target_db_id not in db_manager.list_databases():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "DATABASE_NOT_FOUND",
                "message": f"Database '{target_db_id}' not found",
                "timestamp": datetime.now().isoformat()
            }
        )

    try:
        db_config = db_manager.get_database_config(target_db_id)

        async with db_manager.get_connection(target_db_id) as conn:
            # 1. Generate SQL via Ollama
            sql, explanation = await sql_generator.generate_sql(
                question=request.question,
                connection=conn,
                db_id=target_db_id,
                read_only=request.options.read_only
            )

            logger.info(
                "sql_generated",
                database_id=target_db_id,
                question=request.question[:100],
                sql=sql[:200]
            )

            # 2. Validate SQL
            validated_sql = validator.validate(sql)

            # 3. Execute if requested
            execution_result = None
            if request.options.execute:
                results, exec_time = await executor.execute(
                    connection=conn,
                    sql=validated_sql
                )

                columns = list(results[0].keys()) if results else []

                execution_result = ExecutionResult(
                    rows=results,
                    row_count=len(results),
                    execution_time_ms=round(exec_time, 2),
                    columns=columns
                )

        return QueryResponse(
            success=True,
            question=request.question,
            generated_sql=validated_sql,
            sql_explanation=explanation,
            execution_result=execution_result,
            metadata={
                "database_id": target_db_id,
                "database_nickname": db_config.nickname,
                "ai_model": settings.OLLAMA_MODEL,
                "timestamp": datetime.now().isoformat(),
                "executed": request.options.execute,
            }
        )

    except NLSQLException as e:
        logger.error(
            "query_failed",
            error=str(e),
            error_code=e.code,
            question=request.question[:100]
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": e.code,
                "message": e.message,
                "details": e.details,
                "timestamp": datetime.now().isoformat()
            }
        )

    except Exception as e:
        logger.error(
            "query_unexpected_error",
            error=str(e),
            error_type=type(e).__name__,
            question=request.question[:100]
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "INTERNAL_ERROR",
                "message": f"An unexpected error occurred: {str(e)}",
                "timestamp": datetime.now().isoformat()
            }
        )


@router.post("/sql", response_model=QueryResponse)
async def direct_sql_query(
    request: DirectSQLRequest,
    database_id: Optional[str] = Query(None, description="Database ID to query"),
    db_manager: DatabaseConnectionManager = Depends(get_db_manager),
    validator: QueryValidator = Depends(get_query_validator),
    executor: QueryExecutor = Depends(get_query_executor),
    settings = Depends(get_settings)
) -> QueryResponse:
    """Execute a raw SQL query directly with validation."""
    target_db_id = database_id or db_manager._default_db_id

    if not db_manager.is_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "DATABASE_NOT_CONFIGURED",
                "message": "No database configured",
                "timestamp": datetime.now().isoformat()
            }
        )

    if not target_db_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "NO_DATABASE_SPECIFIED",
                "message": "No database specified and no default database is set",
                "timestamp": datetime.now().isoformat()
            }
        )

    if target_db_id not in db_manager.list_databases():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "DATABASE_NOT_FOUND",
                "message": f"Database '{target_db_id}' not found",
                "timestamp": datetime.now().isoformat()
            }
        )

    try:
        db_config = db_manager.get_database_config(target_db_id)
        validated_sql = validator.validate(request.sql)

        async with db_manager.get_connection(target_db_id) as conn:
            results, exec_time = await executor.execute(
                connection=conn,
                sql=validated_sql
            )

            columns = list(results[0].keys()) if results else []

            execution_result = ExecutionResult(
                rows=results,
                row_count=len(results),
                execution_time_ms=round(exec_time, 2),
                columns=columns
            )

        return QueryResponse(
            success=True,
            question="Direct SQL query",
            generated_sql=validated_sql,
            sql_explanation="User-provided SQL query executed directly",
            execution_result=execution_result,
            metadata={
                "database_id": target_db_id,
                "database_nickname": db_config.nickname,
                "timestamp": datetime.now().isoformat(),
                "executed": True,
                "source": "direct_sql"
            }
        )

    except NLSQLException as e:
        logger.error("direct_sql_failed", error=str(e), error_code=e.code)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": e.code,
                "message": e.message,
                "details": e.details,
                "timestamp": datetime.now().isoformat()
            }
        )

    except Exception as e:
        logger.error("direct_sql_unexpected_error", error=str(e), error_type=type(e).__name__)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "INTERNAL_ERROR",
                "message": f"An unexpected error occurred: {str(e)}",
                "timestamp": datetime.now().isoformat()
            }
        )
