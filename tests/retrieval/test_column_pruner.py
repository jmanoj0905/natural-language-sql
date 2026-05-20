"""Tests for ColumnPruner — plan §7.1.

Tests first, implementation second (TDD).
"""
from __future__ import annotations

import numpy as np
import pytest

from app.core.database.retrieval.column_pruner import ColumnPruner


# ---------------------------------------------------------------------------
# FakeIndex — predictable dot-product scoring
# ---------------------------------------------------------------------------

class FakeIndex:
    """Minimal ColumnVectorIndex for testing — no real embeddings needed."""

    def __init__(
        self,
        column_ids: list[tuple[str, str]],
        column_vecs: np.ndarray,
    ):
        self.column_ids = column_ids
        self.column_vecs = column_vecs


def _l2_norm(v: np.ndarray) -> np.ndarray:
    """Return unit-length vector."""
    norm = np.linalg.norm(v)
    return v / norm if norm > 0 else v


def _make_index(
    column_ids: list[tuple[str, str]],
    raw_vecs: list[list[float]],
) -> FakeIndex:
    """Build a FakeIndex with L2-normalised row vectors."""
    arr = np.array(raw_vecs, dtype=np.float64)
    normed = np.array([_l2_norm(row) for row in arr], dtype=np.float64)
    return FakeIndex(column_ids, normed)


def _unit(v: list[float]) -> np.ndarray:
    return _l2_norm(np.array(v, dtype=np.float64))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _col(name: str, *, is_pk: bool = False, is_fk: bool = False, **kw) -> dict:
    d = {"name": name, "type": "varchar", **kw}
    if is_pk:
        d["is_pk"] = True
    if is_fk:
        d["is_fk"] = True
    return d


def _table(name: str, columns: list[dict]) -> dict:
    return {"name": name, "columns": columns}


# ---------------------------------------------------------------------------
# Passthrough when q_vec is None
# ---------------------------------------------------------------------------

class TestPassthrough:
    def test_qvec_none_returns_tables_unchanged(self):
        pruner = ColumnPruner(max_cols_per_table=2)
        tables = [_table("t", [_col("a"), _col("b"), _col("c")])]
        index = _make_index([("t", "a"), ("t", "b"), ("t", "c")], [[1, 0], [0, 1], [1, 1]])

        result = pruner.prune("q", None, tables, index)

        assert result == tables

    def test_index_none_returns_tables_unchanged(self):
        pruner = ColumnPruner(max_cols_per_table=2)
        tables = [_table("t", [_col("a"), _col("b"), _col("c")])]
        q_vec = _unit([1.0, 0.0])

        result = pruner.prune("q", q_vec, tables, None)

        assert result == tables

    def test_both_none_returns_tables_unchanged(self):
        pruner = ColumnPruner(max_cols_per_table=2)
        tables = [_table("t", [_col("a")])]

        result = pruner.prune("q", None, tables, None)

        assert result == tables


# ---------------------------------------------------------------------------
# Small table passthrough (len <= max_cols_per_table)
# ---------------------------------------------------------------------------

class TestSmallTablePassthrough:
    def test_table_at_cap_returned_unchanged(self):
        """len(columns) == max_cols_per_table → no pruning."""
        pruner = ColumnPruner(max_cols_per_table=3)
        cols = [_col("a"), _col("b"), _col("c")]
        tables = [_table("t", cols)]
        index = _make_index([("t", "a"), ("t", "b"), ("t", "c")], [[1, 0], [0, 1], [1, 1]])
        q_vec = _unit([1.0, 0.0])

        result = pruner.prune("q", q_vec, tables, index)

        assert result[0]["columns"] == cols

    def test_table_below_cap_returned_unchanged(self):
        pruner = ColumnPruner(max_cols_per_table=10)
        cols = [_col("x"), _col("y")]
        tables = [_table("t", cols)]
        index = _make_index([("t", "x"), ("t", "y")], [[1, 0], [0, 1]])
        q_vec = _unit([1.0, 0.0])

        result = pruner.prune("q", q_vec, tables, index)

        assert result[0]["columns"] == cols


# ---------------------------------------------------------------------------
# PK columns always kept
# ---------------------------------------------------------------------------

class TestPKAlwaysKept:
    def test_pk_column_kept_even_at_zero_score(self):
        """PK must be kept regardless of its similarity score."""
        # q_vec points along dim-0; pk_col lives on dim-1 (score ≈ 0)
        pruner = ColumnPruner(max_cols_per_table=2, col_score_threshold=0.5)
        cols = [
            _col("pk_col", is_pk=True),    # lives on dim-1 → score 0 against q_vec
            _col("hi_1"),                   # high score on dim-0
            _col("hi_2"),                   # high score on dim-0
            _col("lo_col"),                 # low score
        ]
        tables = [_table("t", cols)]
        index = _make_index(
            [("t", "pk_col"), ("t", "hi_1"), ("t", "hi_2"), ("t", "lo_col")],
            [[0, 1], [1, 0], [1, 0], [0.1, 0.9]],
        )
        q_vec = _unit([1.0, 0.0])

        result = pruner.prune("q", q_vec, tables, index)
        kept_names = [c["name"] for c in result[0]["columns"]]

        assert "pk_col" in kept_names

    def test_multiple_pk_columns_all_kept(self):
        pruner = ColumnPruner(max_cols_per_table=2)
        cols = [
            _col("pk1", is_pk=True),
            _col("pk2", is_pk=True),
            _col("regular_a"),
            _col("regular_b"),
            _col("regular_c"),
        ]
        tables = [_table("t", cols)]
        # All low similarity — only PKs should survive
        index = _make_index(
            [("t", c["name"]) for c in cols],
            [[0, 1]] * 5,
        )
        q_vec = _unit([1.0, 0.0])

        result = pruner.prune("q", q_vec, tables, index)
        kept_names = [c["name"] for c in result[0]["columns"]]

        assert "pk1" in kept_names
        assert "pk2" in kept_names


# ---------------------------------------------------------------------------
# FK columns always kept
# ---------------------------------------------------------------------------

class TestFKAlwaysKept:
    def test_fk_column_kept_even_at_zero_score(self):
        pruner = ColumnPruner(max_cols_per_table=2, col_score_threshold=0.5)
        cols = [
            _col("fk_col", is_fk=True),
            _col("hi_1"),
            _col("hi_2"),
            _col("lo_col"),
        ]
        tables = [_table("t", cols)]
        index = _make_index(
            [("t", "fk_col"), ("t", "hi_1"), ("t", "hi_2"), ("t", "lo_col")],
            [[0, 1], [1, 0], [1, 0], [0.1, 0.9]],
        )
        q_vec = _unit([1.0, 0.0])

        result = pruner.prune("q", q_vec, tables, index)
        kept_names = [c["name"] for c in result[0]["columns"]]

        assert "fk_col" in kept_names


# ---------------------------------------------------------------------------
# Threshold τ enforced
# ---------------------------------------------------------------------------

class TestThreshold:
    def test_column_above_threshold_kept_even_after_cap(self):
        """A column scoring >= threshold is included even when cap is filled by top-N."""
        # max_cols_per_table=3, col_score_threshold=0.5
        # We have 5 columns; top-2 by score + above-threshold column = 3 minimum
        # But the above-threshold column ranks 4th by score yet still must appear.
        pruner = ColumnPruner(max_cols_per_table=3, col_score_threshold=0.5)
        cols = [
            _col("s95"),  # score 0.95
            _col("s90"),  # score 0.90
            _col("s85"),  # score 0.85  ← will fill top-3
            _col("s60"),  # score 0.60  ← above threshold, must be kept too
            _col("s10"),  # score 0.10  ← below threshold, excluded
        ]
        tables = [_table("t", cols)]
        # q_vec = [1, 0]; each column vec is a unit vector with controlled cosine
        # Use a single-dimension dot product trick: vec[0] ≈ desired score
        index = _make_index(
            [("t", c["name"]) for c in cols],
            [[0.95, 0.312], [0.90, 0.436], [0.85, 0.527], [0.60, 0.800], [0.10, 0.995]],
        )
        q_vec = _unit([1.0, 0.0])

        result = pruner.prune("q", q_vec, tables, index)
        kept_names = [c["name"] for c in result[0]["columns"]]

        # s95, s90, s85 are top-3; s60 is above threshold so also kept; s10 excluded
        assert "s95" in kept_names
        assert "s90" in kept_names
        assert "s85" in kept_names
        assert "s60" in kept_names
        assert "s10" not in kept_names

    def test_column_below_threshold_excluded_when_cap_full(self):
        pruner = ColumnPruner(max_cols_per_table=2, col_score_threshold=0.5)
        cols = [_col("hi1"), _col("hi2"), _col("lo1"), _col("lo2")]
        tables = [_table("t", cols)]
        index = _make_index(
            [("t", c["name"]) for c in cols],
            [[0.9, 0.436], [0.8, 0.600], [0.2, 0.980], [0.1, 0.995]],
        )
        q_vec = _unit([1.0, 0.0])

        result = pruner.prune("q", q_vec, tables, index)
        kept_names = [c["name"] for c in result[0]["columns"]]

        assert "lo1" not in kept_names
        assert "lo2" not in kept_names


# ---------------------------------------------------------------------------
# Original column order preserved
# ---------------------------------------------------------------------------

class TestColumnOrder:
    def test_output_preserves_original_order(self):
        """Kept columns must appear in their original input order, not score order."""
        pruner = ColumnPruner(max_cols_per_table=2)
        # Columns in order: z(high score), a(low), m(high score)
        # After pruning (top-2), we keep z and m; z should still come before m.
        cols = [
            _col("z_high"),   # score 0.9  — position 0
            _col("a_low"),    # score 0.1  — position 1
            _col("m_high"),   # score 0.8  — position 2
            _col("b_low"),    # score 0.05 — position 3
        ]
        tables = [_table("t", cols)]
        index = _make_index(
            [("t", c["name"]) for c in cols],
            [[0.9, 0.436], [0.1, 0.995], [0.8, 0.600], [0.05, 0.999]],
        )
        q_vec = _unit([1.0, 0.0])

        result = pruner.prune("q", q_vec, tables, index)
        kept = result[0]["columns"]

        assert kept[0]["name"] == "z_high"
        assert kept[1]["name"] == "m_high"

    def test_pk_fk_positions_preserved(self):
        """PK/FK columns preserved in their original positions."""
        pruner = ColumnPruner(max_cols_per_table=2)
        cols = [
            _col("a_low"),              # position 0, low score
            _col("pk_col", is_pk=True), # position 1, low score but PK
            _col("hi_col"),             # position 2, high score
            _col("b_low"),              # position 3, low score
            _col("c_low"),              # position 4, low score
        ]
        tables = [_table("t", cols)]
        index = _make_index(
            [("t", c["name"]) for c in cols],
            [[0.1, 0.995], [0.0, 1.0], [0.9, 0.436], [0.1, 0.995], [0.1, 0.995]],
        )
        q_vec = _unit([1.0, 0.0])

        result = pruner.prune("q", q_vec, tables, index)
        kept = result[0]["columns"]
        kept_names = [c["name"] for c in kept]

        # pk_col (pos 1) must come before hi_col (pos 2) in output
        assert kept_names.index("pk_col") < kept_names.index("hi_col")


# ---------------------------------------------------------------------------
# Column not in index gets score 0.0
# ---------------------------------------------------------------------------

class TestMissingFromIndex:
    def test_column_missing_from_index_scores_zero(self):
        """Column absent from index gets score=0 (not an error)."""
        pruner = ColumnPruner(max_cols_per_table=1, col_score_threshold=0.9)
        cols = [_col("indexed_hi"), _col("not_in_index")]
        tables = [_table("t", cols)]
        # Only indexed_hi is in the index
        index = _make_index([("t", "indexed_hi")], [[1.0, 0.0]])
        q_vec = _unit([1.0, 0.0])

        result = pruner.prune("q", q_vec, tables, index)
        kept_names = [c["name"] for c in result[0]["columns"]]

        assert "indexed_hi" in kept_names
        assert "not_in_index" not in kept_names


# ---------------------------------------------------------------------------
# PK+FK deduplication
# ---------------------------------------------------------------------------

class TestDeduplication:
    def test_pk_fk_column_included_only_once(self):
        """A column that is both PK and FK should appear exactly once."""
        pruner = ColumnPruner(max_cols_per_table=2)
        cols = [
            _col("combo", is_pk=True, is_fk=True),
            _col("other_a"),
            _col("other_b"),
            _col("other_c"),
        ]
        tables = [_table("t", cols)]
        index = _make_index(
            [("t", c["name"]) for c in cols],
            [[0, 1], [1, 0], [1, 0], [0.1, 0.9]],
        )
        q_vec = _unit([1.0, 0.0])

        result = pruner.prune("q", q_vec, tables, index)
        kept_names = [c["name"] for c in result[0]["columns"]]

        assert kept_names.count("combo") == 1


# ---------------------------------------------------------------------------
# Empty columns list
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_empty_columns_returns_empty(self):
        pruner = ColumnPruner(max_cols_per_table=5)
        tables = [_table("t", [])]
        index = _make_index([], np.empty((0, 2), dtype=np.float64))
        q_vec = _unit([1.0, 0.0])

        result = pruner.prune("q", q_vec, tables, index)

        assert result[0]["columns"] == []

    def test_extra_table_level_keys_preserved(self):
        """Non-'columns' keys on the table dict must pass through unchanged."""
        pruner = ColumnPruner(max_cols_per_table=1)
        tables = [{"name": "t", "columns": [_col("a"), _col("b")], "schema": "public"}]
        index = _make_index([("t", "a"), ("t", "b")], [[1, 0], [0, 1]])
        q_vec = _unit([1.0, 0.0])

        result = pruner.prune("q", q_vec, tables, index)

        assert result[0].get("schema") == "public"

    def test_multiple_tables_each_pruned_independently(self):
        """Pruning is per-table; big table pruned, small table untouched."""
        pruner = ColumnPruner(max_cols_per_table=2)
        big_cols = [_col("a"), _col("b"), _col("c"), _col("d")]
        small_cols = [_col("x"), _col("y")]
        tables = [_table("big", big_cols), _table("small", small_cols)]
        index = _make_index(
            [("big", "a"), ("big", "b"), ("big", "c"), ("big", "d"),
             ("small", "x"), ("small", "y")],
            [[1, 0], [1, 0], [0, 1], [0, 1],
             [1, 0], [0, 1]],
        )
        q_vec = _unit([1.0, 0.0])

        result = pruner.prune("q", q_vec, tables, index)

        big_result = next(t for t in result if t["name"] == "big")
        small_result = next(t for t in result if t["name"] == "small")

        assert len(big_result["columns"]) == 2
        assert len(small_result["columns"]) == 2  # unchanged
