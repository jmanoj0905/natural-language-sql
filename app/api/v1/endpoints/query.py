"""Natural language query endpoints."""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.models.query import (
    NaturalLanguageQueryRequest,
    DirectSQLRequest,
    QueryResponse,
    ExecutionResult,
)
from app.core.database.connection_manager import (
    get_db_manager,
    DatabaseConnectionManager,
)
from app.core.ai.ollama_sql_generator import SQLGenerator
from app.core.query.validator import QueryValidator
from app.core.query.executor import QueryExecutor
from app.dependencies import get_sql_generator, get_query_validator, get_query_executor
from app.exceptions import NLSQLException
from app.utils.logger import get_logger
from app.config import get_settings
from app.api.v1.endpoints.query_management import add_to_history

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
    settings=Depends(get_settings),
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
                "timestamp": datetime.now().isoformat(),
            },
        )

    if not target_db_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "NO_DATABASE_SPECIFIED",
                "message": "No database specified and no default database is set",
                "timestamp": datetime.now().isoformat(),
            },
        )

    if target_db_id not in db_manager.list_databases():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "DATABASE_NOT_FOUND",
                "message": f"Database '{target_db_id}' not found",
                "timestamp": datetime.now().isoformat(),
            },
        )

    try:
        db_config = db_manager.get_database_config(target_db_id)
        registered_dbs = db_manager.list_databases()

        async with db_manager.get_connection(target_db_id) as conn:
            sql, explanation = await sql_generator.generate_sql(
                question=request.question,
                connection=conn,
                db_id=target_db_id,
                read_only=request.options.read_only,
                registered_dbs=registered_dbs,
                provider=request.options.provider,
                model=request.options.model,
                api_key=request.options.api_key,
            )

            logger.info(
                "sql_generated",
                database_id=target_db_id,
                question=request.question[:100],
                sql=sql[:200],
            )

            validated_sql = validator.validate(sql)

            execution_result = None
            if request.options.execute:
                pagination = None
                if request.pagination:
                    pagination = {
                        "offset": request.pagination.offset,
                        "limit": request.pagination.limit,
                    }

                results, exec_time, total_rows = await executor.execute(
                    connection=conn, sql=validated_sql, pagination=pagination
                )

                columns = list(results[0].keys()) if results else []

                has_more = False
                if total_rows and request.pagination:
                    has_more = (request.pagination.offset + len(results)) < total_rows

                execution_result = ExecutionResult(
                    rows=results,
                    row_count=len(results),
                    execution_time_ms=round(exec_time, 2),
                    columns=columns,
                    total_rows=total_rows,
                    offset=request.pagination.offset if request.pagination else None,
                    limit=request.pagination.limit if request.pagination else None,
                    has_more=has_more,
                )

        add_to_history(target_db_id, request.question)

        return QueryResponse(
            success=True,
            question=request.question,
            generated_sql=validated_sql,
            sql_explanation=explanation,
            execution_result=execution_result,
            metadata={
                "database_id": target_db_id,
                "database_nickname": db_config.nickname,
                "ai_model": request.options.model or settings.OLLAMA_MODEL,
                "ai_provider": request.options.provider,
                "timestamp": datetime.now().isoformat(),
                "executed": request.options.execute,
            },
        )

    except NLSQLException as e:
        logger.error(
            "query_failed",
            error=str(e),
            error_code=e.code,
            question=request.question[:100],
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": e.code,
                "message": e.message,
                "details": e.details,
                "timestamp": datetime.now().isoformat(),
            },
        )

    except Exception as e:
        logger.error(
            "query_unexpected_error",
            error=str(e),
            error_type=type(e).__name__,
            question=request.question[:100],
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "INTERNAL_ERROR",
                "message": f"An unexpected error occurred: {str(e)}",
                "timestamp": datetime.now().isoformat(),
            },
        )


@router.post("/sql", response_model=QueryResponse)
async def direct_sql_query(
    request: DirectSQLRequest,
    database_id: Optional[str] = Query(None, description="Database ID to query"),
    db_manager: DatabaseConnectionManager = Depends(get_db_manager),
    validator: QueryValidator = Depends(get_query_validator),
    executor: QueryExecutor = Depends(get_query_executor),
    settings=Depends(get_settings),
) -> QueryResponse:
    """Execute a raw SQL query directly with validation."""
    target_db_id = database_id or db_manager._default_db_id

    if not db_manager.is_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "DATABASE_NOT_CONFIGURED",
                "message": "No database configured",
                "timestamp": datetime.now().isoformat(),
            },
        )

    if not target_db_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "NO_DATABASE_SPECIFIED",
                "message": "No database specified and no default database is set",
                "timestamp": datetime.now().isoformat(),
            },
        )

    if target_db_id not in db_manager.list_databases():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "DATABASE_NOT_FOUND",
                "message": f"Database '{target_db_id}' not found",
                "timestamp": datetime.now().isoformat(),
            },
        )

    try:
        db_config = db_manager.get_database_config(target_db_id)
        validated_sql = validator.validate(request.sql)

        async with db_manager.get_connection(target_db_id) as conn:
            results, exec_time, total_rows = await executor.execute(
                connection=conn, sql=validated_sql
            )

            columns = list(results[0].keys()) if results else []

            execution_result = ExecutionResult(
                rows=results,
                row_count=len(results),
                execution_time_ms=round(exec_time, 2),
                columns=columns,
                total_rows=total_rows,
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
                "source": "direct_sql",
            },
        )

    except NLSQLException as e:
        logger.error("direct_sql_failed", error=str(e), error_code=e.code)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": e.code,
                "message": e.message,
                "details": e.details,
                "timestamp": datetime.now().isoformat(),
            },
        )

    except Exception as e:
        logger.error(
            "direct_sql_unexpected_error", error=str(e), error_type=type(e).__name__
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "INTERNAL_ERROR",
                "message": f"An unexpected error occurred: {str(e)}",
                "timestamp": datetime.now().isoformat(),
            },
        )


class ExplainRequest(BaseModel):
    """Request to get query execution plan."""

    sql: str = Field(..., description="SQL query to explain")


class ExplainResponse(BaseModel):
    """Response with query execution plan."""

    success: bool
    sql: str
    explain_result: List[Dict[str, Any]]
    metadata: Dict[str, Any]


@router.post("/explain", response_model=ExplainResponse)
async def explain_query(
    request: ExplainRequest,
    database_id: Optional[str] = Query(None, description="Database ID to query"),
    db_manager: DatabaseConnectionManager = Depends(get_db_manager),
    validator: QueryValidator = Depends(get_query_validator),
    executor: QueryExecutor = Depends(get_query_executor),
) -> ExplainResponse:
    """Get query execution plan (EXPLAIN) for debugging slow queries."""
    target_db_id = database_id or db_manager._default_db_id

    if not db_manager.is_configured or not target_db_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "DATABASE_NOT_CONFIGURED",
                "message": "No database configured",
            },
        )

    if target_db_id not in db_manager.list_databases():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "DATABASE_NOT_FOUND",
                "message": f"Database '{target_db_id}' not found",
            },
        )

    try:
        validated_sql = validator.validate(request.sql)

        async with db_manager.get_connection(target_db_id) as conn:
            explain_result = await executor.execute_explain(
                connection=conn, sql=validated_sql
            )

        return ExplainResponse(
            success=True,
            sql=validated_sql,
            explain_result=explain_result,
            metadata={
                "database_id": target_db_id,
                "timestamp": datetime.now().isoformat(),
            },
        )

    except NLSQLException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": e.code, "message": e.message},
        )
    except Exception as e:
        logger.error("explain_query_error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "INTERNAL_ERROR", "message": str(e)},
        )


# Keep intent detection for better prompts (but remove multi-step endpoint)
