"""Tests for app.core.database.retrieval.formatter.format_schema_context."""

import pytest
from app.core.database.retrieval.formatter import format_schema_context


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

ORDERS_TABLE = {
    "name": "orders",
    "columns": [
        {"name": "id", "type": "integer", "nullable": False},
        {"name": "user_id", "type": "integer", "nullable": False},
        {"name": "amount", "type": "numeric", "nullable": True},
    ],
}

USERS_TABLE = {
    "name": "users",
    "columns": [
        {"name": "id", "type": "integer", "nullable": False},
        {"name": "name", "type": "varchar(255)", "nullable": True, "default": "''"},
    ],
}

FK_ORDERS_TO_USERS = {
    "table": "orders",
    "column": "user_id",
    "ref_table": "users",
    "ref_column": "id",
}


# ---------------------------------------------------------------------------
# 1. Output contains CREATE TABLE, FOREIGN KEY, -- RELATIONSHIPS
# ---------------------------------------------------------------------------

def test_output_contains_create_table():
    result = format_schema_context([ORDERS_TABLE, USERS_TABLE], [FK_ORDERS_TO_USERS])
    assert "CREATE TABLE orders (" in result
    assert "CREATE TABLE users (" in result


def test_output_contains_foreign_key_inline():
    result = format_schema_context([ORDERS_TABLE, USERS_TABLE], [FK_ORDERS_TO_USERS])
    assert "FOREIGN KEY (user_id) REFERENCES users(id)" in result


def test_output_contains_relationships_footer():
    result = format_schema_context([ORDERS_TABLE, USERS_TABLE], [FK_ORDERS_TO_USERS])
    assert "-- RELATIONSHIPS (use these for JOINs):" in result
    assert "orders.user_id -> users.id" in result


# ---------------------------------------------------------------------------
# 2. Sample row line present when sample_rows_by_table is provided
# ---------------------------------------------------------------------------

def test_sample_rows_present_when_provided():
    sample = {"orders": [{"id": 1, "user_id": 2, "amount": 9.99}]}
    result = format_schema_context(
        [ORDERS_TABLE, USERS_TABLE],
        [FK_ORDERS_TO_USERS],
        sample_rows_by_table=sample,
    )
    assert "-- Sample rows from orders:" in result
    assert "id=1" in result
    assert "user_id=2" in result
    assert "amount=9.99" in result


# ---------------------------------------------------------------------------
# 3. Sample row line absent when not provided
# ---------------------------------------------------------------------------

def test_sample_rows_absent_when_not_provided():
    result = format_schema_context([ORDERS_TABLE, USERS_TABLE], [FK_ORDERS_TO_USERS])
    assert "-- Sample rows from" not in result


def test_sample_rows_absent_when_none():
    result = format_schema_context(
        [ORDERS_TABLE, USERS_TABLE], [FK_ORDERS_TO_USERS], sample_rows_by_table=None
    )
    assert "-- Sample rows from" not in result


# ---------------------------------------------------------------------------
# 4. Same input → byte-identical output (determinism)
# ---------------------------------------------------------------------------

def test_deterministic_output():
    sample = {"orders": [{"id": 1, "user_id": 2, "amount": 9.99}]}
    a = format_schema_context(
        [ORDERS_TABLE, USERS_TABLE], [FK_ORDERS_TO_USERS], sample_rows_by_table=sample
    )
    b = format_schema_context(
        [ORDERS_TABLE, USERS_TABLE], [FK_ORDERS_TO_USERS], sample_rows_by_table=sample
    )
    assert a == b


# ---------------------------------------------------------------------------
# 5. Empty selected_tables → sentinel string
# ---------------------------------------------------------------------------

def test_empty_tables_returns_sentinel():
    result = format_schema_context([], [])
    assert result == "-- No tables found in this database."


def test_empty_tables_with_fks_returns_sentinel():
    result = format_schema_context([], [FK_ORDERS_TO_USERS])
    assert result == "-- No tables found in this database."


# ---------------------------------------------------------------------------
# 6. fallback_used=True → first line is the fallback comment
# ---------------------------------------------------------------------------

def test_fallback_used_first_line():
    result = format_schema_context(
        [USERS_TABLE], [], fallback_used=True
    )
    first_line = result.splitlines()[0]
    assert first_line == (
        "-- Schema retrieval had no lexical matches; showing a bounded fallback."
    )


def test_fallback_not_used_first_line_is_header():
    result = format_schema_context([USERS_TABLE], [], fallback_used=False)
    first_line = result.splitlines()[0]
    assert first_line.startswith("-- AVAILABLE TABLES")


# ---------------------------------------------------------------------------
# 7. Relationships footer only includes FKs where BOTH endpoints in selected_names
# ---------------------------------------------------------------------------

def test_relationships_only_when_both_endpoints_selected():
    # Only orders is selected — users is NOT — so FK should not appear in footer
    result = format_schema_context([ORDERS_TABLE], [FK_ORDERS_TO_USERS])
    assert "-- RELATIONSHIPS" not in result
    assert "-> users.id" not in result


def test_relationships_excluded_inline_fk_when_ref_table_not_selected():
    # Inline FK inside CREATE TABLE should also be suppressed if ref_table not selected
    result = format_schema_context([ORDERS_TABLE], [FK_ORDERS_TO_USERS])
    assert "FOREIGN KEY (user_id) REFERENCES users(id)" not in result


def test_relationships_present_when_both_selected():
    result = format_schema_context([ORDERS_TABLE, USERS_TABLE], [FK_ORDERS_TO_USERS])
    assert "-- RELATIONSHIPS (use these for JOINs):" in result
    assert "orders.user_id -> users.id" in result


# ---------------------------------------------------------------------------
# 8. Column modifiers: NOT NULL and DEFAULT
# ---------------------------------------------------------------------------

def test_not_null_emitted_when_nullable_false():
    result = format_schema_context([ORDERS_TABLE], [])
    assert "id integer NOT NULL" in result


def test_nullable_col_no_not_null():
    result = format_schema_context([ORDERS_TABLE], [])
    # amount is nullable=True, should not have NOT NULL
    lines = [l for l in result.splitlines() if "amount" in l]
    assert lines, "Expected a line containing 'amount'"
    assert "NOT NULL" not in lines[0]


def test_default_emitted_when_present():
    result = format_schema_context([USERS_TABLE], [])
    assert "DEFAULT" in result
    assert "''" in result


# ---------------------------------------------------------------------------
# 9. Header line
# ---------------------------------------------------------------------------

def test_header_lists_table_names():
    result = format_schema_context([ORDERS_TABLE, USERS_TABLE], [])
    assert "-- AVAILABLE TABLES (use only these exact names, do not guess):" in result
    # The table names should appear on the next line
    lines = result.splitlines()
    header_idx = next(i for i, l in enumerate(lines) if "AVAILABLE TABLES" in l)
    names_line = lines[header_idx + 1]
    assert "orders" in names_line
    assert "users" in names_line


# ---------------------------------------------------------------------------
# 10. No trailing newline
# ---------------------------------------------------------------------------

def test_no_trailing_newline():
    result = format_schema_context([USERS_TABLE], [])
    assert not result.endswith("\n")


# ---------------------------------------------------------------------------
# 11. repr() used for sample row values
# ---------------------------------------------------------------------------

def test_repr_used_for_string_values():
    sample = {"users": [{"id": 1, "name": "Alice"}]}
    result = format_schema_context(
        [USERS_TABLE], [], sample_rows_by_table=sample
    )
    # repr("Alice") == "'Alice'"
    assert "name='Alice'" in result


def test_repr_used_for_none_values():
    sample = {"users": [{"id": 1, "name": None}]}
    result = format_schema_context(
        [USERS_TABLE], [], sample_rows_by_table=sample
    )
    assert "name=None" in result
