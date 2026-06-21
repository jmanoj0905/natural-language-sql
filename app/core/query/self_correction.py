"""Provider-agnostic SQL self-correction loop (async generator).

Runs candidate SQL; on an execution error, feeds the error (and, on later
retries, a widened schema) back to the model to regenerate, retrying up to
``max_retries`` times. Yields ``CorrectionEvent`` progress so the SSE endpoint
can stream retries live; the terminal event carries the ``CorrectionOutcome``.
Callers inject ``generate`` (prompt -> raw text), ``execute`` (sql -> result,
raises on failure) and optionally ``schema_for_attempt`` so the same loop serves
the REST endpoint, the SSE endpoint, and the benchmark.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Awaitable, Callable, Optional

from app.core.ai.prompts import build_sql_correction_prompt, extract_sql_from_response
from app.utils.logger import get_logger

logger = get_logger(__name__)

GenerateFn = Callable[[str], Awaitable[str]]
ExecuteFn = Callable[[str], Awaitable[Any]]
TransformFn = Callable[[str], str]
SchemaForAttemptFn = Callable[[int], Awaitable[str]]


@dataclass
class CorrectionOutcome:
    """Final result of a self-correction run."""

    sql: str
    result: Optional[Any]
    succeeded: bool
    retries: int
    error: Optional[str] = None
    errors: list[str] = field(default_factory=list)


@dataclass
class CorrectionEvent:
    """Streamed progress. kind is "retry" (before a regeneration) or "done"."""

    kind: str
    attempt: int = 0
    error: Optional[str] = None
    failed_sql: Optional[str] = None
    outcome: Optional[CorrectionOutcome] = None


async def self_correct_sql(
    *,
    question: str,
    schema_context: str,
    database_type: str,
    read_only: bool,
    initial_sql: str,
    generate: GenerateFn,
    execute: ExecuteFn,
    transform: Optional[TransformFn] = None,
    schema_for_attempt: Optional[SchemaForAttemptFn] = None,
    max_retries: int = 2,
) -> AsyncIterator[CorrectionEvent]:
    """Execute ``initial_sql``; on failure regenerate from the error and retry.

    Yields a ``retry`` event before each regeneration and exactly one terminal
    ``done`` event. On success ``outcome.result`` holds whatever ``execute``
    returned (no second execution).
    """
    errors: list[str] = []
    candidate = initial_sql
    retries = 0

    for attempt in range(max_retries + 1):
        try:
            sql_to_run = transform(candidate) if transform is not None else candidate
            result = await execute(sql_to_run)
            yield CorrectionEvent(
                kind="done",
                outcome=CorrectionOutcome(
                    sql=sql_to_run, result=result, succeeded=True,
                    retries=retries, errors=errors,
                ),
            )
            return
        except Exception as exc:  # noqa: BLE001 — error text is fed back to the model
            err = str(exc)
            errors.append(err)

        if attempt >= max_retries:
            break

        retries += 1
        logger.info(
            "self_correction_retry",
            attempt=retries,
            error=err[:200],
            failed_sql=candidate[:200],
        )
        yield CorrectionEvent(
            kind="retry", attempt=retries, error=err, failed_sql=candidate
        )

        # Widen schema for this retry if a provider was given (retries is the
        # 1-based retry number; the app returns the full dump at retries >= 2).
        attempt_schema = schema_context
        if schema_for_attempt is not None:
            attempt_schema = await schema_for_attempt(retries)

        prompt = build_sql_correction_prompt(
            question=question,
            schema_context=attempt_schema,
            failed_sql=candidate,
            error_message=err,
            database_type=database_type,
            read_only=read_only,
        )
        raw = await generate(prompt)
        corrected = extract_sql_from_response(raw)
        if not corrected:
            errors.append("correction_produced_no_sql")
            break
        candidate = corrected

    yield CorrectionEvent(
        kind="done",
        outcome=CorrectionOutcome(
            sql=candidate, result=None, succeeded=False, retries=retries,
            error=errors[-1] if errors else None, errors=errors,
        ),
    )


async def run_self_correction(**kwargs) -> CorrectionOutcome:
    """Drain ``self_correct_sql`` to its terminal outcome (ignores live events)."""
    outcome: Optional[CorrectionOutcome] = None
    async for event in self_correct_sql(**kwargs):
        if event.kind == "done":
            outcome = event.outcome
    assert outcome is not None  # generator always yields a terminal done event
    return outcome
