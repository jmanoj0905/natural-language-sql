"""ColumnPruner — prunes per-table column lists using vector similarity.

Given a query vector and a column vector index, keeps:
  1. All PK columns (is_pk=True) — always.
  2. All FK columns (is_fk=True) — always.
  3. Top-N highest-scoring columns until max_cols_per_table is reached.
  4. Any column scoring >= col_score_threshold, even beyond the cap.

Original column order is preserved in the output (no re-ordering by score).
"""
from __future__ import annotations

from typing import Any, Protocol

from app.core.database.retrieval.bm25 import _tokenize


class ColumnVectorIndex(Protocol):
    """Minimal interface — VectorIndex (T6) will satisfy this."""

    column_ids: list[tuple[str, str]]  # (table, column) in row order of column_vecs
    column_vecs: Any                   # np.ndarray; L2-normalised rows


class ColumnPruner:
    def __init__(
        self,
        max_cols_per_table: int = 15,
        col_score_threshold: float = 0.25,
    ):
        self.max_cols_per_table = max_cols_per_table
        self.col_score_threshold = col_score_threshold

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def prune(
        self,
        question: str,
        q_vec,                    # np.ndarray shape (DIM,), L2-normalised; or None
        selected_tables: list[dict],
        index,                    # ColumnVectorIndex; or None
    ) -> list[dict]:
        """Return a copy of selected_tables with columns possibly reduced.

        Passthrough conditions (table returned as-is):
          - q_vec is None, OR
          - index is None, OR
          - len(table["columns"]) <= max_cols_per_table
        """
        if q_vec is None or index is None:
            return list(selected_tables)

        # Build a lookup: (table, column) -> row index in the index
        id_to_row: dict[tuple[str, str], int] = {
            cid: row for row, cid in enumerate(index.column_ids)
        }

        q_tokens = set(_tokenize(question))

        result: list[dict] = []
        for table in selected_tables:
            result.append(self._prune_table(table, q_vec, index, id_to_row, q_tokens))
        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _prune_table(
        self,
        table: dict,
        q_vec,
        index,
        id_to_row: dict[tuple[str, str], int],
        q_tokens: set[str] | None = None,
    ) -> dict:
        columns: list[dict] = table.get("columns", [])

        # Short-circuit: nothing to prune
        if len(columns) <= self.max_cols_per_table:
            return table

        table_name: str = table["name"]

        # Compute per-column scores
        scored: list[tuple[int, float]] = []  # (original_index, score)
        for orig_idx, col in enumerate(columns):
            col_name = col["name"]
            row = id_to_row.get((table_name, col_name))
            if row is None:
                score = 0.0
            else:
                score = float(index.column_vecs[row] @ q_vec)
            scored.append((orig_idx, score))

        # --- Determine which columns to keep ---

        # Mandatory: PK / FK (always kept)
        mandatory: set[int] = {
            orig_idx
            for orig_idx, col in enumerate(columns)
            if col.get("is_pk") is True or col.get("is_fk") is True
        }

        # Lexical keep: columns whose name tokens overlap the question tokens
        if q_tokens:
            mandatory |= {
                orig_idx
                for orig_idx, col in enumerate(columns)
                if set(_tokenize(col["name"])) & q_tokens
            }

        # Top-N by score to fill up to max_cols_per_table
        sorted_by_score = sorted(scored, key=lambda t: t[1], reverse=True)
        top_n: set[int] = set()
        slots_remaining = self.max_cols_per_table - len(mandatory)
        for orig_idx, _score in sorted_by_score:
            if len(top_n | mandatory) >= self.max_cols_per_table:
                break
            if orig_idx not in mandatory:
                top_n.add(orig_idx)

        # Above-threshold: keep regardless of cap
        above_threshold: set[int] = {
            orig_idx
            for orig_idx, score in scored
            if score >= self.col_score_threshold and orig_idx not in mandatory
        }

        keep_indices = mandatory | top_n | above_threshold

        # Preserve original order
        kept_columns = [col for orig_idx, col in enumerate(columns) if orig_idx in keep_indices]

        # Build new table dict preserving all non-"columns" keys
        new_table = {k: v for k, v in table.items() if k != "columns"}
        new_table["columns"] = kept_columns
        return new_table
