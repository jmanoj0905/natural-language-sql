"""End-to-end smoke tests for the hybrid RAG path through SQLGenerator.

Covers plan §7.5:
  - Stub embedder + Ollama client.
  - Semantic-mismatch question routes to the correct table (test 1).
  - Prompt contains pruned columns (≤ MAX_COLS_PER_TABLE) + 1 sample row line
    per table (test 2).
  - HYBRID_RETRIEVAL_ENABLED=false produces BM25-only (regression guard, test 3).
"""

from __future__ import annotations

import re
import pytest
import numpy as np
from unittest.mock import AsyncMock

from app.core.ai.ollama_sql_generator import SQLGenerator
from app.config import get_settings


# ---------------------------------------------------------------------------
# FakeEmbedder
# ---------------------------------------------------------------------------


class FakeEmbedder:
    """Minimal drop-in for SchemaEmbedder that uses a keyword→vector mapping.

    Vector space: 4-dimensional.  Each text is assigned a unit vector based
    on keyword matching.  Unmatched texts get the orthogonal [0, 0, 0, 1]
    direction.
    """

    MODEL = "fake-test-embedder"
    DIM = 4

    def __init__(self, mapping=None):
        # mapping: text-substring (lower) → raw vector (will be L2-normalised)
        self.mapping = mapping or {}
        self.calls: list[str] = []

    def embed(self, texts: list[str]) -> np.ndarray:
        out: list[np.ndarray] = []
        for t in texts:
            self.calls.append(t)
            v = self._vector_for(t.lower())
            arr = np.array(v, dtype=np.float32)
            norm = float(np.linalg.norm(arr))
            arr = arr / max(norm, 1e-9)
            out.append(arr)
        return np.array(out, dtype=np.float32)

    def _vector_for(self, text_lower: str) -> list[float]:
        for keyword, vec in self.mapping.items():
            if keyword in text_lower:
                return list(vec)
        return [0.0, 0.0, 0.0, 1.0]  # default orthogonal direction


# ---------------------------------------------------------------------------
# Schema builders
# ---------------------------------------------------------------------------


def _make_col(
    name: str,
    ctype: str = "integer",
    is_pk: bool = False,
    is_fk: bool = False,
) -> dict:
    return {
        "name": name,
        "type": ctype,
        "nullable": True,
        "default": None,
        "is_generated": False,
        "is_pk": is_pk,
        "is_fk": is_fk,
    }


def _small_tables_info() -> list[dict]:
    """3 tables: client, orders, product — no 'customer' token in any name/column."""
    return [
        {
            "name": "client",
            "columns": [
                _make_col("id", is_pk=True),
                _make_col("name", "varchar"),
                _make_col("email", "varchar"),
            ],
        },
        {
            "name": "orders",
            "columns": [
                _make_col("id", is_pk=True),
                _make_col("client_id", is_fk=True),
                _make_col("total", "numeric"),
            ],
        },
        {
            "name": "product",
            "columns": [
                _make_col("id", is_pk=True),
                _make_col("name", "varchar"),
            ],
        },
    ]


def _large_tables_info(n_cols: int = 20) -> list[dict]:
    """One 'fat' table with n_cols columns plus a simple companion table."""
    fat_cols = [_make_col("id", is_pk=True)] + [
        _make_col(f"col_{i}") for i in range(1, n_cols)
    ]
    return [
        {"name": "fat_table", "columns": fat_cols},
        {
            "name": "slim_table",
            "columns": [_make_col("id", is_pk=True), _make_col("name", "varchar")],
        },
    ]


def _synonym_tables_info() -> list[dict]:
    """15 unrelated filler tables followed by 'client'.

    With hybrid OFF: BM25 gives zero signal → fallback takes first MAX_TABLES=12
    tables → 'client' (position 15) is NOT included.

    With hybrid ON: vector search lifts 'client' via customer↔client mapping →
    seeds include 'client' → it appears in the prompt.
    """
    fillers = [
        {
            "name": f"table_{i}",
            "columns": [
                _make_col("id", is_pk=True),
                _make_col(f"data_{i}"),
            ],
        }
        for i in range(15)
    ]
    client_table = {
        "name": "client",
        "columns": [
            _make_col("id", is_pk=True),
            _make_col("name", "varchar"),
            _make_col("email", "varchar"),
        ],
    }
    return fillers + [client_table]


# ---------------------------------------------------------------------------
# Common patch helpers
# ---------------------------------------------------------------------------


def _patch_inspector(
    monkeypatch, gen: SQLGenerator, tables_info: list[dict]
) -> None:
    """Patch the DB-touching methods on the schema inspector."""

    async def fake_tables(*a, **k):
        return tables_info

    async def fake_fks(*a, **k):
        return []

    async def fake_hash(*a, **k):
        return 42

    async def fake_sample(conn, table_name, limit=1, db_type="postgresql"):
        return [{"id": 1, "name": "x"}]

    monkeypatch.setattr(gen.schema_inspector, "_get_all_tables_info", fake_tables)
    monkeypatch.setattr(gen.schema_inspector, "_get_foreign_keys", fake_fks)
    monkeypatch.setattr(gen.schema_inspector, "get_schema_version", fake_hash)
    monkeypatch.setattr(gen.schema_inspector, "_get_sample_rows", fake_sample)


def _patch_ollama(monkeypatch) -> dict:
    """Patch generate_with_config to capture the prompt and return canned SQL."""
    captured: dict = {}

    async def fake_generate(prompt, *args, **kwargs):
        captured["prompt"] = prompt
        return "```sql\nSELECT * FROM client;\n```"

    monkeypatch.setattr(
        "app.core.ai.ollama_sql_generator.generate_with_config",
        fake_generate,
    )
    return captured


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_settings_after_each():
    """Ensure settings LRU cache is cleared after every test."""
    yield
    get_settings.cache_clear()


@pytest.fixture
def patched_generator_hybrid_on(monkeypatch, tmp_path):
    """SQLGenerator with HYBRID_RETRIEVAL_ENABLED=True and FakeEmbedder injected."""
    monkeypatch.setenv("EMBEDDING_INDEX_DIR", str(tmp_path / "embeddings"))
    monkeypatch.setenv("HYBRID_RETRIEVAL_ENABLED", "True")
    get_settings.cache_clear()

    gen = SQLGenerator()
    # Inject FakeEmbedder that maps 'customer' and 'client' to the same vector
    gen.schema_inspector._hybrid._embedder = FakeEmbedder(
        mapping={
            "customer": [1.0, 0.0, 0.0, 0.0],
            "client": [1.0, 0.0, 0.0, 0.0],
        }
    )
    return gen


@pytest.fixture
def patched_generator_hybrid_off(monkeypatch, tmp_path):
    """SQLGenerator with HYBRID_RETRIEVAL_ENABLED=False (BM25-only path)."""
    monkeypatch.setenv("EMBEDDING_INDEX_DIR", str(tmp_path / "embeddings"))
    monkeypatch.setenv("HYBRID_RETRIEVAL_ENABLED", "False")
    get_settings.cache_clear()
    return SQLGenerator()


# ---------------------------------------------------------------------------
# Test 1: Semantic-mismatch question routes to the right table
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_semantic_mismatch_routes_to_client_table(
    monkeypatch, patched_generator_hybrid_on
):
    """With hybrid ON, 'customers' query finds the 'client' table via vector.

    BM25 gives zero score for 'client' when question says 'customers'.
    The FakeEmbedder maps 'customer' and 'client' to the same vector space →
    vector search lifts 'client' into the seed set → appears in the prompt.

    Uses a 16-table schema where 'client' is at position 15 (outside the
    BM25 fallback window of MAX_TABLES=12), so only the vector path can
    bring it in.
    """
    gen = patched_generator_hybrid_on
    tables_info = _synonym_tables_info()
    _patch_inspector(monkeypatch, gen, tables_info)
    captured = _patch_ollama(monkeypatch)

    conn = AsyncMock()
    sql, _ = await gen.generate_sql(
        question="show me all customers",
        connection=conn,
        db_id="test_db",
        read_only=True,
    )

    assert sql == "SELECT * FROM client;"
    assert "CREATE TABLE client" in captured["prompt"], (
        "Expected 'CREATE TABLE client' in prompt when hybrid retrieval is enabled "
        "and embedder maps 'customer' semantically to 'client'"
    )


# ---------------------------------------------------------------------------
# Test 2: Prompt contains pruned columns + 1 sample row line per table
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pruned_columns_and_sample_rows_in_prompt(
    monkeypatch, tmp_path
):
    """With hybrid ON, fat table (20 cols) is pruned to MAX_COLS_PER_TABLE=15.

    Column pruning logic:
      - PK column (id) is always kept (mandatory).
      - Top-N scoring fills remaining slots up to max_cols_per_table.
      - `above_threshold` adds extra columns if score >= col_score_threshold.

    To make pruning deterministic, we set col_score_threshold=2.0 (higher than
    max possible cosine score of 1.0), so the 'above_threshold' rule never fires
    and only mandatory + top-N determine the kept set.  With 1 PK column and
    max_cols_per_table=15, exactly 15 columns are kept regardless of scores.

    Also verifies sample rows are injected into the prompt.
    """
    monkeypatch.setenv("EMBEDDING_INDEX_DIR", str(tmp_path / "embeddings"))
    monkeypatch.setenv("HYBRID_RETRIEVAL_ENABLED", "True")
    get_settings.cache_clear()

    gen = SQLGenerator()

    # FakeEmbedder: all docs and query get the same vector — every column
    # has score 1.0.  With threshold=2.0 the 'above_threshold' rule never
    # fires so pruner caps strictly at max_cols_per_table (15).
    gen.schema_inspector._hybrid._embedder = FakeEmbedder()  # default: all [0,0,0,1]
    # Override col_score_threshold so no column is lifted via the threshold rule
    gen.schema_inspector._hybrid.col_score_threshold = 2.0

    n_cols = 20  # more than MAX_COLS_PER_TABLE=15
    tables_info = _large_tables_info(n_cols=n_cols)
    _patch_inspector(monkeypatch, gen, tables_info)
    captured = _patch_ollama(monkeypatch)

    conn = AsyncMock()
    await gen.generate_sql(
        question="list all fat table records",
        connection=conn,
        db_id="test_db",
        read_only=True,
    )

    assert "prompt" in captured, "generate_with_config was never called"
    prompt = captured["prompt"]

    # --- Column count assertion ---
    match = re.search(
        r"CREATE TABLE fat_table \((.*?)\);",
        prompt,
        re.DOTALL,
    )
    assert match, "CREATE TABLE fat_table not found in prompt"

    block = match.group(1)
    # Count actual column definition lines (non-empty, non-FK lines)
    col_lines = [
        ln.strip()
        for ln in block.splitlines()
        if ln.strip() and not ln.strip().startswith("FOREIGN")
    ]
    assert len(col_lines) <= 15, (
        f"Expected at most 15 column lines in pruned fat_table block, "
        f"got {len(col_lines)}: {col_lines}"
    )

    # --- Sample rows assertion ---
    assert "-- Sample rows from" in prompt, "Expected sample rows header in prompt"

    lines = prompt.splitlines()
    sample_header_indices = [
        i for i, ln in enumerate(lines) if ln.startswith("-- Sample rows from")
    ]
    assert sample_header_indices, "No '-- Sample rows from' line found"
    first_header_idx = sample_header_indices[0]
    assert first_header_idx + 1 < len(lines), "Sample rows header has no following line"
    assert lines[first_header_idx + 1].startswith("--   "), (
        f"Expected sample row line starting with '--   ', "
        f"got: {lines[first_header_idx + 1]!r}"
    )


# ---------------------------------------------------------------------------
# Test 3: HYBRID_RETRIEVAL_ENABLED=false regression guard
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_hybrid_off_client_not_in_prompt_via_bm25_only(
    monkeypatch, patched_generator_hybrid_off
):
    """With hybrid OFF, BM25-only path cannot lift 'client' via semantic matching.

    Using the synonym schema (15 filler tables then 'client'), BM25 gives zero
    signal for 'customers' → fallback picks the first MAX_TABLES=12 tables →
    'client' is at position 15 → excluded from the prompt.

    Regression guard from plan §10: "With HYBRID_RETRIEVAL_ENABLED=false it
    [client] does not [appear in the prompt]."
    """
    gen = patched_generator_hybrid_off
    tables_info = _synonym_tables_info()
    _patch_inspector(monkeypatch, gen, tables_info)
    captured = _patch_ollama(monkeypatch)

    conn = AsyncMock()
    await gen.generate_sql(
        question="show me all customers",
        connection=conn,
        db_id="test_db",
        read_only=True,
    )

    assert "prompt" in captured, "generate_with_config was never called"
    assert "CREATE TABLE client" not in captured["prompt"], (
        "With HYBRID_RETRIEVAL_ENABLED=False, 'client' should NOT appear in "
        "the prompt when it is outside the BM25 fallback window "
        "(first MAX_TABLES=12 tables)"
    )


@pytest.mark.asyncio
async def test_hybrid_off_full_columns_not_pruned(
    monkeypatch, patched_generator_hybrid_off
):
    """With hybrid OFF, column pruning is skipped — all columns appear in prompt.

    With 20 columns and no vector index, the pruner is a passthrough and every
    column should be present in the generated prompt.
    """
    gen = patched_generator_hybrid_off
    n_cols = 20
    tables_info = _large_tables_info(n_cols=n_cols)
    _patch_inspector(monkeypatch, gen, tables_info)
    captured = _patch_ollama(monkeypatch)

    conn = AsyncMock()
    await gen.generate_sql(
        question="list all fat table records",
        connection=conn,
        db_id="test_db",
        read_only=True,
    )

    prompt = captured["prompt"]
    match = re.search(
        r"CREATE TABLE fat_table \((.*?)\);",
        prompt,
        re.DOTALL,
    )
    assert match, "CREATE TABLE fat_table not found in prompt"

    block = match.group(1)
    col_lines = [
        ln.strip()
        for ln in block.splitlines()
        if ln.strip() and not ln.strip().startswith("FOREIGN")
    ]
    # With pruning skipped, we expect all n_cols columns to be present
    assert len(col_lines) == n_cols, (
        f"With hybrid OFF, expected all {n_cols} columns in prompt, "
        f"got {len(col_lines)}"
    )
