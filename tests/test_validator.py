"""Tests for app.core.query.validator — SQL validation and LIMIT enforcement."""

import pytest
from unittest.mock import patch, MagicMock
from app.core.query.validator import QueryValidator
from app.exceptions import QueryValidationError, QuerySyntaxError


@pytest.fixture
def validator():
    """QueryValidator with default settings."""
    settings = MagicMock()
    settings.MAX_QUERY_RESULTS = 1000
    settings.DEFAULT_QUERY_LIMIT = 100
    with patch("app.core.query.validator.get_settings", return_value=settings):
        return QueryValidator()


class TestValidateBasic:
    def test_valid_select(self, validator):
        result = validator.validate("SELECT * FROM users;")
        assert "SELECT" in result

    def test_empty_raises(self, validator):
        with pytest.raises(QueryValidationError, match="empty"):
            validator.validate("")

    def test_whitespace_only_raises(self, validator):
        with pytest.raises(QueryValidationError, match="empty"):
            validator.validate("   ")

    def test_multiple_statements_raises(self, validator):
        with pytest.raises(QueryValidationError, match="Multiple"):
            validator.validate("SELECT 1; SELECT 2;")

    def test_insert_passes(self, validator):
        result = validator.validate("INSERT INTO users (name) VALUES ('bob');")
        assert "INSERT" in result

    def test_update_passes(self, validator):
        result = validator.validate("UPDATE users SET name='x' WHERE id=1;")
        assert "UPDATE" in result

    def test_delete_passes(self, validator):
        result = validator.validate("DELETE FROM users WHERE id=1;")
        assert "DELETE" in result


class TestLimitEnforcement:
    def test_adds_limit_to_select(self, validator):
        result = validator.validate("SELECT * FROM users")
        assert "LIMIT 100" in result

    def test_preserves_existing_limit(self, validator):
        result = validator.validate("SELECT * FROM users LIMIT 50;")
        assert "LIMIT 50" in result

    def test_caps_excessive_limit(self, validator):
        result = validator.validate("SELECT * FROM users LIMIT 9999;")
        assert "LIMIT 1000" in result

    def test_no_limit_on_insert(self, validator):
        result = validator.validate("INSERT INTO users (name) VALUES ('bob');")
        assert "LIMIT" not in result

    def test_no_limit_on_update(self, validator):
        result = validator.validate("UPDATE users SET name='x' WHERE id=1;")
        assert "LIMIT" not in result

    def test_with_cte_gets_limit(self, validator):
        sql = "WITH recent AS (SELECT * FROM users) SELECT * FROM recent"
        result = validator.validate(sql)
        assert "LIMIT 100" in result

    def test_limit_at_max_is_kept(self, validator):
        result = validator.validate("SELECT * FROM users LIMIT 1000;")
        assert "LIMIT 1000" in result
