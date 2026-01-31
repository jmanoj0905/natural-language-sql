"""Schema introspection endpoints."""

from fastapi import APIRouter, HTTPException, Query, status
from typing import List, Dict, Any, Optional

from app.core.database.connection_manager import get_db_manager
from app.core.database.schema_inspector import SchemaInspector
from app.utils.logger import get_logger
from sqlalchemy import text

logger = get_logger(__name__)
router = APIRouter(prefix="/schema", tags=["schema"])

# Initialize schema inspector
schema_inspector = SchemaInspector()


@router.get("", response_model=Dict[str, Any])
async def get_database_schema(
    database_id: Optional[str] = Query(None, description="Database ID (uses default if not specified)")
):
    """
    Get the complete database schema for specified or default database.

    Returns information about all tables and their columns.
    """
    db_manager = get_db_manager()

    # Determine which database to use
    target_db_id = database_id or db_manager._default_db_id

    if not db_manager.is_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "message": "Database not configured",
                "code": "DATABASE_NOT_CONFIGURED"
            }
        )

    if not target_db_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": "No database specified and no default database is set",
                "code": "NO_DATABASE_SPECIFIED"
            }
        )

    if target_db_id not in db_manager.list_databases():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "message": f"Database '{target_db_id}' not found",
                "code": "DATABASE_NOT_FOUND"
            }
        )

    try:
        async with db_manager.get_connection(target_db_id) as conn:
            # Get all tables info with caching
            tables_info = await schema_inspector.get_schema_for_database(
                conn,
                target_db_id,
                max_tables=50
            )

            # Also get primary keys for each table
            enhanced_tables = []
            for table in tables_info:
                table_name = table["name"]

                # Query for primary keys
                pk_query = """
                    SELECT a.attname
                    FROM pg_index i
                    JOIN pg_attribute a ON a.attrelid = i.indrelid
                        AND a.attnum = ANY(i.indkey)
                    WHERE i.indrelid = :table_name::regclass
                        AND i.indisprimary
                """

                try:
                    result = await conn.execute(
                        text(pk_query),
                        {"table_name": table_name}
                    )
                    primary_keys = [row[0] for row in result.fetchall()]

                    # Mark primary key columns
                    for col in table["columns"]:
                        col["primary_key"] = col["name"] in primary_keys

                except Exception as e:
                    logger.warning(
                        "failed_to_get_primary_keys",
                        table=table_name,
                        error=str(e)
                    )
                    # Continue without primary key info
                    for col in table["columns"]:
                        col["primary_key"] = False

                enhanced_tables.append(table)

            logger.info(
                "schema_retrieved",
                database_id=target_db_id,
                table_count=len(enhanced_tables)
            )

            return {
                "success": True,
                "database_id": target_db_id,
                "tables": enhanced_tables,
                "table_count": len(enhanced_tables)
            }

    except Exception as e:
        logger.error(
            "schema_retrieval_failed",
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "message": f"Failed to retrieve schema: {str(e)}",
                "code": "SCHEMA_RETRIEVAL_FAILED"
            }
        )


@router.get("/all", response_model=Dict[str, Any])
async def get_all_schemas():
    """
    Get schemas for all registered databases.

    Returns schema information for each database.
    """
    db_manager = get_db_manager()
    schemas = {}

    for db_id in db_manager.list_databases():
        try:
            async with db_manager.get_connection(db_id) as conn:
                schema = await schema_inspector.get_schema_for_database(conn, db_id, max_tables=50)
                schemas[db_id] = schema
        except Exception as e:
            logger.error("failed_to_get_schema", database_id=db_id, error=str(e))
            schemas[db_id] = {"error": str(e)}

    return {
        "success": True,
        "schemas": schemas
    }


@router.get("/summary", response_model=Dict[str, Any])
async def get_schema_summary(
    database_id: Optional[str] = Query(None, description="Database ID (uses default if not specified)")
):
    """
    Get a concise schema summary for AI context.

    Returns a text summary of the database schema.
    """
    db_manager = get_db_manager()

    # Determine which database to use
    target_db_id = database_id or db_manager._default_db_id

    if not db_manager.is_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "message": "Database not configured",
                "code": "DATABASE_NOT_CONFIGURED"
            }
        )

    if not target_db_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": "No database specified and no default database is set",
                "code": "NO_DATABASE_SPECIFIED"
            }
        )

    if target_db_id not in db_manager.list_databases():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "message": f"Database '{target_db_id}' not found",
                "code": "DATABASE_NOT_FOUND"
            }
        )

    try:
        async with db_manager.get_connection(target_db_id) as conn:
            summary = await schema_inspector.get_schema_summary(conn, target_db_id)

            return {
                "success": True,
                "database_id": target_db_id,
                "summary": summary
            }

    except Exception as e:
        logger.error(
            "schema_summary_failed",
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "message": f"Failed to get schema summary: {str(e)}",
                "code": "SCHEMA_SUMMARY_FAILED"
            }
        )


@router.post("/cache/clear")
async def clear_schema_cache():
    """
    Clear the schema cache.

    Forces fresh retrieval of schema information on next request.
    """
    schema_inspector.clear_cache()

    logger.info("schema_cache_cleared_via_api")

    return {
        "success": True,
        "message": "Schema cache cleared successfully"
    }
