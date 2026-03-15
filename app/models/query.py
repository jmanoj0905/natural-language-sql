"""Pydantic models for query requests and responses."""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class QueryOptions(BaseModel):
    """Options for query execution."""

    execute: bool = Field(
        default=True,
        description="Whether to execute the query after generation"
    )
    read_only: bool = Field(
        default=True,
        description="If True, only SELECT queries allowed. The UI checkbox controls this."
    )


class NaturalLanguageQueryRequest(BaseModel):
    """Request to convert natural language to SQL."""

    question: str = Field(
        ...,
        description="Natural language question to convert to SQL",
        min_length=3,
        max_length=1000
    )
    options: QueryOptions = Field(
        default_factory=QueryOptions,
        description="Query execution options"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "question": "Show me all users who signed up in the last 7 days",
                "options": {
                    "execute": True,
                    "read_only": True
                }
            }
        }


class ExecutionResult(BaseModel):
    """Query execution results."""

    rows: List[Dict[str, Any]] = Field(
        ...,
        description="Result rows as dictionaries"
    )
    row_count: int = Field(
        ...,
        description="Number of rows returned"
    )
    execution_time_ms: float = Field(
        ...,
        description="Query execution time in milliseconds"
    )
    columns: List[str] = Field(
        default_factory=list,
        description="Column names in result set"
    )


class QueryResponse(BaseModel):
    """Response for natural language query."""

    success: bool = Field(..., description="Whether the request was successful")
    question: str = Field(..., description="Original natural language question")
    generated_sql: str = Field(default="", description="Generated SQL query")
    sql_explanation: str = Field(default="", description="Explanation of the SQL query")
    execution_result: Optional[ExecutionResult] = Field(
        None,
        description="Query execution results (if executed)"
    )
    warnings: List[str] = Field(
        default_factory=list,
        description="Any warnings about the query"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata"
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
                    "columns": ["id", "username", "created_at"]
                },
                "warnings": [],
                "metadata": {
                    "ai_model": "llama3.2",
                    "timestamp": "2026-01-29T10:30:00Z"
                }
            }
        }


class DirectSQLRequest(BaseModel):
    """Request to execute pre-written SQL directly."""

    sql: str = Field(
        ...,
        description="SQL query to execute",
        min_length=10,
        max_length=5000
    )

    class Config:
        json_schema_extra = {
            "example": {
                "sql": "SELECT * FROM users WHERE id = 123;"
            }
        }


class ErrorResponse(BaseModel):
    """Error response model."""

    success: bool = Field(default=False, description="Always false for errors")
    error: Dict[str, Any] = Field(
        ...,
        description="Error details"
    )
