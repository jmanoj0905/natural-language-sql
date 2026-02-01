"""Natural language query endpoints."""

from datetime import datetime
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.models.query import (
    NaturalLanguageQueryRequest,
    DirectSQLRequest,
    QueryResponse,
    ExecutionResult,
    ErrorResponse,
    WriteConfirmationRequest
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
    database_id: Optional[str] = Query(None, description="Database ID to query (uses default if not specified)"),
    db_manager: DatabaseConnectionManager = Depends(get_db_manager),
    sql_generator: SQLGenerator = Depends(get_sql_generator),
    validator: QueryValidator = Depends(get_query_validator),
    executor: QueryExecutor = Depends(get_query_executor),
    settings = Depends(get_settings)
) -> QueryResponse:
    """
    Convert natural language question to SQL and optionally execute it.

    This endpoint:
    1. Converts natural language to SQL using Ollama
    2. Validates the generated SQL for safety
    3. Optionally executes the query
    4. Returns results with explanation

    Args:
        request: Natural language query request
        database_id: Optional database ID to query (uses default if not specified)

    Returns:
        QueryResponse: Generated SQL, explanation, and optional results

    Raises:
        HTTPException: If database not configured or processing fails
    """
    # Determine which database to use
    target_db_id = database_id or db_manager._default_db_id

    # Check database is configured
    if not db_manager.is_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "DATABASE_NOT_CONFIGURED",
                "message": "Database connection not configured. Please configure database first.",
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
        # Get database config for metadata
        db_config = db_manager.get_database_config(target_db_id)

        # Check if this is a write operation to add suggestion
        question_lower = request.question.lower()
        write_keywords = ['delete', 'remove', 'drop', 'erase', 'destroy', 'update', 'insert']
        is_write_operation = any(keyword in question_lower for keyword in write_keywords)

        # Step 1: Generate SQL using Ollama with sample data context
        async with db_manager.get_connection(target_db_id) as conn:
            sql, explanation = await sql_generator.generate_sql(
                question=request.question,
                connection=conn,
                include_schema=request.options.include_schema_context,
                read_only=request.options.read_only,
                db_id=target_db_id
            )

            logger.info(
                "sql_generated_from_nl",
                database_id=target_db_id,
                question=request.question[:100],
                sql=sql[:200]
            )

            # Step 2: Validate SQL (pass read_only flag)
            validated_sql = validator.validate(sql, read_only=request.options.read_only)

            # Step 3: Check for DELETE operations and require confirmation
            sql_upper = validated_sql.upper().strip()
            is_delete = sql_upper.startswith('DELETE')
            is_write = any(sql_upper.startswith(op) for op in ['DELETE', 'UPDATE', 'INSERT', 'DROP', 'TRUNCATE', 'ALTER'])

            # Log all write operations
            if is_write:
                logger.warning(
                    "write_operation_generated",
                    database_id=target_db_id,
                    question=request.question[:100],
                    sql_type=sql_upper.split()[0],
                    sql=validated_sql[:200],
                    execute_requested=request.options.execute,
                    confirmed=request.options.confirm_delete if is_delete else None
                )

            # Step 3: Execute query if requested
            execution_result = None
            if request.options.execute:
                results, exec_time = await executor.execute(
                    connection=conn,
                    sql=validated_sql
                )

                # Get column names from first row if available
                columns = list(results[0].keys()) if results else []

                execution_result = ExecutionResult(
                    rows=results,
                    row_count=len(results),
                    execution_time_ms=round(exec_time, 2),
                    columns=columns
                )

                # Log write operation execution
                if is_write:
                    logger.warning(
                        "write_operation_executed",
                        database_id=target_db_id,
                        question=request.question[:100],
                        sql_type=sql_upper.split()[0],
                        sql=validated_sql[:200],
                        affected_rows=len(results),
                        execution_time_ms=round(exec_time, 2),
                        confirmed=request.options.confirm_delete if is_delete else None
                    )

        # Step 4: Build response
        warnings = []

        response = QueryResponse(
            success=True,
            question=request.question,
            generated_sql=validated_sql,
            sql_explanation=explanation,
            execution_result=execution_result,
            warnings=warnings,
            metadata={
                "database_id": target_db_id,
                "database_nickname": db_config.nickname,
                "ai_model": settings.OLLAMA_MODEL,
                "timestamp": datetime.now().isoformat(),
                "executed": request.options.execute,
                "write_operation_detected": is_write_operation,
                "read_only_mode": request.options.read_only
            }
        )

        logger.info(
            "natural_language_query_completed",
            database_id=target_db_id,
            question=request.question[:100],
            executed=request.options.execute,
            row_count=execution_result.row_count if execution_result else 0
        )

        return response

    except NLSQLException as e:
        # Handle known application exceptions
        logger.error(
            "natural_language_query_failed",
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
        # Handle unexpected exceptions
        logger.error(
            "natural_language_query_unexpected_error",
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
    database_id: Optional[str] = Query(None, description="Database ID to query (uses default if not specified)"),
    db_manager: DatabaseConnectionManager = Depends(get_db_manager),
    validator: QueryValidator = Depends(get_query_validator),
    executor: QueryExecutor = Depends(get_query_executor),
    settings = Depends(get_settings)
) -> QueryResponse:
    """
    Execute pre-written SQL query directly with validation.

    This endpoint:
    1. Validates the SQL for safety (SELECT only, no injection)
    2. Executes the query
    3. Returns results

    Args:
        request: Direct SQL query request
        database_id: Optional database ID to query (uses default if not specified)

    Returns:
        QueryResponse: Query results

    Raises:
        HTTPException: If database not configured or validation/execution fails
    """
    # Determine which database to use
    target_db_id = database_id or db_manager._default_db_id

    # Check database is configured
    if not db_manager.is_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "DATABASE_NOT_CONFIGURED",
                "message": "Database connection not configured",
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
        # Get database config for metadata
        db_config = db_manager.get_database_config(target_db_id)

        # Step 1: Validate SQL
        validated_sql = validator.validate(request.sql)

        # Step 2: Execute query
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

        # Step 3: Build response
        response = QueryResponse(
            success=True,
            question="Direct SQL query",
            generated_sql=validated_sql,
            sql_explanation="User-provided SQL query executed directly",
            execution_result=execution_result,
            warnings=[],
            metadata={
                "database_id": target_db_id,
                "database_nickname": db_config.nickname,
                "timestamp": datetime.now().isoformat(),
                "executed": True,
                "source": "direct_sql"
            }
        )

        logger.info(
            "direct_sql_query_completed",
            database_id=target_db_id,
            sql=validated_sql[:200],
            row_count=execution_result.row_count
        )

        return response

    except NLSQLException as e:
        logger.error(
            "direct_sql_query_failed",
            error=str(e),
            error_code=e.code,
            sql=request.sql[:200]
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
            "direct_sql_query_unexpected_error",
            error=str(e),
            error_type=type(e).__name__,
            sql=request.sql[:200]
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "INTERNAL_ERROR",
                "message": f"An unexpected error occurred: {str(e)}",
                "timestamp": datetime.now().isoformat()
            }
        )


@router.post("/write/preview")
async def preview_write_operation(
    request: NaturalLanguageQueryRequest,
    database_id: Optional[str] = Query(None, description="Database ID to query (uses default if not specified)"),
    db_manager: DatabaseConnectionManager = Depends(get_db_manager)
) -> Dict[str, Any]:
    """
    Preview a write operation before execution.

    Returns matching records and cascade impact.
    Does NOT execute - requires separate confirmation.

    Args:
        request: Natural language query request
        database_id: Optional database ID to query (uses default if not specified)

    Returns:
        Preview information with matches and impact analysis

    Raises:
        HTTPException: If database not found or processing fails
    """
    target_db_id = database_id or db_manager._default_db_id

    # Validate database connection
    if not target_db_id or target_db_id not in db_manager.list_databases():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "DATABASE_NOT_FOUND",
                "message": "Database not found",
                "timestamp": datetime.now().isoformat()
            }
        )

    try:
        from app.core.query.write_operation_handler import WriteOperationHandler
        handler = WriteOperationHandler()

        async with db_manager.get_connection(target_db_id) as conn:
            # Check if it's a batch operation (multiple users)
            if any(keyword in request.question.lower() for keyword in ['all', 'inactive', 'batch', 'multiple']):
                result = await handler.handle_batch_delete_users(request.question, conn)
            else:
                result = await handler.handle_delete_user(request.question, conn)

        logger.info(
            "write_preview_generated",
            database_id=target_db_id,
            question=request.question[:100],
            phase=result.get("phase"),
            matches_count=len(result.get("matches", []))
        )

        return result

    except Exception as e:
        logger.error(
            "write_preview_failed",
            error=str(e),
            question=request.question[:100]
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "PREVIEW_FAILED",
                "message": f"Failed to preview write operation: {str(e)}",
                "timestamp": datetime.now().isoformat()
            }
        )


@router.post("/write/execute")
async def execute_confirmed_write_operation(
    request: WriteConfirmationRequest,
    database_id: Optional[str] = Query(None, description="Database ID (uses default if not specified)"),
    db_manager: DatabaseConnectionManager = Depends(get_db_manager)
) -> Dict[str, Any]:
    """
    Execute a confirmed write operation.

    Requires explicit user_id and confirmation=true.

    Args:
        request: Write confirmation request with user_id and confirmation flag
        database_id: Optional database ID

    Returns:
        Execution result with success status

    Raises:
        HTTPException: If database not found or execution fails
    """
    target_db_id = database_id or db_manager._default_db_id

    if not target_db_id or target_db_id not in db_manager.list_databases():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "DATABASE_NOT_FOUND",
                "message": "Database not found",
                "timestamp": datetime.now().isoformat()
            }
        )

    try:
        from app.core.query.write_operation_handler import WriteOperationHandler
        handler = WriteOperationHandler()

        async with db_manager.get_connection(target_db_id) as conn:
            async with conn.begin():  # Transaction
                result = await handler.execute_delete_user(
                    user_id=request.user_id,
                    connection=conn,
                    performed_by="api_user"
                )

                logger.info(
                    "write_operation_executed",
                    database_id=target_db_id,
                    user_id=request.user_id,
                    operation_type=request.operation_type,
                    deleted_count=result.get("deleted_count", 0)
                )

                return {
                    "success": True,
                    "user_id": request.user_id,
                    "deleted_count": result["deleted_count"],
                    "cascade_impact": result["cascade_impact"],
                    "message": f"User {request.user_id} and all related records deleted successfully",
                    "audit_logged": result["audit_logged"],
                    "timestamp": datetime.now().isoformat()
                }

    except Exception as e:
        logger.error(
            "write_operation_failed",
            error=str(e),
            user_id=request.user_id,
            operation_type=request.operation_type
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "WRITE_OPERATION_FAILED",
                "message": f"Delete operation failed: {str(e)}",
                "timestamp": datetime.now().isoformat()
            }
        )
