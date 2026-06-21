"""Tests for the provider-agnostic self-correction async generator."""

import pytest

from app.core.query.self_correction import (
    self_correct_sql,
    run_self_correction,
    CorrectionEvent,
)


def _final(events):
    done = [e for e in events if e.kind == "done"]
    assert len(done) == 1
    return done[-1].outcome


@pytest.mark.asyncio
async def test_first_sql_succeeds_no_generate_calls():
    calls = {"generate": 0}

    async def generate(prompt):
        calls["generate"] += 1
        return "```sql\nSELECT 2\n```"

    async def execute(sql):
        return [{"n": 1}]

    events = [
        e async for e in self_correct_sql(
            question="q", schema_context="s", database_type="SQLite",
            read_only=True, initial_sql="SELECT 1",
            generate=generate, execute=execute, max_retries=2,
        )
    ]
    out = _final(events)
    assert out.succeeded is True
    assert out.retries == 0
    assert out.result == [{"n": 1}]
    assert calls["generate"] == 0
    assert not [e for e in events if e.kind == "retry"]


@pytest.mark.asyncio
async def test_retry_emits_event_and_fixes_bad_sql():
    attempts = []

    async def generate(prompt):
        assert "no such column" in prompt  # error fed back
        return "SELECT PetType FROM pets"

    async def execute(sql):
        attempts.append(sql)
        if sql == "SELECT pet_type FROM pets":
            raise RuntimeError("no such column: pet_type")
        return [{"PetType": "dog"}]

    events = [
        e async for e in self_correct_sql(
            question="pets", schema_context="CREATE TABLE pets (PetType text)",
            database_type="SQLite", read_only=True,
            initial_sql="SELECT pet_type FROM pets",
            generate=generate, execute=execute, max_retries=2,
        )
    ]
    retries = [e for e in events if e.kind == "retry"]
    assert len(retries) == 1
    assert retries[0].attempt == 1
    assert retries[0].failed_sql == "SELECT pet_type FROM pets"
    assert "no such column" in retries[0].error

    out = _final(events)
    assert out.succeeded is True
    assert out.retries == 1
    # extract_sql_from_response normalises SQL to end with ";" — accept both forms
    assert out.sql.rstrip(";").strip() == "SELECT PetType FROM pets"
    assert len(attempts) == 2
    assert attempts[0] == "SELECT pet_type FROM pets"
    assert attempts[1].rstrip(";").strip() == "SELECT PetType FROM pets"


@pytest.mark.asyncio
async def test_schema_for_attempt_widens_context():
    seen_schema = []

    async def generate(prompt):
        # capture which schema text the correction prompt used
        seen_schema.append("FULL_DUMP" if "FULL_DUMP" in prompt else "pruned")
        return "SELECT good FROM t"

    async def execute(sql):
        if "bad" in sql:
            raise RuntimeError("no such column: bad")
        return []

    async def schema_for_attempt(n):
        return "FULL_DUMP schema" if n >= 2 else "pruned schema"

    events = [
        e async for e in self_correct_sql(
            question="q", schema_context="pruned schema", database_type="SQLite",
            read_only=True, initial_sql="SELECT bad FROM t",
            generate=generate, execute=execute,
            schema_for_attempt=schema_for_attempt, max_retries=2,
        )
    ]
    out = _final(events)
    assert out.succeeded is True
    assert out.retries == 1          # recovered on first retry (pruned)
    assert seen_schema == ["pruned"]  # widening only kicks in at retry 2


@pytest.mark.asyncio
async def test_exhausts_retries_returns_failure():
    async def generate(prompt):
        return "SELECT still_bad FROM t"

    async def execute(sql):
        raise RuntimeError("no such column: still_bad")

    out = await run_self_correction(
        question="q", schema_context="s", database_type="SQLite",
        read_only=True, initial_sql="SELECT bad FROM t",
        generate=generate, execute=execute, max_retries=2,
    )
    assert out.succeeded is False
    assert out.retries == 2
    assert "still_bad" in out.error
    assert len(out.errors) == 3  # initial + 2 retries


@pytest.mark.asyncio
async def test_transform_applied_before_execute():
    seen = []

    async def generate(prompt):
        return "SELECT 1"

    async def execute(sql):
        seen.append(sql)
        return []

    def transform(sql):
        return sql + " LIMIT 100"

    out = await run_self_correction(
        question="q", schema_context="s", database_type="SQLite",
        read_only=True, initial_sql="SELECT 1",
        generate=generate, execute=execute, transform=transform, max_retries=1,
    )
    assert out.succeeded is True
    assert seen == ["SELECT 1 LIMIT 100"]
    assert out.sql == "SELECT 1 LIMIT 100"
