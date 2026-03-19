"""SSE streaming endpoint for real-time query progress."""

import asyncio
import json
import time
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, Query
from starlette.responses import StreamingResponse

from app.models.query import (
    NaturalLanguageQueryRequest,
    QueryResponse,
    ExecutionResult,
)
from app.core.database.connection_manager import get_db_manager, DatabaseConnectionManager
from app.core.ai.ollama_client import get_ollama_client
from app.core.ai.prompts import (
    build_sql_generation_prompt,
    extract_sql_from_response,
    extract_explanation_from_response,
    build_explanation,
)
from app.core.database.schema_inspector import SchemaInspector
from app.core.query.validator import QueryValidator
from app.core.query.executor import QueryExecutor
from app.dependencies import get_query_validator, get_query_executor
from app.exceptions import NLSQLException
from app.config import get_settings
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/query", tags=["query"])


def sse_event(event: str, data: dict) -> str:
    """Format a Server-Sent Event."""
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


def _parse_db_ids(
    database_ids: Optional[str],
    database_id: Optional[str],
    db_manager: DatabaseConnectionManager,
) -> List[str]:
    """Resolve the list of database IDs from query parameters."""
    if database_ids:
        return [x.strip() for x in database_ids.split(",") if x.strip()]
    if database_id:
        return [database_id]
    if db_manager._default_db_id:
        return [db_manager._default_db_id]
    return []


@router.post("/natural/stream")
async def natural_language_query_stream(
    request: NaturalLanguageQueryRequest,
    database_id: Optional[str] = Query(None, description="Database ID to query"),
    database_ids: Optional[str] = Query(None, description="Comma-separated database IDs for multi-DB fan-out"),
    db_manager: DatabaseConnectionManager = Depends(get_db_manager),
    validator: QueryValidator = Depends(get_query_validator),
    executor: QueryExecutor = Depends(get_query_executor),
    settings=Depends(get_settings),
):
    """
    Stream query progress via Server-Sent Events.

    Same request body as /query/natural but returns text/event-stream
    with real-time progress events for each pipeline stage.

    Supports multi-DB fan-out: pass database_ids=id1,id2 to execute
    the same generated SQL against multiple databases of the same type.
    """
    ids = _parse_db_ids(database_ids, database_id, db_manager)

    # --- Pre-stream validation ---
    if not db_manager.is_configured:
        async def error_stream():
            yield sse_event("error", {
                "stage": "connect",
                "error": "No database configured. Please add a database connection first.",
                "code": "DATABASE_NOT_CONFIGURED",
            })
        return StreamingResponse(error_stream(), media_type="text/event-stream")

    if not ids:
        async def error_stream():
            yield sse_event("error", {
                "stage": "connect",
                "error": "No database specified and no default database is set",
                "code": "NO_DATABASE_SPECIFIED",
            })
        return StreamingResponse(error_stream(), media_type="text/event-stream")

    known_ids = set(db_manager.list_databases())
    missing = [i for i in ids if i not in known_ids]
    if missing:
        async def error_stream():
            yield sse_event("error", {
                "stage": "connect",
                "error": f"Database(s) not found: {', '.join(missing)}",
                "code": "DATABASE_NOT_FOUND",
            })
        return StreamingResponse(error_stream(), media_type="text/event-stream")

    # All selected DBs must share the same db_type
    db_types = {db_manager.get_database_config(i).db_type for i in ids}
    if len(db_types) > 1:
        async def error_stream():
            yield sse_event("error", {
                "stage": "connect",
                "error": "Cannot fan out across mixed database types. All selected databases must be the same type.",
                "code": "MIXED_DB_TYPES",
            })
        return StreamingResponse(error_stream(), media_type="text/event-stream")

    multi_db = len(ids) > 1

    # ---- Single-DB fast path ----
    if not multi_db:
        async def single_db_generator():
            target_db_id = ids[0]
            try:
                db_config = db_manager.get_database_config(target_db_id)
                schema_inspector = SchemaInspector()
                ai_client = get_ollama_client()

                # --- Stage 1: Connect ---
                yield sse_event("progress", {"stage": "connect", "status": "in_progress"})
                t0 = time.perf_counter()
                try:
                    conn_cm = db_manager.get_connection(target_db_id)
                    conn = await conn_cm.__aenter__()
                except Exception as e:
                    yield sse_event("error", {
                        "stage": "connect",
                        "error": str(e),
                        "code": "DATABASE_CONNECTION_ERROR",
                    })
                    return
                elapsed = round((time.perf_counter() - t0) * 1000)
                yield sse_event("progress", {
                    "stage": "connect",
                    "status": "completed",
                    "duration_ms": elapsed,
                })

                try:
                    # --- Stage 2: Schema ---
                    yield sse_event("progress", {"stage": "schema", "status": "in_progress"})
                    t0 = time.perf_counter()
                    schema_context = await schema_inspector.get_schema_summary(
                        conn,
                        db_id=target_db_id,
                        max_tables=50,
                        include_sample_data=True,
                        sample_rows=3,
                    )
                    elapsed = round((time.perf_counter() - t0) * 1000)
                    yield sse_event("progress", {
                        "stage": "schema",
                        "status": "completed",
                        "duration_ms": elapsed,
                        "message": "Schema loaded",
                    })

                    # --- Stage 3: AI Generate ---
                    yield sse_event("progress", {
                        "stage": "ai",
                        "status": "in_progress",
                        "message": "Waiting for Ollama...",
                    })
                    t0 = time.perf_counter()

                    raw_db_type = (db_config.db_type or "postgresql").lower()
                    database_type = "MySQL" if raw_db_type == "mysql" else "PostgreSQL"
                    prompt = build_sql_generation_prompt(
                        question=request.question,
                        schema_context=schema_context,
                        database_type=database_type,
                        max_limit=settings.MAX_QUERY_RESULTS,
                        read_only=request.options.read_only,
                    )
                    response_text = await ai_client.generate_content(prompt)
                    logger.debug("ollama_raw_response", response=response_text)
                    sql = extract_sql_from_response(response_text)
                    explanation = extract_explanation_from_response(response_text)
                    if not explanation and sql:
                        explanation = build_explanation(request.question, sql)

                    if not sql:
                        logger.error("sql_extraction_failed", response=response_text)
                        yield sse_event("error", {
                            "stage": "ai",
                            "error": "Failed to extract SQL from AI response",
                            "raw_response": response_text[:500],
                            "code": "AI_PARSE_ERROR",
                        })
                        return

                    elapsed = round((time.perf_counter() - t0) * 1000)
                    yield sse_event("progress", {
                        "stage": "ai",
                        "status": "completed",
                        "duration_ms": elapsed,
                    })

                    # --- Stage 4: Validate ---
                    yield sse_event("progress", {"stage": "validate", "status": "in_progress"})
                    t0 = time.perf_counter()
                    validated_sql = validator.validate(
                        sql,
                        read_only=request.options.read_only,
                        original_question=request.question,
                    )
                    elapsed = round((time.perf_counter() - t0) * 1000)
                    yield sse_event("progress", {
                        "stage": "validate",
                        "status": "completed",
                        "duration_ms": elapsed,
                    })

                    # --- Stage 5: Execute ---
                    execution_result = None
                    if request.options.execute:
                        yield sse_event("progress", {"stage": "execute", "status": "in_progress"})
                        t0 = time.perf_counter()
                        results, exec_time = await executor.execute(
                            connection=conn, sql=validated_sql
                        )
                        columns = list(results[0].keys()) if results else []
                        execution_result = ExecutionResult(
                            rows=results,
                            row_count=len(results),
                            execution_time_ms=round(exec_time, 2),
                            columns=columns,
                        )
                        elapsed = round((time.perf_counter() - t0) * 1000)
                        yield sse_event("progress", {
                            "stage": "execute",
                            "status": "completed",
                            "duration_ms": elapsed,
                        })
                    else:
                        yield sse_event("progress", {"stage": "execute", "status": "skipped"})

                    # --- Final result ---
                    query_response = QueryResponse(
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
                        },
                    )
                    yield sse_event("result", query_response.model_dump(mode="json"))

                finally:
                    await conn_cm.__aexit__(None, None, None)

            except NLSQLException as e:
                logger.error("stream_query_failed", error=str(e), error_code=e.code)
                yield sse_event("error", {
                    "stage": "unknown",
                    "error": e.message,
                    "code": e.code,
                })
            except Exception as e:
                logger.error("stream_query_unexpected_error", error=str(e), error_type=type(e).__name__)
                yield sse_event("error", {
                    "stage": "unknown",
                    "error": str(e),
                    "code": "INTERNAL_ERROR",
                })

        return StreamingResponse(
            single_db_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    # ---- Multi-DB fan-out path ----
    async def multi_db_generator():
        db_configs = {i: db_manager.get_database_config(i) for i in ids}
        nicknames = {i: cfg.nickname or i for i, cfg in db_configs.items()}
        schema_inspector = SchemaInspector()
        ai_client = get_ollama_client()
        open_connections = {}  # db_id -> (context_manager, connection)

        try:
            # --- Stage 1: Connect to all databases ---
            yield sse_event("progress", {
                "stage": "connect",
                "status": "in_progress",
                "message": f"Connecting to {len(ids)} databases...",
            })
            t0 = time.perf_counter()

            for db_id in ids:
                try:
                    conn_cm = db_manager.get_connection(db_id)
                    conn = await conn_cm.__aenter__()
                    open_connections[db_id] = (conn_cm, conn)
                except Exception as e:
                    logger.error("multi_db_connect_failed", db_id=db_id, error=str(e))
                    # Close all already-opened connections
                    for _, (cm, _) in open_connections.items():
                        try:
                            await cm.__aexit__(None, None, None)
                        except Exception:
                            pass
                    yield sse_event("error", {
                        "stage": "connect",
                        "error": f"Failed to connect to '{nicknames[db_id]}': {e}",
                        "code": "DATABASE_CONNECTION_ERROR",
                    })
                    return

            elapsed = round((time.perf_counter() - t0) * 1000)
            yield sse_event("progress", {
                "stage": "connect",
                "status": "completed",
                "duration_ms": elapsed,
                "message": f"Connected to {len(ids)} databases",
            })

            # --- Stage 2: Schema from first database ---
            primary_id = ids[0]
            primary_config = db_configs[primary_id]
            _, primary_conn = open_connections[primary_id]

            yield sse_event("progress", {"stage": "schema", "status": "in_progress"})
            t0 = time.perf_counter()
            schema_context = await schema_inspector.get_schema_summary(
                primary_conn,
                db_id=primary_id,
                max_tables=50,
                include_sample_data=True,
                sample_rows=3,
            )
            elapsed = round((time.perf_counter() - t0) * 1000)
            yield sse_event("progress", {
                "stage": "schema",
                "status": "completed",
                "duration_ms": elapsed,
                "message": f"Schema loaded from {nicknames[primary_id]}",
            })

            # --- Stage 3: AI Generate (once) ---
            yield sse_event("progress", {
                "stage": "ai",
                "status": "in_progress",
                "message": "Waiting for Ollama...",
            })
            t0 = time.perf_counter()

            raw_db_type = (primary_config.db_type or "postgresql").lower()
            database_type = "MySQL" if raw_db_type == "mysql" else "PostgreSQL"
            prompt = build_sql_generation_prompt(
                question=request.question,
                schema_context=schema_context,
                database_type=database_type,
                max_limit=settings.MAX_QUERY_RESULTS,
                read_only=request.options.read_only,
            )
            response_text = await ai_client.generate_content(prompt)
            logger.debug("ollama_raw_response", response=response_text)
            sql = extract_sql_from_response(response_text)
            explanation = extract_explanation_from_response(response_text)
            if not explanation and sql:
                explanation = build_explanation(request.question, sql)

            if not sql:
                logger.error("sql_extraction_failed", response=response_text)
                yield sse_event("error", {
                    "stage": "ai",
                    "error": "Failed to extract SQL from AI response",
                    "raw_response": response_text[:500],
                    "code": "AI_PARSE_ERROR",
                })
                return

            elapsed = round((time.perf_counter() - t0) * 1000)
            yield sse_event("progress", {
                "stage": "ai",
                "status": "completed",
                "duration_ms": elapsed,
            })

            # --- Stage 4: Validate (once) ---
            yield sse_event("progress", {"stage": "validate", "status": "in_progress"})
            t0 = time.perf_counter()
            validated_sql = validator.validate(
                sql,
                read_only=request.options.read_only,
                original_question=request.question,
            )
            elapsed = round((time.perf_counter() - t0) * 1000)
            yield sse_event("progress", {
                "stage": "validate",
                "status": "completed",
                "duration_ms": elapsed,
            })

            # --- Stage 5: Execute across all databases in parallel ---
            execution_result = None
            warnings = []
            if request.options.execute:
                yield sse_event("progress", {
                    "stage": "execute",
                    "status": "in_progress",
                    "message": f"Executing on {len(ids)} databases...",
                })
                t0 = time.perf_counter()

                async def _run_on(db_id):
                    _, conn = open_connections[db_id]
                    return await executor.execute(connection=conn, sql=validated_sql)

                gather_results = await asyncio.gather(
                    *[_run_on(db_id) for db_id in ids],
                    return_exceptions=True,
                )

                merged_rows = []
                total_exec_time = 0.0
                original_columns = []

                for db_id, result in zip(ids, gather_results):
                    if isinstance(result, Exception):
                        warnings.append(f"{nicknames[db_id]}: {result}")
                        logger.warning("multi_db_exec_failed", db_id=db_id, error=str(result))
                    else:
                        rows, exec_time = result
                        total_exec_time = max(total_exec_time, exec_time)
                        if rows and not original_columns:
                            original_columns = list(rows[0].keys())
                        for row in rows:
                            merged_rows.append({"__source_db__": nicknames[db_id], **row})

                if not merged_rows and warnings:
                    # All executions failed
                    yield sse_event("error", {
                        "stage": "execute",
                        "error": "All database executions failed",
                        "details": [str(w) for w in warnings],
                        "code": "MULTI_DB_ALL_FAILED",
                    })
                    return

                columns = (["__source_db__"] + original_columns) if merged_rows else []
                execution_result = ExecutionResult(
                    rows=merged_rows,
                    row_count=len(merged_rows),
                    execution_time_ms=round(total_exec_time, 2),
                    columns=columns,
                )

                elapsed = round((time.perf_counter() - t0) * 1000)
                yield sse_event("progress", {
                    "stage": "execute",
                    "status": "completed",
                    "duration_ms": elapsed,
                    "message": f"Executed on {len(ids) - len(warnings)}/{len(ids)} databases",
                })
            else:
                yield sse_event("progress", {"stage": "execute", "status": "skipped"})

            # --- Final result ---
            query_response = QueryResponse(
                success=True,
                question=request.question,
                generated_sql=validated_sql,
                sql_explanation=explanation,
                execution_result=execution_result,
                warnings=[str(w) for w in warnings],
                metadata={
                    "database_ids": ids,
                    "database_nicknames": [nicknames[i] for i in ids],
                    "multi_db": True,
                    "ai_model": settings.OLLAMA_MODEL,
                    "timestamp": datetime.now().isoformat(),
                    "executed": request.options.execute,
                },
            )
            yield sse_event("result", query_response.model_dump(mode="json"))

        except NLSQLException as e:
            logger.error("stream_multi_query_failed", error=str(e), error_code=e.code)
            yield sse_event("error", {
                "stage": "unknown",
                "error": e.message,
                "code": e.code,
            })
        except Exception as e:
            logger.error("stream_multi_query_unexpected_error", error=str(e), error_type=type(e).__name__)
            yield sse_event("error", {
                "stage": "unknown",
                "error": str(e),
                "code": "INTERNAL_ERROR",
            })
        finally:
            # Close all open connections
            for db_id, (cm, _) in open_connections.items():
                try:
                    await cm.__aexit__(None, None, None)
                except Exception:
                    pass

    return StreamingResponse(
        multi_db_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
