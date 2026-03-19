"""Tests for app.api.v1.endpoints.query_stream — SSE streaming endpoint."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.api.v1.endpoints.query_stream import sse_event, _parse_db_ids


# ---------------------------------------------------------------------------
# sse_event helper
# ---------------------------------------------------------------------------

class TestSseEvent:
    def test_format(self):
        result = sse_event("progress", {"stage": "connect"})
        assert result.startswith("event: progress\n")
        assert "data: " in result
        assert result.endswith("\n\n")

    def test_data_is_json(self):
        result = sse_event("error", {"code": "TEST"})
        data_line = [l for l in result.split("\n") if l.startswith("data: ")][0]
        parsed = json.loads(data_line[6:])
        assert parsed["code"] == "TEST"


# ---------------------------------------------------------------------------
# _parse_db_ids helper
# ---------------------------------------------------------------------------

class TestParseDbIds:
    def _mock_manager(self, default_id=None):
        m = MagicMock()
        m._default_db_id = default_id
        return m

    def test_database_ids_comma_separated(self):
        result = _parse_db_ids("a,b,c", None, self._mock_manager())
        assert result == ["a", "b", "c"]

    def test_database_ids_strips_whitespace(self):
        result = _parse_db_ids(" a , b ", None, self._mock_manager())
        assert result == ["a", "b"]

    def test_database_id_fallback(self):
        result = _parse_db_ids(None, "single", self._mock_manager())
        assert result == ["single"]

    def test_default_fallback(self):
        result = _parse_db_ids(None, None, self._mock_manager(default_id="def"))
        assert result == ["def"]

    def test_empty_when_nothing(self):
        result = _parse_db_ids(None, None, self._mock_manager())
        assert result == []

    def test_database_ids_takes_precedence(self):
        result = _parse_db_ids("a,b", "ignored", self._mock_manager(default_id="also_ignored"))
        assert result == ["a", "b"]

    def test_empty_strings_filtered(self):
        result = _parse_db_ids("a,,b,", None, self._mock_manager())
        assert result == ["a", "b"]
