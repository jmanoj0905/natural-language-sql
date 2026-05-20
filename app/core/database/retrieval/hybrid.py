"""HybridRetriever — composes the full schema-retrieval pipeline.

Pipeline (per plan §4.2):
  BM25 → Vector (table + path search) → RRF fuse → FK expand → Column prune
  → Sample rows → format_schema_context
"""

from __future__ import annotations

import asyncio
import glob
import os
import time
from pathlib import Path
from typing import Awaitable, Callable, Optional

import numpy as np

from app.core.ai.schema_embedder import EmbedderUnavailableError, SchemaEmbedder
from app.core.database.retrieval.bm25 import BM25Ranker
from app.core.database.retrieval.column_pruner import ColumnPruner
from app.core.database.retrieval.corpus import SchemaCorpusBuilder
from app.core.database.retrieval.fk_expander import expand_with_fks
from app.core.database.retrieval.formatter import format_schema_context
from app.core.database.retrieval.progress import ProgressEmitter, ProgressEvent
from app.core.database.retrieval.rrf import rrf_fuse
from app.core.database.retrieval.vector_index import VectorIndex
from app.utils.logger import get_logger

logger = get_logger(__name__)

SampleRowFetcher = Callable[[str], Awaitable[list[dict]]]


class HybridRetriever:
    """Compose BM25 + vector + FK expansion + column pruning into one call."""

    def __init__(
        self,
        embedder: Optional[SchemaEmbedder],
        index_dir: Path,
        max_seed_tables: int = 5,
        max_tables: int = 12,
        max_cols_per_table: int = 15,
        col_score_threshold: float = 0.25,
        rrf_k: int = 60,
        include_sample_rows: bool = True,
        hybrid_enabled: bool = True,
    ) -> None:
        self._embedder = embedder
        self.index_dir = Path(index_dir)
        self.max_seed_tables = max_seed_tables
        self.max_tables = max_tables
        self.max_cols_per_table = max_cols_per_table
        self.col_score_threshold = col_score_threshold
        self.rrf_k = rrf_k
        self.include_sample_rows = include_sample_rows
        self.hybrid_enabled = hybrid_enabled

        # Per-db_id locks to prevent concurrent rebuilds.
        self._locks: dict[str, asyncio.Lock] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def build_context(
        self,
        *,
        question: str,
        db_id: str,
        schema_hash: int,
        tables_info: list[dict],
        foreign_keys: list[dict],
        sample_row_fetcher: Optional[SampleRowFetcher] = None,
        progress: Optional[ProgressEmitter] = None,
    ) -> str:
        """Build a schema-context string for the given question and database.

        Returns a formatted schema context suitable for injection into an AI
        prompt.
        """

        # Step 1 — Empty guard
        if not tables_info:
            return format_schema_context([], [], None, False)

        # Step 2 — Table lookup
        table_lookup: dict[str, dict] = {t["name"]: t for t in tables_info}

        # ------------------------------------------------------------------
        # Step 3 — BM25 ranking
        # ------------------------------------------------------------------
        t0 = time.monotonic()
        bm25_scores = BM25Ranker().rank_tables(question, tables_info)
        bm25_rank = [s.name for s in bm25_scores if s.score > 0]
        bm25_ms = int((time.monotonic() - t0) * 1000)

        await _emit(
            progress,
            ProgressEvent(
                stage="schema.retrieve.bm25",
                status="completed",
                duration_ms=bm25_ms,
                meta={"matched_tables": len(bm25_rank)},
            ),
        )

        # ------------------------------------------------------------------
        # Step 4 — Decide whether to use the vector path
        # ------------------------------------------------------------------
        use_vector = self.hybrid_enabled and self._embedder is not None

        index: Optional[VectorIndex] = None
        index_status: str = "unavailable"  # "built" | "loaded" | "unavailable"

        if use_vector:
            t_ensure = time.monotonic()
            index, index_status = await self._ensure_index(
                db_id, schema_hash, tables_info, foreign_keys
            )
            ensure_ms = int((time.monotonic() - t_ensure) * 1000)
            if index is None:
                use_vector = False

        # Emit schema.embed.build — reflects whether a fresh index was built,
        # loaded from disk, or not applicable (BM25-only path).
        if use_vector or index_status in ("built", "loaded"):
            if index_status == "built":
                await _emit(
                    progress,
                    ProgressEvent(
                        stage="schema.embed.build",
                        status="completed",
                        duration_ms=ensure_ms,
                    ),
                )
            else:
                # "loaded" or "unavailable" (embed failed but we tried)
                await _emit(
                    progress,
                    ProgressEvent(stage="schema.embed.build", status="skipped"),
                )
        else:
            # BM25-only path (hybrid_enabled=False or embedder is None) —
            # vector index was never attempted.
            await _emit(
                progress,
                ProgressEvent(stage="schema.embed.build", status="skipped"),
            )

        # ------------------------------------------------------------------
        # Step 5 — Vector search + RRF fusion
        # ------------------------------------------------------------------
        q_vec: Optional[np.ndarray] = None
        fused: list[str]

        if use_vector and index is not None:
            t0 = time.monotonic()
            try:
                q_vec = self._embedder.embed([question])[0]  # shape (DIM,)
            except EmbedderUnavailableError as exc:
                logger.warning(
                    "hybrid_retriever_embed_query_failed",
                    error=str(exc),
                )
                use_vector = False
                q_vec = None

        if use_vector and index is not None and q_vec is not None:
            # Table-level vector search
            table_rank: list[str] = [
                t for (t, _score) in index.search(q_vec, k=20, kind="tables")
            ]

            # Path-level vector search → expand each (tableA, tableB) pair
            path_expanded_seen: set[str] = set()
            path_expanded: list[str] = []
            for (table_a, table_b), _score in index.search(q_vec, k=10, kind="paths"):
                for tbl in (table_a, table_b):
                    if tbl not in path_expanded_seen:
                        path_expanded.append(tbl)
                        path_expanded_seen.add(tbl)

            vector_ms = int((time.monotonic() - t0) * 1000)
            await _emit(
                progress,
                ProgressEvent(
                    stage="schema.retrieve.vector",
                    status="completed",
                    duration_ms=vector_ms,
                ),
            )

            t0 = time.monotonic()
            fused = rrf_fuse([bm25_rank, table_rank, path_expanded], k=self.rrf_k)
            fuse_ms = int((time.monotonic() - t0) * 1000)
            await _emit(
                progress,
                ProgressEvent(
                    stage="schema.retrieve.fuse",
                    status="completed",
                    duration_ms=fuse_ms,
                ),
            )

        else:
            # BM25-only path (no vector signal available)
            fused = bm25_rank
            q_vec = None
            index = None

            await _emit(
                progress,
                ProgressEvent(stage="schema.retrieve.vector", status="skipped"),
            )
            await _emit(
                progress,
                ProgressEvent(stage="schema.retrieve.fuse", status="skipped"),
            )

        # ------------------------------------------------------------------
        # Step 7 — Seed selection + FK expansion
        # ------------------------------------------------------------------
        if not fused:
            fallback_used = True
            selected_names = [t["name"] for t in tables_info[: self.max_tables]]
        else:
            fallback_used = False
            seeds = fused[: self.max_seed_tables]
            selected_names = expand_with_fks(seeds, foreign_keys, table_lookup)[
                : self.max_tables
            ]

        # Step 8 — Build selected_tables list
        selected_tables = [
            table_lookup[n] for n in selected_names if n in table_lookup
        ]

        # ------------------------------------------------------------------
        # Step 9 — Column pruning
        # ------------------------------------------------------------------
        t0 = time.monotonic()
        if q_vec is not None and index is not None:
            pruned = ColumnPruner(
                max_cols_per_table=self.max_cols_per_table,
                col_score_threshold=self.col_score_threshold,
            ).prune(question, q_vec, selected_tables, index)
            prune_ms = int((time.monotonic() - t0) * 1000)
            await _emit(
                progress,
                ProgressEvent(
                    stage="schema.prune",
                    status="completed",
                    duration_ms=prune_ms,
                ),
            )
        else:
            pruned = selected_tables
            await _emit(
                progress,
                ProgressEvent(stage="schema.prune", status="skipped"),
            )

        # ------------------------------------------------------------------
        # Step 10 — Sample rows
        # ------------------------------------------------------------------
        t0 = time.monotonic()
        samples: dict[str, list[dict]] = {}

        if self.include_sample_rows and sample_row_fetcher is not None:
            for name in selected_names:
                try:
                    rows = await sample_row_fetcher(name)
                    samples[name] = rows
                except Exception as exc:
                    logger.warning(
                        "sample_row_fetch_error",
                        table=name,
                        error=str(exc),
                    )

        samples_ms = int((time.monotonic() - t0) * 1000)
        await _emit(
            progress,
            ProgressEvent(
                stage="schema.samples",
                status="completed",
                duration_ms=samples_ms,
            ),
        )

        # Step 11 — Format and return
        return format_schema_context(
            pruned,
            foreign_keys,
            samples if samples else None,
            fallback_used,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _ensure_index(
        self,
        db_id: str,
        schema_hash: int,
        tables_info: list[dict],
        foreign_keys: list[dict],
    ) -> tuple[Optional[VectorIndex], str]:
        """Load index from disk or build and persist it.

        Protected by a per-db_id asyncio.Lock so concurrent calls don't
        trigger parallel rebuilds.

        Returns a tuple of (index, status) where status is one of:
          - "built"       — a fresh index was built and saved.
          - "loaded"      — an existing index was loaded from disk.
          - "unavailable" — the embedder raised EmbedderUnavailableError.
        """
        # Lazy-create the lock
        if db_id not in self._locks:
            self._locks[db_id] = asyncio.Lock()

        lock = self._locks[db_id]

        async with lock:
            try:
                return await self._ensure_index_locked(
                    db_id, schema_hash, tables_info, foreign_keys
                )
            except EmbedderUnavailableError as exc:
                logger.warning(
                    "hybrid_retriever_embedder_unavailable",
                    db_id=db_id,
                    error=str(exc),
                )
                return None, "unavailable"

    async def _ensure_index_locked(
        self,
        db_id: str,
        schema_hash: int,
        tables_info: list[dict],
        foreign_keys: list[dict],
    ) -> tuple[Optional[VectorIndex], str]:
        """Must be called under the db_id lock.

        Returns (index, status) — see _ensure_index for status values.
        """
        model_safe = self._embedder.MODEL.replace("/", "_")
        filename = f"{db_id}__{schema_hash}__{model_safe}.npz"
        path = self.index_dir / filename

        # Attempt to load from disk
        if path.exists():
            try:
                index = VectorIndex.load(path)
                return index, "loaded"
            except Exception as exc:
                logger.warning(
                    "vector_index_load_failed_rebuilding",
                    path=str(path),
                    error=str(exc),
                )
                # Corrupt file — delete and rebuild below
                try:
                    os.remove(path)
                except OSError:
                    pass

        # Build the index
        os.makedirs(self.index_dir, exist_ok=True)

        corpus = SchemaCorpusBuilder().build(tables_info, foreign_keys)
        dim = SchemaEmbedder.DIM

        # Embed table docs
        if corpus.table_docs:
            table_texts = [doc for (_, doc) in corpus.table_docs]
            table_vecs = self._embedder.embed(table_texts)
        else:
            table_vecs = np.zeros((0, dim), dtype=np.float32)

        # Embed column docs
        if corpus.column_docs:
            column_texts = [doc for (_, doc) in corpus.column_docs]
            column_vecs = self._embedder.embed(column_texts)
        else:
            column_vecs = np.zeros((0, dim), dtype=np.float32)

        # Embed path docs
        if corpus.path_docs:
            path_texts = [doc for (_, doc) in corpus.path_docs]
            path_vecs = self._embedder.embed(path_texts)
        else:
            path_vecs = np.zeros((0, dim), dtype=np.float32)

        index = VectorIndex(
            table_vecs=table_vecs,
            column_vecs=column_vecs,
            path_vecs=path_vecs,
            table_ids=[t for (t, _) in corpus.table_docs],
            column_ids=[c for (c, _) in corpus.column_docs],
            path_ids=[p for (p, _) in corpus.path_docs],
            schema_hash=schema_hash,
            model_name=self._embedder.MODEL,
        )
        index.save(path)

        # Cleanup: keep at most 3 index files per db_id, delete older ones.
        self._cleanup_old_indexes(db_id, keep=3)

        return index, "built"

    def _cleanup_old_indexes(self, db_id: str, keep: int = 3) -> None:
        """Delete oldest index files for *db_id*, keeping the *keep* newest."""
        pattern = str(self.index_dir / f"{db_id}__*.npz")
        files = glob.glob(pattern)
        if len(files) <= keep:
            return
        # Sort by mtime, newest first
        files.sort(key=lambda f: os.path.getmtime(f), reverse=True)
        for old_file in files[keep:]:
            try:
                os.remove(old_file)
                logger.debug("vector_index_old_file_removed", path=old_file)
            except OSError as exc:
                logger.warning(
                    "vector_index_cleanup_error",
                    path=old_file,
                    error=str(exc),
                )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _emit(
    progress: Optional[ProgressEmitter],
    event: ProgressEvent,
) -> None:
    """Safely call the progress emitter if provided."""
    if progress is not None:
        await progress(event)
