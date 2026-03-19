"""Tests for app.core.ai.prompts — prompt building and response parsing."""

import pytest
from app.core.ai.prompts import (
    build_sql_generation_prompt,
    extract_sql_from_response,
    extract_explanation_from_response,
    build_explanation,
)


# ---------------------------------------------------------------------------
# build_sql_generation_prompt
# ---------------------------------------------------------------------------

class TestBuildSqlGenerationPrompt:
    def test_contains_question(self, sample_schema):
        prompt = build_sql_generation_prompt("Show all users", sample_schema)
        assert "Show all users" in prompt

    def test_contains_schema(self, sample_schema):
        prompt = build_sql_generation_prompt("x", sample_schema)
        assert "CREATE TABLE users" in prompt

    def test_defaults_to_postgresql(self, sample_schema):
        prompt = build_sql_generation_prompt("x", sample_schema)
        assert "PostgreSQL" in prompt

    def test_mysql_type(self, sample_schema):
        prompt = build_sql_generation_prompt("x", sample_schema, database_type="MySQL")
        assert "MySQL" in prompt
        assert "PostgreSQL" not in prompt

    def test_read_only_constraint(self, sample_schema):
        prompt = build_sql_generation_prompt("x", sample_schema, read_only=True)
        assert "Only generate SELECT queries" in prompt

    def test_write_allowed_constraint(self, sample_schema):
        prompt = build_sql_generation_prompt("x", sample_schema, read_only=False)
        assert "Generate exactly the SQL" in prompt

    def test_ends_with_sql_fence(self, sample_schema):
        prompt = build_sql_generation_prompt("x", sample_schema)
        assert prompt.rstrip().endswith("```sql")

    def test_enforcement_note_present(self, sample_schema):
        prompt = build_sql_generation_prompt("x", sample_schema)
        assert "never invent or guess names" in prompt


# ---------------------------------------------------------------------------
# extract_sql_from_response
# ---------------------------------------------------------------------------

class TestExtractSqlFromResponse:
    def test_raw_select(self):
        resp = "SELECT * FROM users WHERE id = 1;"
        assert extract_sql_from_response(resp) == "SELECT * FROM users WHERE id = 1;"

    def test_raw_select_no_semicolon(self):
        resp = "SELECT * FROM users"
        result = extract_sql_from_response(resp)
        assert result.endswith(";")

    def test_sql_code_block(self):
        resp = "Here is the SQL:\n```sql\nSELECT 1;\n```"
        result = extract_sql_from_response(resp)
        assert result is not None
        assert "SELECT 1;" in result

    def test_generic_code_block(self):
        resp = "```\nSELECT 1;\n```"
        result = extract_sql_from_response(resp)
        assert result is not None
        assert "SELECT 1;" in result

    def test_json_response(self):
        resp = '{"sql": "SELECT 1;"}'
        assert extract_sql_from_response(resp) == "SELECT 1;"

    def test_json_query_key(self):
        resp = '{"query": "SELECT id FROM users;"}'
        assert extract_sql_from_response(resp) == "SELECT id FROM users;"

    def test_empty_returns_none(self):
        assert extract_sql_from_response("") is None
        assert extract_sql_from_response("   ") is None
        assert extract_sql_from_response(None) is None

    def test_no_sql_returns_none(self):
        assert extract_sql_from_response("Hello world, no SQL here.") is None

    def test_strips_explanation_after_sql(self):
        resp = "SELECT * FROM users;\nExplanation: gets all users"
        result = extract_sql_from_response(resp)
        assert "Explanation" not in result
        assert "SELECT * FROM users;" in result

    def test_insert_statement(self):
        resp = "INSERT INTO users (name) VALUES ('bob');"
        assert "INSERT INTO" in extract_sql_from_response(resp)

    def test_with_cte(self):
        resp = "WITH recent AS (SELECT * FROM users) SELECT * FROM recent;"
        result = extract_sql_from_response(resp)
        assert result.startswith("WITH")

    def test_update_statement(self):
        resp = "UPDATE users SET name = 'alice' WHERE id = 1;"
        result = extract_sql_from_response(resp)
        assert "UPDATE" in result

    def test_delete_statement(self):
        resp = "DELETE FROM users WHERE id = 1;"
        result = extract_sql_from_response(resp)
        assert "DELETE" in result


# ---------------------------------------------------------------------------
# extract_explanation_from_response
# ---------------------------------------------------------------------------

class TestExtractExplanationFromResponse:
    def test_empty(self):
        assert extract_explanation_from_response("") == ""
        assert extract_explanation_from_response(None) == ""

    def test_labeled_explanation(self):
        resp = "SELECT 1;\nExplanation: Gets the number one."
        result = extract_explanation_from_response(resp)
        assert "Gets the number one" in result

    def test_bold_labeled_explanation(self):
        resp = "SELECT 1;\n**Explanation:** Gets the number one."
        result = extract_explanation_from_response(resp)
        assert "Gets the number one" in result

    def test_json_explanation(self):
        resp = '{"sql": "SELECT 1;", "explanation": "Gets the number one."}'
        result = extract_explanation_from_response(resp)
        assert "Gets the number one" in result

    def test_truncation_at_500_chars(self):
        long = "x" * 600
        resp = f'{{"explanation": "{long}"}}'
        result = extract_explanation_from_response(resp)
        assert len(result) == 500
        assert result.endswith("...")

    def test_no_explanation_returns_empty(self):
        result = extract_explanation_from_response("SELECT * FROM users;")
        assert result == ""


# ---------------------------------------------------------------------------
# build_explanation
# ---------------------------------------------------------------------------

class TestBuildExplanation:
    def test_select(self):
        result = build_explanation("Show users", "SELECT * FROM users;")
        assert "Retrieves" in result
        assert "users" in result

    def test_insert(self):
        result = build_explanation("Add a user", "INSERT INTO users (name) VALUES ('bob');")
        assert "Inserts" in result

    def test_update(self):
        result = build_explanation("Fix name", "UPDATE users SET name='x' WHERE id=1;")
        assert "Updates" in result

    def test_delete(self):
        result = build_explanation("Remove user", "DELETE FROM users WHERE id=1;")
        assert "Deletes" in result

    def test_with_cte(self):
        result = build_explanation("Recent", "WITH r AS (SELECT * FROM users) SELECT * FROM r;")
        assert "CTE" in result

    def test_join_extracts_both_tables(self):
        sql = "SELECT * FROM users JOIN orders ON users.id = orders.user_id;"
        result = build_explanation("User orders", sql)
        assert "users" in result
        assert "orders" in result

    def test_question_in_output(self):
        result = build_explanation("my question", "SELECT 1;")
        assert "my question" in result
