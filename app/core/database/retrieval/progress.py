"""Progress event types for retrieval pipeline observability."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Awaitable, Callable, Optional


@dataclass(frozen=True)
class ProgressEvent:
    stage: str
    status: str  # "in_progress" | "completed" | "skipped" | "error"
    message: str = ""
    duration_ms: Optional[int] = None
    meta: Optional[dict] = None


ProgressEmitter = Callable[[ProgressEvent], Awaitable[None]]
