"""Tests for app.core.ai.ollama_sql_generator."""

from unittest.mock import ANY, AsyncMock, MagicMock, patch

import pytest

from app.core.ai.ollama_sql_generator import SQLGenerator, SQLGenerationResult


@pytest.mark.asyncio
async def test_generate_sql_uses_question_scoped_schema_retrieval():
    generator = SQLGenerator()
    generator.schema_inspector.get_relevant_schema_summary = AsyncMock(
        return_value="CREATE TABLE purchases (id integer, total_amount numeric);"
    )

    with patch(
        "app.core.ai.ollama_sql_generator.generate_with_config",
        new=AsyncMock(return_value="SELECT total_amount FROM purchases;"),
    ):
        sql, _ = await generator.generate_sql(
            question="show purchase totals",
            connection=MagicMock(),
            db_id="sales",
            read_only=True,
        )

    assert sql == "SELECT total_amount FROM purchases;"
    generator.schema_inspector.get_relevant_schema_summary.assert_awaited_once_with(
        ANY,
        question="show purchase totals",
        db_id="sales",
    )


@pytest.mark.asyncio
async def test_generate_returns_schema_context(monkeypatch):
    gen = SQLGenerator()

    async def fake_schema(self, connection, question, db_id):
        return "CREATE TABLE users (id INT);"

    async def fake_generate(prompt, provider, model, api_key):
        return "```sql\nSELECT * FROM users\n```"

    monkeypatch.setattr(
        "app.core.ai.ollama_sql_generator.SchemaInspector.get_relevant_schema_summary",
        fake_schema,
    )
    monkeypatch.setattr(
        "app.core.ai.ollama_sql_generator.generate_with_config", fake_generate
    )

    result = await gen.generate(
        question="show users", connection=None, db_id="default", read_only=True
    )
    assert isinstance(result, SQLGenerationResult)
    assert "SELECT * FROM users" in result.sql
    assert "CREATE TABLE users" in result.schema_context
    assert result.database_type in ("PostgreSQL", "MySQL")


@pytest.mark.asyncio
async def test_generate_sql_still_returns_tuple(monkeypatch):
    gen = SQLGenerator()

    async def fake_schema(self, connection, question, db_id):
        return "CREATE TABLE users (id INT);"

    async def fake_generate(prompt, provider, model, api_key):
        return "```sql\nSELECT 1\n```"

    monkeypatch.setattr(
        "app.core.ai.ollama_sql_generator.SchemaInspector.get_relevant_schema_summary",
        fake_schema,
    )
    monkeypatch.setattr(
        "app.core.ai.ollama_sql_generator.generate_with_config", fake_generate
    )

    sql, explanation = await gen.generate_sql(
        question="x", connection=None, db_id="default"
    )
    assert "SELECT 1" in sql
    assert isinstance(explanation, str)
