from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import numpy as np


@dataclass
class VectorIndex:
    table_vecs:  np.ndarray          # (N_t, DIM)
    column_vecs: np.ndarray          # (N_c, DIM)
    path_vecs:   np.ndarray          # (N_p, DIM)
    table_ids:   list[str]
    column_ids:  list[tuple[str, str]]
    path_ids:    list[tuple[str, str]]
    schema_hash: int
    model_name:  str

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self, path: Path | str) -> None:
        """Persist this index to *path* (numpy adds .npz if absent)."""
        p = Path(path)
        # If caller already provided .npz extension, strip it so numpy
        # doesn't double-append and produce .npz.npz.
        if p.suffix == ".npz":
            p = p.with_suffix("")

        np.savez_compressed(
            str(p),
            table_vecs=self.table_vecs,
            column_vecs=self.column_vecs,
            path_vecs=self.path_vecs,
            table_ids=np.array(self.table_ids, dtype=object),
            column_ids=np.array(self.column_ids, dtype=object),
            path_ids=np.array(self.path_ids, dtype=object),
            schema_hash=np.int64(self.schema_hash),
            model_name=np.str_(self.model_name),
        )

    @classmethod
    def load(cls, path: Path | str) -> "VectorIndex":
        """Load a previously saved VectorIndex from *path*.

        Raises:
            ValueError: if the file is missing required keys.
            Any numpy exception if the file is corrupt.
        """
        data = np.load(str(path), allow_pickle=True)

        required = {
            "table_vecs", "column_vecs", "path_vecs",
            "table_ids", "column_ids", "path_ids",
            "schema_hash", "model_name",
        }
        missing = required - set(data.files)
        if missing:
            raise ValueError(f"VectorIndex file missing keys: {missing}")

        # Rehydrate ids
        table_ids: list[str] = [str(x) for x in data["table_ids"].tolist()]

        raw_col = data["column_ids"].tolist()
        column_ids: list[tuple[str, str]] = [
            (str(a), str(b)) for a, b in (raw_col or [])
        ]

        raw_path = data["path_ids"].tolist()
        path_ids: list[tuple[str, str]] = [
            (str(a), str(b)) for a, b in (raw_path or [])
        ]

        return cls(
            table_vecs=data["table_vecs"],
            column_vecs=data["column_vecs"],
            path_vecs=data["path_vecs"],
            table_ids=table_ids,
            column_ids=column_ids,
            path_ids=path_ids,
            schema_hash=int(data["schema_hash"]),
            model_name=str(data["model_name"]),
        )

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(
        self,
        q: np.ndarray,
        k: int,
        kind: Literal["tables", "columns", "paths"],
    ) -> list[tuple[Any, float]]:
        """Cosine similarity search (dot product on pre-normalised vectors).

        Both *q* and the stored vectors must be L2-normalised.

        Args:
            q:    Query vector, shape (DIM,).
            k:    Number of top results to return.
            kind: Which set of vectors to search.

        Returns:
            List of (id, score) sorted by score descending.
            Returns ``[]`` when the relevant matrix is empty.
        """
        if kind == "tables":
            vecs = self.table_vecs
            ids = self.table_ids
        elif kind == "columns":
            vecs = self.column_vecs
            ids = self.column_ids
        else:
            vecs = self.path_vecs
            ids = self.path_ids

        if vecs.shape[0] == 0:
            return []

        scores: np.ndarray = vecs @ q          # dot product → cosine (pre-normed)
        k_actual = min(k, len(scores))
        top_indices = np.argsort(scores)[::-1][:k_actual]

        return [(ids[int(i)], float(scores[i])) for i in top_indices]
