"""Tests for VectorIndex — TDD: tests written before implementation."""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest

from app.core.database.retrieval.vector_index import VectorIndex


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

DIM = 4


def unit(v: list[float]) -> np.ndarray:
    """Return an L2-normalised float32 vector."""
    arr = np.array(v, dtype=np.float32)
    return arr / np.linalg.norm(arr)


def make_index(
    *,
    n_tables: int = 3,
    n_columns: int = 3,
    n_paths: int = 2,
    schema_hash: int = 42,
    model_name: str = "test-model",
) -> VectorIndex:
    """Build a small VectorIndex with predictable unit vectors."""
    rng = np.random.default_rng(0)

    def rand_unit_matrix(n: int) -> np.ndarray:
        if n == 0:
            return np.empty((0, DIM), dtype=np.float32)
        m = rng.standard_normal((n, DIM)).astype(np.float32)
        norms = np.linalg.norm(m, axis=1, keepdims=True)
        return m / norms

    table_vecs = rand_unit_matrix(n_tables)
    column_vecs = rand_unit_matrix(n_columns)
    path_vecs = rand_unit_matrix(n_paths)

    table_ids = [f"tbl_{i}" for i in range(n_tables)]
    column_ids = [(f"tbl_{i % 2}", f"col_{i}") for i in range(n_columns)]
    path_ids = [(f"tbl_{i}", f"tbl_{i+1}") for i in range(n_paths)]

    return VectorIndex(
        table_vecs=table_vecs,
        column_vecs=column_vecs,
        path_vecs=path_vecs,
        table_ids=table_ids,
        column_ids=column_ids,
        path_ids=path_ids,
        schema_hash=schema_hash,
        model_name=model_name,
    )


# ---------------------------------------------------------------------------
# 1. Save / load round-trip
# ---------------------------------------------------------------------------


def test_save_load_arrays_roundtrip(tmp_path: Path) -> None:
    idx = make_index()
    fpath = tmp_path / "idx"
    idx.save(fpath)

    loaded = VectorIndex.load(tmp_path / "idx.npz")

    np.testing.assert_array_almost_equal(loaded.table_vecs, idx.table_vecs)
    np.testing.assert_array_almost_equal(loaded.column_vecs, idx.column_vecs)
    np.testing.assert_array_almost_equal(loaded.path_vecs, idx.path_vecs)


def test_save_load_table_ids_roundtrip(tmp_path: Path) -> None:
    idx = make_index()
    idx.save(tmp_path / "idx")
    loaded = VectorIndex.load(tmp_path / "idx.npz")

    assert loaded.table_ids == idx.table_ids
    assert isinstance(loaded.table_ids, list)
    assert isinstance(loaded.table_ids[0], str)


def test_save_load_column_ids_roundtrip(tmp_path: Path) -> None:
    idx = make_index()
    idx.save(tmp_path / "idx")
    loaded = VectorIndex.load(tmp_path / "idx.npz")

    assert loaded.column_ids == idx.column_ids
    assert isinstance(loaded.column_ids, list)
    first = loaded.column_ids[0]
    assert isinstance(first, tuple)
    assert len(first) == 2


def test_save_load_path_ids_roundtrip(tmp_path: Path) -> None:
    idx = make_index()
    idx.save(tmp_path / "idx")
    loaded = VectorIndex.load(tmp_path / "idx.npz")

    assert loaded.path_ids == idx.path_ids
    assert isinstance(loaded.path_ids, list)
    first = loaded.path_ids[0]
    assert isinstance(first, tuple)
    assert len(first) == 2


def test_save_load_scalars_roundtrip(tmp_path: Path) -> None:
    idx = make_index(schema_hash=99999, model_name="my-embed-v2")
    idx.save(tmp_path / "idx")
    loaded = VectorIndex.load(tmp_path / "idx.npz")

    assert loaded.schema_hash == 99999
    assert isinstance(loaded.schema_hash, int)
    assert loaded.model_name == "my-embed-v2"
    assert isinstance(loaded.model_name, str)


def test_save_accepts_path_with_npz_extension(tmp_path: Path) -> None:
    """save() must work when caller already appends .npz."""
    idx = make_index()
    idx.save(tmp_path / "idx.npz")
    loaded = VectorIndex.load(tmp_path / "idx.npz")
    assert loaded.table_ids == idx.table_ids


# ---------------------------------------------------------------------------
# 2. search — tables
# ---------------------------------------------------------------------------


def test_search_tables_returns_top_k_descending(tmp_path: Path) -> None:
    """Top-k results come back sorted highest cosine first."""
    # Three table vectors; query is identical to table_vecs[1] → score 1.0
    t0 = unit([1.0, 0.0, 0.0, 0.0])
    t1 = unit([0.0, 1.0, 0.0, 0.0])
    t2 = unit([0.0, 0.0, 1.0, 0.0])

    idx = VectorIndex(
        table_vecs=np.stack([t0, t1, t2]),
        column_vecs=np.empty((0, DIM), dtype=np.float32),
        path_vecs=np.empty((0, DIM), dtype=np.float32),
        table_ids=["A", "B", "C"],
        column_ids=[],
        path_ids=[],
        schema_hash=0,
        model_name="test",
    )

    results = idx.search(t1, k=2, kind="tables")

    assert len(results) == 2
    ids = [r[0] for r in results]
    scores = [r[1] for r in results]

    assert ids[0] == "B"
    assert math.isclose(scores[0], 1.0, abs_tol=1e-5)
    # Scores must be descending
    assert scores[0] >= scores[1]


def test_search_tables_score_type_is_float(tmp_path: Path) -> None:
    idx = make_index()
    q = unit([1.0, 0.0, 0.0, 0.0])
    results = idx.search(q, k=1, kind="tables")
    assert len(results) == 1
    _, score = results[0]
    assert isinstance(score, float)


# ---------------------------------------------------------------------------
# 3. search — columns (tuple ids)
# ---------------------------------------------------------------------------


def test_search_columns_returns_tuple_ids() -> None:
    c0 = unit([1.0, 0.0, 0.0, 0.0])
    c1 = unit([0.0, 1.0, 0.0, 0.0])

    idx = VectorIndex(
        table_vecs=np.empty((0, DIM), dtype=np.float32),
        column_vecs=np.stack([c0, c1]),
        path_vecs=np.empty((0, DIM), dtype=np.float32),
        table_ids=[],
        column_ids=[("orders", "total"), ("customer", "name")],
        path_ids=[],
        schema_hash=0,
        model_name="test",
    )

    results = idx.search(c1, k=2, kind="columns")
    assert len(results) == 2
    top_id = results[0][0]
    assert top_id == ("customer", "name")
    assert isinstance(top_id, tuple)


# ---------------------------------------------------------------------------
# 4. search — paths (tuple ids)
# ---------------------------------------------------------------------------


def test_search_paths_returns_tuple_ids() -> None:
    p0 = unit([1.0, 0.0, 0.0, 0.0])
    p1 = unit([0.0, 1.0, 0.0, 0.0])

    idx = VectorIndex(
        table_vecs=np.empty((0, DIM), dtype=np.float32),
        column_vecs=np.empty((0, DIM), dtype=np.float32),
        path_vecs=np.stack([p0, p1]),
        table_ids=[],
        column_ids=[],
        path_ids=[("orders", "customer"), ("product", "orders")],
        schema_hash=0,
        model_name="test",
    )

    results = idx.search(p0, k=1, kind="paths")
    assert len(results) == 1
    top_id = results[0][0]
    assert top_id == ("orders", "customer")
    assert isinstance(top_id, tuple)


# ---------------------------------------------------------------------------
# 5. search — empty vecs → empty list
# ---------------------------------------------------------------------------


def test_search_empty_table_vecs_returns_empty() -> None:
    idx = VectorIndex(
        table_vecs=np.empty((0, DIM), dtype=np.float32),
        column_vecs=np.empty((0, DIM), dtype=np.float32),
        path_vecs=np.empty((0, DIM), dtype=np.float32),
        table_ids=[],
        column_ids=[],
        path_ids=[],
        schema_hash=0,
        model_name="test",
    )
    q = unit([1.0, 0.0, 0.0, 0.0])
    assert idx.search(q, k=5, kind="tables") == []
    assert idx.search(q, k=5, kind="columns") == []
    assert idx.search(q, k=5, kind="paths") == []


# ---------------------------------------------------------------------------
# 6. search — k > len(vecs) returns all rows
# ---------------------------------------------------------------------------


def test_search_k_larger_than_vecs_returns_all() -> None:
    t0 = unit([1.0, 0.0, 0.0, 0.0])
    t1 = unit([0.0, 1.0, 0.0, 0.0])

    idx = VectorIndex(
        table_vecs=np.stack([t0, t1]),
        column_vecs=np.empty((0, DIM), dtype=np.float32),
        path_vecs=np.empty((0, DIM), dtype=np.float32),
        table_ids=["X", "Y"],
        column_ids=[],
        path_ids=[],
        schema_hash=0,
        model_name="test",
    )

    results = idx.search(t0, k=100, kind="tables")
    assert len(results) == 2


# ---------------------------------------------------------------------------
# 7. search does not mutate query vector
# ---------------------------------------------------------------------------


def test_search_does_not_mutate_query_vector() -> None:
    idx = make_index()
    q = unit([1.0, 0.0, 0.0, 0.0])
    q_orig = q.copy()
    idx.search(q, k=2, kind="tables")
    np.testing.assert_array_equal(q, q_orig)


# ---------------------------------------------------------------------------
# 8. Corrupt file raises on load
# ---------------------------------------------------------------------------


def test_load_corrupt_file_raises(tmp_path: Path) -> None:
    bogus = tmp_path / "bogus.npz"
    bogus.write_bytes(b"not a numpy file at all \x00\x01\x02")

    with pytest.raises(Exception):
        VectorIndex.load(bogus)


# ---------------------------------------------------------------------------
# 9. Round-trip with path already containing .npz extension (load)
# ---------------------------------------------------------------------------


def test_load_accepts_path_without_npz_extension(tmp_path: Path) -> None:
    """load() called with no extension finds the .npz file numpy wrote."""
    idx = make_index()
    idx.save(tmp_path / "idx")
    # numpy wrote tmp_path/idx.npz; load without extension should work
    loaded = VectorIndex.load(tmp_path / "idx.npz")
    assert loaded.model_name == idx.model_name
