"""Query autocomplete and management endpoints."""

import time
import asyncio
from typing import Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

router = APIRouter(prefix="/query", tags=["query"])


class CancelRequest(BaseModel):
    """Request to cancel an in-progress query."""

    query_id: str = Field(..., description="ID of query to cancel")


class CancelResponse(BaseModel):
    """Response for cancel request."""

    success: bool
    message: str
    query_id: str


class QueryStatusResponse(BaseModel):
    """Response with query status."""

    query_id: str
    status: str
    stage: Optional[str] = None
    progress: Optional[int] = None


class SuggestionResponse(BaseModel):
    """Response with autocomplete suggestions."""

    suggestions: List[str]


_in_progress_queries: Dict[str, dict] = {}
_query_counter = 0
_query_lock = asyncio.Lock()


async def generate_query_id() -> str:
    """Generate a unique query ID."""
    global _query_counter
    async with _query_lock:
        _query_counter += 1
        return f"q_{int(time.time() * 1000)}_{_query_counter}"


def register_query(query_id: str, metadata: dict = None) -> None:
    """Register a query as in-progress."""
    _in_progress_queries[query_id] = {
        "status": "running",
        "stage": "initializing",
        "progress": 0,
        "metadata": metadata or {},
        "started_at": time.time(),
    }


def update_query_progress(query_id: str, stage: str, progress: int) -> None:
    """Update query progress."""
    if query_id in _in_progress_queries:
        _in_progress_queries[query_id]["stage"] = stage
        _in_progress_queries[query_id]["progress"] = progress


def complete_query(query_id: str, status: str = "completed") -> None:
    """Mark a query as completed."""
    if query_id in _in_progress_queries:
        _in_progress_queries[query_id]["status"] = status
        _in_progress_queries[query_id]["progress"] = 100


@router.post("/cancel", response_model=CancelResponse)
async def cancel_query(request: CancelRequest) -> CancelResponse:
    """
    Cancel an in-progress query.

    Note: Cancellation is best-effort. If the query is already executing,
    it will be marked for cancellation and the client should handle the
    partial result.
    """
    if request.query_id not in _in_progress_queries:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "QUERY_NOT_FOUND",
                "message": f"Query '{request.query_id}' not found or already completed",
            },
        )

    _in_progress_queries[request.query_id]["status"] = "cancelled"

    return CancelResponse(
        success=True, message="Query cancellation requested", query_id=request.query_id
    )


@router.get("/status/{query_id}", response_model=QueryStatusResponse)
async def get_query_status(query_id: str) -> QueryStatusResponse:
    """Get the status of an in-progress query."""
    if query_id not in _in_progress_queries:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "QUERY_NOT_FOUND",
                "message": f"Query '{query_id}' not found",
            },
        )

    query_info = _in_progress_queries[query_id]

    return QueryStatusResponse(
        query_id=query_id,
        status=query_info["status"],
        stage=query_info.get("stage"),
        progress=query_info.get("progress"),
    )


# Simple in-memory query history for autocomplete
_query_history: Dict[str, List[str]] = {}


@router.get("/suggestions", response_model=SuggestionResponse)
async def get_suggestions(
    database_id: Optional[str] = Query(None, description="Database ID for suggestions"),
    prefix: str = Query("", description="Prefix to match for autocomplete"),
    limit: int = Query(5, ge=1, le=20, description="Max suggestions to return"),
) -> SuggestionResponse:
    """
    Get autocomplete suggestions based on query history.

    Returns recent queries that match the given prefix for the database.
    """
    key = database_id or "default"

    if not prefix:
        suggestions = _query_history.get(key, [])[:limit]
    else:
        suggestions = [
            q for q in _query_history.get(key, []) if prefix.lower() in q.lower()
        ][:limit]

    return SuggestionResponse(suggestions=suggestions)


def add_to_history(database_id: Optional[str], question: str) -> None:
    """Add a query to history for autocomplete."""
    key = database_id or "default"

    if key not in _query_history:
        _query_history[key] = []

    if question not in _query_history[key]:
        _query_history[key].insert(0, question)
        _query_history[key] = _query_history[key][:50]
