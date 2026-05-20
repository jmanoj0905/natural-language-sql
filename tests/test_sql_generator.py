"""Tests for app.core.ai.ollama_sql_generator."""

from unittest.mock import ANY, AsyncMock, MagicMock, patch

import pytest

from app.core.ai.ollama_sql_generator import SQLGenerator


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
