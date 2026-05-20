"""Tests for SchemaInspector wiring with HybridRetriever (Task 10)."""

from __future__ import annotations

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from app.core.database.schema_inspector import SchemaInspector
from app.config import get_settings


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def inspector(monkeypatch, tmp_path):
    """Create a SchemaInspector with EMBEDDING_INDEX_DIR pointed at a tmp dir."""
    monkeypatch.setenv("EMBEDDING_INDEX_DIR", str(tmp_path / "embeddings"))
    get_settings.cache_clear()
    insp = SchemaInspector()
    # Patch out the embedder acquisition so no sentence-transformers needed
    insp._hybrid._embedder = None
    insp._hybrid.hybrid_enabled = False
    return insp


@pytest.fixture(autouse=True)
def _reset_settings_cache():
    """Always reset the lru_cache after each test."""
    yield
    get_settings.cache_clear()


# ---------------------------------------------------------------------------
# Test: get_relevant_schema_summary calls HybridRetriever.build_context
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_calls_hybrid_once_per_cache_window(inspector, monkeypatch):
    """Same question + db_id should hit the TTL cache on the second call."""
    mock_hybrid = MagicMock()
    mock_hybrid.build_context = AsyncMock(return_value="fake_summary")
    inspector._hybrid = mock_hybrid

    async def fake_tables(*a, **k):
        return [{"name": "t", "columns": []}]

    async def fake_fks(*a, **k):
        return []

    async def fake_hash(*a, **k):
        return 1

    monkeypatch.setattr(inspector, "_get_all_tables_info", fake_tables)
    monkeypatch.setattr(inspector, "_get_foreign_keys", fake_fks)
    monkeypatch.setattr(inspector, "get_schema_version", fake_hash)

    conn = AsyncMock()
    s1 = await inspector.get_relevant_schema_summary(conn, "show all users")
    s2 = await inspector.get_relevant_schema_summary(conn, "show all users")
    assert s1 == s2 == "fake_summary"
    # Second call should hit the TTL cache — build_context called only once
    assert mock_hybrid.build_context.call_count == 1


@pytest.mark.asyncio
async def test_calls_hybrid_again_for_different_question(inspector, monkeypatch):
    """Different question → different cache key → build_context called twice."""
    mock_hybrid = MagicMock()
    mock_hybrid.build_context = AsyncMock(side_effect=["summary_a", "summary_b"])
    inspector._hybrid = mock_hybrid

    async def fake_tables(*a, **k):
        return [{"name": "t", "columns": []}]

    async def fake_fks(*a, **k):
        return []

    async def fake_hash(*a, **k):
        return 1

    monkeypatch.setattr(inspector, "_get_all_tables_info", fake_tables)
    monkeypatch.setattr(inspector, "_get_foreign_keys", fake_fks)
    monkeypatch.setattr(inspector, "get_schema_version", fake_hash)

    conn = AsyncMock()
    s1 = await inspector.get_relevant_schema_summary(conn, "show all users")
    s2 = await inspector.get_relevant_schema_summary(conn, "list all orders")
    assert s1 == "summary_a"
    assert s2 == "summary_b"
    assert mock_hybrid.build_context.call_count == 2


@pytest.mark.asyncio
async def test_passes_progress_to_build_context(inspector, monkeypatch):
    """The progress kwarg must be forwarded to HybridRetriever.build_context."""
    mock_hybrid = MagicMock()
    mock_hybrid.build_context = AsyncMock(return_value="ok")
    inspector._hybrid = mock_hybrid

    async def fake_tables(*a, **k):
        return []

    async def fake_fks(*a, **k):
        return []

    async def fake_hash(*a, **k):
        return 99

    monkeypatch.setattr(inspector, "_get_all_tables_info", fake_tables)
    monkeypatch.setattr(inspector, "_get_foreign_keys", fake_fks)
    monkeypatch.setattr(inspector, "get_schema_version", fake_hash)

    sentinel_progress = MagicMock()
    conn = AsyncMock()
    await inspector.get_relevant_schema_summary(
        conn, "any question", progress=sentinel_progress
    )
    call_kwargs = mock_hybrid.build_context.call_args[1]
    assert call_kwargs.get("progress") is sentinel_progress


# ---------------------------------------------------------------------------
# Test: clear_cache_for_database removes TTL entries and .npz files
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_clear_cache_removes_npz(inspector, tmp_path, monkeypatch):
    """clear_cache_for_database should delete all {db_id}__*.npz files for that db."""
    index_dir = Path(get_settings().EMBEDDING_INDEX_DIR).expanduser()
    index_dir.mkdir(parents=True, exist_ok=True)

    # Create fake .npz files for two different db_ids
    (index_dir / "default__1__test.npz").write_bytes(b"x")
    (index_dir / "default__2__test.npz").write_bytes(b"x")
    (index_dir / "other__1__test.npz").write_bytes(b"x")

    inspector.clear_cache_for_database("default")

    # Both default files should be gone
    assert not (index_dir / "default__1__test.npz").exists()
    assert not (index_dir / "default__2__test.npz").exists()
    # File belonging to a different db_id must remain
    assert (index_dir / "other__1__test.npz").exists()


@pytest.mark.asyncio
async def test_clear_cache_does_not_error_when_no_npz_files(inspector, tmp_path, monkeypatch):
    """clear_cache_for_database should succeed even if index_dir is empty."""
    index_dir = Path(get_settings().EMBEDDING_INDEX_DIR).expanduser()
    index_dir.mkdir(parents=True, exist_ok=True)
    # No files — should not raise
    inspector.clear_cache_for_database("default")


@pytest.mark.asyncio
async def test_clear_cache_does_not_error_when_index_dir_missing(inspector, tmp_path, monkeypatch):
    """clear_cache_for_database should succeed even if index_dir doesn't exist yet."""
    # index_dir was NOT created — glob should simply return no matches
    inspector.clear_cache_for_database("nonexistent_db")


# ---------------------------------------------------------------------------
# Test: is_pk / is_fk annotation in _get_all_tables_info
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_all_tables_info_annotates_pk_and_fk(monkeypatch, tmp_path):
    """_get_all_tables_info should annotate columns with is_pk and is_fk flags."""
    monkeypatch.setenv("EMBEDDING_INDEX_DIR", str(tmp_path / "embeddings"))
    get_settings.cache_clear()

    insp = SchemaInspector()

    # Mock _get_primary_keys and _get_foreign_keys
    async def fake_pks(*a, **k):
        return {"users": {"id"}, "orders": {"id"}}

    async def fake_fks(*a, **k):
        return [{"table": "orders", "column": "user_id", "ref_table": "users", "ref_column": "id"}]

    monkeypatch.setattr(insp, "_get_primary_keys", fake_pks)
    monkeypatch.setattr(insp, "_get_foreign_keys", fake_fks)

    # Mock the DB query
    conn = AsyncMock()
    # Simulate rows: (table_name, col_name, data_type, is_nullable, col_default, is_generated)
    rows = [
        ("users", "id", "integer", "NO", None, "NEVER"),
        ("users", "email", "text", "YES", None, "NEVER"),
        ("orders", "id", "integer", "NO", None, "NEVER"),
        ("orders", "user_id", "integer", "NO", None, "NEVER"),
    ]

    class FakeResult:
        def fetchall(self):
            return rows
        def keys(self):
            return ["table_name", "column_name", "data_type", "is_nullable", "column_default", "is_generated"]

    conn.execute.return_value = FakeResult()

    tables_info = await insp._get_all_tables_info(conn, max_tables=10, db_id="default")

    # Find users.id — should be is_pk=True, is_fk=False
    users_table = next(t for t in tables_info if t["name"] == "users")
    users_id_col = next(c for c in users_table["columns"] if c["name"] == "id")
    assert users_id_col["is_pk"] is True
    assert users_id_col["is_fk"] is False

    # Find orders.user_id — should be is_pk=False, is_fk=True
    orders_table = next(t for t in tables_info if t["name"] == "orders")
    orders_user_id_col = next(c for c in orders_table["columns"] if c["name"] == "user_id")
    assert orders_user_id_col["is_pk"] is False
    assert orders_user_id_col["is_fk"] is True

    # Find users.email — should be is_pk=False, is_fk=False
    users_email_col = next(c for c in users_table["columns"] if c["name"] == "email")
    assert users_email_col["is_pk"] is False
    assert users_email_col["is_fk"] is False
