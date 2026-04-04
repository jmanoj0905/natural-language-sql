"""Pydantic models for query requests and responses."""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class QueryOptions(BaseModel):
    """Options for query execution."""

    execute: bool = Field(
        default=True, description="Whether to execute the query after generation"
    )
    read_only: bool = Field(
        default=True,
        description="If True, only SELECT queries allowed. The UI checkbox controls this.",
    )


class PaginationParams(BaseModel):
    """Pagination parameters for query results."""

    offset: int = Field(default=0, ge=0, description="Number of rows to skip")
    limit: int = Field(default=100, ge=1, le=1000, description="Max rows to return")


class NaturalLanguageQueryRequest(BaseModel):
    """Request to convert natural language to SQL."""

    question: str = Field(
        ...,
        description="Natural language question to convert to SQL",
        min_length=3,
        max_length=1000,
    )
    options: QueryOptions = Field(
        default_factory=QueryOptions, description="Query execution options"
    )
    pagination: Optional[PaginationParams] = Field(
        default=None, description="Pagination parameters for results"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "question": "Show me all users who signed up in the last 7 days",
                "options": {"execute": True, "read_only": True},
                "pagination": {"offset": 0, "limit": 50},
            }
        }


class ExecutionResult(BaseModel):
    """Query execution results."""

    rows: List[Dict[str, Any]] = Field(..., description="Result rows as dictionaries")
    row_count: int = Field(..., description="Number of rows returned")
    execution_time_ms: float = Field(
        ..., description="Query execution time in milliseconds"
    )
    columns: List[str] = Field(
        default_factory=list, description="Column names in result set"
    )
    total_rows: Optional[int] = Field(
        default=None, description="Total rows available (for pagination)"
    )
    offset: Optional[int] = Field(default=None, description="Current offset")
    limit: Optional[int] = Field(default=None, description="Current limit")
    has_more: bool = Field(default=False, description="Whether more rows are available")


class QueryResponse(BaseModel):
    """Response for natural language query."""

    success: bool = Field(..., description="Whether the request was successful")
    question: str = Field(..., description="Original natural language question")
    generated_sql: str = Field(default="", description="Generated SQL query")
    sql_explanation: str = Field(default="", description="Explanation of the SQL query")
    execution_result: Optional[ExecutionResult] = Field(
        None, description="Query execution results (if executed)"
    )
    warnings: List[str] = Field(
        default_factory=list, description="Any warnings about the query"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "question": "Show me all users who signed up in the last 7 days",
                "generated_sql": "SELECT * FROM users WHERE created_at >= NOW() - INTERVAL '7 days' LIMIT 100;",
                "sql_explanation": "This query retrieves all user records created within the past 7 days.",
                "execution_result": {
                    "rows": [
                        {"id": 1, "username": "john_doe", "created_at": "2026-01-23"}
                    ],
                    "row_count": 1,
                    "execution_time_ms": 23.5,
                    "columns": ["id", "username", "created_at"],
                },
                "warnings": [],
                "metadata": {
                    "ai_model": "llama3.2",
                    "timestamp": "2026-01-29T10:30:00Z",
                },
            }
        }


class DirectSQLRequest(BaseModel):
    """Request to execute pre-written SQL directly."""

    sql: str = Field(
        ..., description="SQL query to execute", min_length=10, max_length=5000
    )

    class Config:
        json_schema_extra = {"example": {"sql": "SELECT * FROM users WHERE id = 123;"}}


class ErrorResponse(BaseModel):
    """Error response model."""

    success: bool = Field(default=False, description="Always false for errors")
    error: Dict[str, Any] = Field(..., description="Error details")


# Multi-step query models


class QueryStepModel(BaseModel):
    """A single step in a multi-step query."""

    step: int = Field(..., description="Step number")
    question: str = Field(..., description="Natural language question for this step")
    database_id: Optional[str] = Field(None, description="Database ID for this step")
    database_nickname: Optional[str] = Field(None, description="Database nickname")
    generated_sql: Optional[str] = Field(
        None, description="Generated SQL for this step"
    )
    action: str = Field(default="read", description="Action type: read or write")
    status: str = Field(
        default="pending",
        description="Status: pending, generated, executing, completed, error",
    )


class QueryPlanRequest(BaseModel):
    """Request to create a query plan from natural language."""

    question: str = Field(
        ..., description="Natural language question", min_length=3, max_length=1000
    )
    database_ids: Optional[str] = Field(
        None, description="Comma-separated database IDs"
    )


class QueryPlanResponse(BaseModel):
    """Response containing the query plan."""

    success: bool = Field(..., description="Whether the request was successful")
    intent: str = Field(..., description="Detected query intent")
    steps: List[QueryStepModel] = Field(..., description="List of query steps")
    message: Optional[str] = Field(None, description="Additional message")
    suggestions: List[str] = Field(
        default_factory=list, description="Suggestions for breaking up compound queries"
    )
    warning: Optional[str] = Field(None, description="Warning about multi-step query")
