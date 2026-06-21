"""Self-correction wiring for POST /query/natural."""

import pytest
from contextlib import asynccontextmanager
from fastapi.testclient import TestClient

from app.main import app
from app.dependencies import get_sql_generator, get_query_validator, get_query_executor
from app.core.database.connection_manager import get_db_manager


# ---------------------------------------------------------------------------
# Fake connection with begin_nested() support
# ---------------------------------------------------------------------------

class _FakeNested:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False


class _FakeConn:
    def begin_nested(self):
        return _FakeNested()


# ---------------------------------------------------------------------------
# Fake DB manager
# ---------------------------------------------------------------------------

class _FakeDbConfig:
    nickname = "test-db"


class _FakeDbManager:
    _default_db_id = "test"

    @property
    def is_configured(self):
        return True

    def list_databases(self):
        return ["test"]

    def get_database_config(self, db_id):
        return _FakeDbConfig()

    @asynccontextmanager
    async def get_connection(self, db_id):
        yield _FakeConn()


# ---------------------------------------------------------------------------
# Fake SQL generator
# ---------------------------------------------------------------------------

class _FakeGen:
    schema_inspector = None  # Not called in success path — only on retry 2

    async def generate(self, **kwargs):
        from app.core.ai.ollama_sql_generator import SQLGenerationResult
        return SQLGenerationResult(
            sql="SELECT pet_type FROM pets",
            explanation="e",
            schema_context="CREATE TABLE pets (PetType TEXT);",
            database_type="SQLite",
        )


# ---------------------------------------------------------------------------
# Fake validator
# ---------------------------------------------------------------------------

class _FakeValidator:
    def validate(self, sql):
        return sql


# ---------------------------------------------------------------------------
# Fake executor — raises on first call, succeeds on second
# ---------------------------------------------------------------------------

class _FakeExecutor:
    def __init__(self):
        self.calls = 0

    async def execute(self, connection, sql, pagination=None):
        self.calls += 1
        if "pet_type" in sql:
            raise Exception("no such column: pet_type")
        return ([{"PetType": "dog"}], 1.0, 1)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_self_correction_recovers_exec_fail(monkeypatch):
    executor = _FakeExecutor()

    async def fake_generate(prompt, provider, model, api_key):
        return "```sql\nSELECT PetType FROM pets\n```"

    monkeypatch.setattr(
        "app.api.v1.endpoints.query.generate_with_config", fake_generate
    )

    app.dependency_overrides[get_sql_generator] = lambda: _FakeGen()
    app.dependency_overrides[get_query_validator] = lambda: _FakeValidator()
    app.dependency_overrides[get_query_executor] = lambda: executor
    app.dependency_overrides[get_db_manager] = lambda: _FakeDbManager()

    try:
        client = TestClient(app)
        resp = client.post(
            "/api/v1/query/natural?database_id=test",
            json={"question": "pets?", "options": {"execute": True, "read_only": True}},
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        body = resp.json()
        assert body["execution_result"]["rows"] == [{"PetType": "dog"}]
        assert body["metadata"]["self_correction_retries"] == 1
        assert executor.calls == 2
    finally:
        app.dependency_overrides.clear()


def test_self_correction_disabled_raises_on_fail():
    """When SELF_CORRECTION_ENABLED=False, executor failure propagates as HTTP 500."""
    from app.config import get_settings as _get_settings
    original_settings = _get_settings()

    class _PatchedSettings:
        SELF_CORRECTION_ENABLED = False
        SELF_CORRECTION_MAX_RETRIES = 2

        def __getattr__(self, name):
            return getattr(original_settings, name)

    executor = _FakeExecutor()

    app.dependency_overrides[get_sql_generator] = lambda: _FakeGen()
    app.dependency_overrides[get_query_validator] = lambda: _FakeValidator()
    app.dependency_overrides[get_query_executor] = lambda: executor
    app.dependency_overrides[get_db_manager] = lambda: _FakeDbManager()
    app.dependency_overrides[_get_settings] = lambda: _PatchedSettings()

    try:
        client = TestClient(app)
        resp = client.post(
            "/api/v1/query/natural?database_id=test",
            json={"question": "pets?", "options": {"execute": True, "read_only": True}},
        )
        # Without correction, exception bubbles up as 500
        assert resp.status_code == 500
        # Executor called exactly once (no retry)
        assert executor.calls == 1
    finally:
        app.dependency_overrides.clear()
