"""Tests for app.api.v1.endpoints.query_stream — SSE streaming endpoint."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.api.v1.endpoints.query_stream import sse_event, _parse_db_ids
import app.core.security.key_store as key_store
import app.core.security.secret_store as secret_store
from app.config import get_settings


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


# ---------------------------------------------------------------------------
# Integration helpers for streaming endpoint tests
# ---------------------------------------------------------------------------

def collect_sse_events(client, url, body):
    """POST to the SSE endpoint and parse all events from the stream.

    Returns a list of dicts with keys "event" and "data" (parsed JSON).
    """
    response = client.post(url, json=body)
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

    events = []
    current_event = None
    current_data = None

    for line in response.text.splitlines():
        if line.startswith("event: "):
            current_event = line[len("event: "):]
        elif line.startswith("data: "):
            current_data = line[len("data: "):]
        elif line == "" and current_event is not None and current_data is not None:
            try:
                parsed_data = json.loads(current_data)
            except json.JSONDecodeError:
                parsed_data = {"raw": current_data}
            events.append({"event": current_event, "data": parsed_data})
            current_event = None
            current_data = None

    # flush final event if no trailing blank line
    if current_event is not None and current_data is not None:
        try:
            parsed_data = json.loads(current_data)
        except json.JSONDecodeError:
            parsed_data = {"raw": current_data}
        events.append({"event": current_event, "data": parsed_data})

    return events


# ---------------------------------------------------------------------------
# Fake async infrastructure for streaming integration tests
# ---------------------------------------------------------------------------

class _FakeNested:
    """Async context manager returned by conn.begin_nested()."""

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakeConn:
    """Minimal async connection fake with begin_nested() support."""

    def begin_nested(self):
        return _FakeNested()


class _FakeConnCM:
    """Fake async context manager wrapping _FakeConn."""

    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, *args):
        pass


def _make_db_manager(db_id: str = "test", db_type: str = "postgresql"):
    """Build a mock DatabaseConnectionManager for a single database."""
    fake_conn = _FakeConn()
    fake_cm = _FakeConnCM(fake_conn)

    db_config = MagicMock()
    db_config.db_type = db_type
    db_config.nickname = "Test DB"

    manager = MagicMock()
    manager.is_configured = True
    manager._default_db_id = db_id
    manager.list_databases.return_value = [db_id]
    manager.get_database_config.return_value = db_config
    manager.get_connection.return_value = fake_cm

    return manager, fake_conn


def _make_validator():
    """Return a validator whose validate() passes SQL through unchanged."""
    v = MagicMock()
    v.validate.side_effect = lambda sql: sql
    return v


# ---------------------------------------------------------------------------
# Self-correction streaming test
# ---------------------------------------------------------------------------

@pytest.fixture
def sse_client_with_failing_executor():
    """
    TestClient wired so:
      - generate_with_config returns corrected SQL on the second call
      - executor.execute raises on the first SQL, succeeds on the second
      - SELF_CORRECTION_ENABLED = True
    """
    from fastapi.testclient import TestClient
    from fastapi import FastAPI
    from app.api.v1.endpoints import query_stream as qs_module
    from app.config import Settings

    # Create a minimal FastAPI app with the stream router
    app = FastAPI()
    app.include_router(qs_module.router, prefix="/api/v1")

    manager, fake_conn = _make_db_manager()
    validator = _make_validator()

    # Executor: fail on the bad SQL, succeed with results on the corrected SQL
    bad_sql_marker = "SELECT PetType FROM pets"
    good_sql_marker = "SELECT PetType FROM pets"  # corrected SQL (same text for simplicity)

    call_count = {"n": 0}

    async def _fake_execute(connection, sql, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise RuntimeError("no such column: PetType")
        # Second call succeeds
        return ([{"PetType": "Cat"}, {"PetType": "Dog"}], 5.0, None)

    executor = MagicMock()
    executor.execute = _fake_execute

    # Override settings with self-correction enabled
    fake_settings = Settings(
        SELF_CORRECTION_ENABLED=True,
        SELF_CORRECTION_MAX_RETRIES=2,
        OLLAMA_MODEL="test-model",
    )

    # DI overrides
    from app.dependencies import get_query_validator, get_query_executor
    from app.config import get_settings
    from app.core.database.connection_manager import get_db_manager

    app.dependency_overrides[get_db_manager] = lambda: manager
    app.dependency_overrides[get_query_validator] = lambda: validator
    app.dependency_overrides[get_query_executor] = lambda: executor
    app.dependency_overrides[get_settings] = lambda: fake_settings

    # Patch generate_with_config and schema_inspector at the module level
    gen_call_count = {"n": 0}

    async def _fake_generate(prompt, provider=None, model=None, api_key=None, ollama_url=None):
        gen_call_count["n"] += 1
        # Always return valid SQL
        return "```sql\nSELECT PetType FROM pets\n```"

    schema_inspector_mock = MagicMock()
    schema_inspector_mock.get_relevant_schema_summary = AsyncMock(
        return_value="CREATE TABLE pets (PetType TEXT);"
    )
    schema_inspector_mock.get_schema_summary = AsyncMock(
        return_value="CREATE TABLE pets (PetType TEXT);"
    )

    intent_detector_mock = MagicMock()
    intent_detector_mock.detect_intent.return_value = MagicMock(
        intent=MagicMock(value="read"),
        database_refs=[],
        needs_decomposition=False,
    )

    with (
        patch.object(qs_module, "generate_with_config", _fake_generate),
        patch("app.api.v1.endpoints.query_stream.SchemaInspector", return_value=schema_inspector_mock),
        patch("app.api.v1.endpoints.query_stream.get_intent_detector", return_value=intent_detector_mock),
    ):
        with TestClient(app, raise_server_exceptions=False) as client:
            yield client


def test_stream_emits_self_correct_event_on_exec_fail(sse_client_with_failing_executor):
    """When the executor fails once then succeeds, the stream must emit a
    self_correct progress event and report self_correction_retries == 1 in
    the final result metadata.
    """
    events = collect_sse_events(
        sse_client_with_failing_executor,
        "/api/v1/query/natural/stream?database_id=test",
        {"question": "pets?", "options": {"execute": True, "read_only": True}},
    )
    stages = [e["data"].get("stage") for e in events if e["event"] == "progress"]
    assert "self_correct" in stages, f"Expected 'self_correct' stage in {stages}"

    result_events = [e for e in events if e["event"] == "result"]
    assert result_events, f"No result event found. Events: {events}"
    result = result_events[0]
    assert result["data"]["metadata"]["self_correction_retries"] == 1, (
        f"Expected self_correction_retries=1, got {result['data']['metadata']}"
    )


# ---------------------------------------------------------------------------
# Provider resolution via stored settings
# ---------------------------------------------------------------------------

def _fresh(monkeypatch, tmp_path):
    """Reset encryption / settings state to a clean tmp directory."""
    monkeypatch.setenv("DB_ENCRYPTION_KEY", "")
    get_settings.cache_clear()
    monkeypatch.setattr(key_store, "KEY_FILE", tmp_path / ".encryption_key")
    monkeypatch.setattr(secret_store, "SETTINGS_FILE", tmp_path / "settings.json")
    key_store.reset_cipher_cache()


def test_stream_resolves_provider_from_stored_settings(monkeypatch, tmp_path):
    """Stream endpoint must pass the stored provider/api_key to generate_with_config
    when the request carries only default (ollama) options.
    """
    from fastapi.testclient import TestClient
    from fastapi import FastAPI
    from app.api.v1.endpoints import query_stream as qs_module
    from app.config import Settings

    # Persist a cloud provider key to the secret store
    _fresh(monkeypatch, tmp_path)
    secret_store.save_settings("openai", "gpt-4o-mini", "", api_key="sk-stored-stream")

    app = FastAPI()
    app.include_router(qs_module.router, prefix="/api/v1")

    manager, _fake_conn = _make_db_manager()
    validator = _make_validator()

    captured = {}

    async def _fake_generate(prompt, provider=None, model=None, api_key=None, ollama_url=None):
        captured["provider"] = provider
        captured["api_key"] = api_key
        return "```sql\nSELECT 1\n```"

    fake_settings = Settings(
        SELF_CORRECTION_ENABLED=False,
        OLLAMA_MODEL="test-model",
    )

    executor = MagicMock()
    executor.execute = AsyncMock(return_value=([{"col": 1}], 1.0, None))

    from app.dependencies import get_query_validator, get_query_executor
    from app.core.database.connection_manager import get_db_manager as get_db_mgr

    app.dependency_overrides[get_db_mgr] = lambda: manager
    app.dependency_overrides[get_query_validator] = lambda: validator
    app.dependency_overrides[get_query_executor] = lambda: executor
    app.dependency_overrides[get_settings] = lambda: fake_settings

    schema_inspector_mock = MagicMock()
    schema_inspector_mock.get_relevant_schema_summary = AsyncMock(
        return_value="CREATE TABLE t (id INT);"
    )
    schema_inspector_mock.get_schema_summary = AsyncMock(
        return_value="CREATE TABLE t (id INT);"
    )
    intent_detector_mock = MagicMock()
    intent_detector_mock.detect_intent.return_value = MagicMock(
        intent=MagicMock(value="read"),
        database_refs=[],
        needs_decomposition=False,
    )

    with (
        patch.object(qs_module, "generate_with_config", _fake_generate),
        patch("app.api.v1.endpoints.query_stream.SchemaInspector", return_value=schema_inspector_mock),
        patch("app.api.v1.endpoints.query_stream.get_intent_detector", return_value=intent_detector_mock),
    ):
        with TestClient(app, raise_server_exceptions=False) as client:
            events = collect_sse_events(
                client,
                "/api/v1/query/natural/stream?database_id=test",
                {"question": "count rows", "options": {"execute": True, "read_only": True}},
            )

    assert captured.get("provider") == "openai", (
        f"Expected resolved provider 'openai', got {captured.get('provider')!r}"
    )
    assert captured.get("api_key") == "sk-stored-stream", (
        f"Expected resolved api_key 'sk-stored-stream', got {captured.get('api_key')!r}"
    )
