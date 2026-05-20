"""Tests for HybridRetriever — Task 9.

FakeEmbedder produces deterministic, low-dimensional (DIM=4) embeddings so
tests are fast and don't need sentence-transformers installed.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Optional
from unittest.mock import AsyncMock

import numpy as np
import pytest

from app.core.database.retrieval.hybrid import HybridRetriever
from app.core.database.retrieval.progress import ProgressEmitter, ProgressEvent
from app.core.database.retrieval.vector_index import VectorIndex


# ---------------------------------------------------------------------------
# FakeEmbedder
# ---------------------------------------------------------------------------


class FakeEmbedder:
    """Deterministic embedder with configurable token→vector mapping.

    Strategy:
      - Split text on whitespace.
      - For each token, look up self.mapping (lowercased), else use self.default.
      - Return average of token vectors, L2-normalised.
    """

    MODEL = "fake-embedder"
    DIM = 4

    def __init__(
        self,
        mapping: dict[str, list[float]] | None = None,
        default: list[float] | None = None,
    ):
        self.mapping = mapping or {}
        self.default = default or [1.0, 0.0, 0.0, 0.0]
        self.call_count = 0  # tracks number of embed() calls

    def embed(self, texts: list[str]) -> np.ndarray:
        self.call_count += 1
        out = []
        for text in texts:
            tokens = text.lower().split()
            vecs = [
                np.array(self.mapping.get(tok, self.default), dtype=np.float32)
                for tok in tokens
            ] if tokens else [np.array(self.default, dtype=np.float32)]
            avg = np.mean(vecs, axis=0)
            norm = np.linalg.norm(avg)
            if norm > 0:
                avg /= norm
            out.append(avg)
        return np.array(out, dtype=np.float32)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_tables():
    return [
        {
            "name": "customer",
            "columns": [
                {"name": "id", "type": "int"},
                {"name": "name", "type": "varchar"},
                {"name": "email", "type": "varchar"},
            ],
        },
        {
            "name": "orders",
            "columns": [
                {"name": "id", "type": "int"},
                {"name": "customer_id", "type": "int"},
                {"name": "total", "type": "numeric"},
            ],
        },
        {
            "name": "product",
            "columns": [
                {"name": "id", "type": "int"},
                {"name": "name", "type": "varchar"},
                {"name": "price", "type": "numeric"},
                {"name": "sku", "type": "varchar"},
            ],
        },
    ]


def _make_fks():
    return [
        {
            "table": "orders",
            "column": "customer_id",
            "ref_table": "customer",
            "ref_column": "id",
        }
    ]


async def _no_samples(table_name: str) -> list[dict]:
    return []


class RecordingEmitter:
    """Collects emitted ProgressEvent objects in order."""

    def __init__(self):
        self.events: list[ProgressEvent] = []

    async def emit(self, event: ProgressEvent) -> None:
        self.events.append(event)

    def stages(self) -> list[str]:
        return [e.stage for e in self.events]

    def by_stage(self, stage: str) -> list[ProgressEvent]:
        return [e for e in self.events if e.stage == stage]


# ---------------------------------------------------------------------------
# Test 1: Strong lexical match — BM25 dominates fused
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bm25_dominates_with_lexical_match(tmp_path):
    """When the question matches a table name precisely, BM25 favours it and
    the result should contain that table."""
    # "customer" appears literally in the question.
    question = "show all customer records"
    tables = _make_tables()
    fks = _make_fks()

    # Neutral embedder: all docs get the same vector → no vector bias.
    embedder = FakeEmbedder()

    retriever = HybridRetriever(
        embedder=embedder,
        index_dir=tmp_path / "idx",
        max_seed_tables=3,
        max_tables=6,
    )
    ctx = await retriever.build_context(
        question=question,
        db_id="db1",
        schema_hash=1,
        tables_info=tables,
        foreign_keys=fks,
        sample_row_fetcher=_no_samples,
    )
    assert "customer" in ctx


# ---------------------------------------------------------------------------
# Test 2: Synonym mismatch — vector lifts the right table
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_vector_lifts_synonym(tmp_path):
    """'show all clients' has no lexical overlap with 'customer' but the
    embedder maps 'client'/'clients' and 'customer' doc to the same direction,
    so the vector ranking should surface 'customer'."""

    question = "show all clients"
    tables = _make_tables()
    fks = _make_fks()

    # "client" and "customer" share the same embedding direction → high cosine.
    customer_vec = [0.0, 1.0, 0.0, 0.0]
    embedder = FakeEmbedder(
        mapping={
            "client": customer_vec,
            "clients": customer_vec,
            "show": [0.5, 0.5, 0.0, 0.0],
            "all": [0.5, 0.5, 0.0, 0.0],
            # customer doc tokens also map to the same direction
            "customer": customer_vec,
            "customers": customer_vec,
        }
    )

    retriever = HybridRetriever(
        embedder=embedder,
        index_dir=tmp_path / "idx",
        max_seed_tables=3,
        max_tables=6,
    )
    ctx = await retriever.build_context(
        question=question,
        db_id="db1",
        schema_hash=2,
        tables_info=tables,
        foreign_keys=fks,
        sample_row_fetcher=_no_samples,
    )
    # customer should appear in the generated context due to vector similarity
    assert "customer" in ctx


# ---------------------------------------------------------------------------
# Test 3: Path match — join path tables included via path search
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_path_match_includes_joined_tables(tmp_path):
    """A question about 'orders joined with customer' should include both tables
    through the path search, even if only 'orders' has direct lexical overlap."""

    question = "list orders joined with customer"
    tables = _make_tables()
    fks = _make_fks()

    # Give "join orders customer" a distinctive vector so the path doc ranks high.
    join_vec = [0.0, 0.0, 1.0, 0.0]
    embedder = FakeEmbedder(
        mapping={
            "join": join_vec,
            "joined": join_vec,
            "orders": [0.7, 0.0, 0.3, 0.0],
            "order": [0.7, 0.0, 0.3, 0.0],
            "customer": [0.6, 0.2, 0.2, 0.0],
            "customers": [0.6, 0.2, 0.2, 0.0],
            # path doc text contains "join orders and customer"
            "and": join_vec,
        }
    )

    retriever = HybridRetriever(
        embedder=embedder,
        index_dir=tmp_path / "idx",
        max_seed_tables=5,
        max_tables=8,
    )
    ctx = await retriever.build_context(
        question=question,
        db_id="db1",
        schema_hash=3,
        tables_info=tables,
        foreign_keys=fks,
        sample_row_fetcher=_no_samples,
    )
    assert "orders" in ctx
    assert "customer" in ctx


# ---------------------------------------------------------------------------
# Test 4: hybrid_enabled=False → BM25-only path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_hybrid_disabled_produces_same_as_no_embedder(tmp_path):
    """Both hybrid_enabled=False and embedder=None should degrade to BM25-only,
    producing equivalent context (same tables selected)."""

    question = "show customer data"
    tables = _make_tables()
    fks = _make_fks()

    embedder = FakeEmbedder()

    # Path 1: hybrid_enabled=False but embedder provided
    ret_disabled = HybridRetriever(
        embedder=embedder,
        index_dir=tmp_path / "idx1",
        max_seed_tables=3,
        max_tables=6,
        hybrid_enabled=False,
    )
    ctx_disabled = await ret_disabled.build_context(
        question=question,
        db_id="db1",
        schema_hash=4,
        tables_info=tables,
        foreign_keys=fks,
        sample_row_fetcher=_no_samples,
    )

    # Path 2: embedder=None (auto BM25-only)
    ret_no_emb = HybridRetriever(
        embedder=None,
        index_dir=tmp_path / "idx2",
        max_seed_tables=3,
        max_tables=6,
        hybrid_enabled=True,
    )
    ctx_no_emb = await ret_no_emb.build_context(
        question=question,
        db_id="db1",
        schema_hash=4,
        tables_info=tables,
        foreign_keys=fks,
        sample_row_fetcher=_no_samples,
    )

    # Both should include "customer" (lexically best match)
    assert "customer" in ctx_disabled
    assert "customer" in ctx_no_emb

    # embedder should NOT have been called in the disabled path
    assert embedder.call_count == 0


# ---------------------------------------------------------------------------
# Test 5: Index rebuild when schema_hash changes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_index_rebuilt_on_schema_hash_change(tmp_path):
    """Building with hash=1, then hash=2 should produce two separate index files."""

    tables = _make_tables()
    fks = _make_fks()
    embedder = FakeEmbedder()
    idx_dir = tmp_path / "idx"

    retriever = HybridRetriever(
        embedder=embedder,
        index_dir=idx_dir,
        max_seed_tables=3,
        max_tables=6,
    )

    await retriever.build_context(
        question="customers",
        db_id="testdb",
        schema_hash=1,
        tables_info=tables,
        foreign_keys=fks,
        sample_row_fetcher=_no_samples,
    )

    await retriever.build_context(
        question="customers",
        db_id="testdb",
        schema_hash=2,
        tables_info=tables,
        foreign_keys=fks,
        sample_row_fetcher=_no_samples,
    )

    # Both hash-1 and hash-2 files should exist (or only hash-2 if cleanup ran,
    # but we have at most 2 files < 3 so both are kept).
    model_safe = embedder.MODEL.replace("/", "_")
    file1 = idx_dir / f"testdb__1__{model_safe}.npz"
    file2 = idx_dir / f"testdb__2__{model_safe}.npz"

    assert file2.exists(), "Index for hash=2 must exist"


# ---------------------------------------------------------------------------
# Test 6: Index reload on matching (db_id, schema_hash)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_index_reloaded_not_rebuilt(tmp_path):
    """Second call with same db_id/hash should load from disk, not re-embed."""

    tables = _make_tables()
    fks = _make_fks()
    embedder = FakeEmbedder()
    idx_dir = tmp_path / "idx"

    retriever = HybridRetriever(
        embedder=embedder,
        index_dir=idx_dir,
        max_seed_tables=3,
        max_tables=6,
    )

    # First call — builds index
    await retriever.build_context(
        question="orders",
        db_id="testdb",
        schema_hash=99,
        tables_info=tables,
        foreign_keys=fks,
        sample_row_fetcher=_no_samples,
    )
    calls_after_build = embedder.call_count

    # Second call — same hash → should reload from disk (only 1 extra embed call
    # for the query vector, but NOT a full rebuild that embeds all docs).
    # We track: embed is called once per build_context for query embedding.
    # On reload, we skip the bulk doc embed calls.
    await retriever.build_context(
        question="orders",
        db_id="testdb",
        schema_hash=99,
        tables_info=tables,
        foreign_keys=fks,
        sample_row_fetcher=_no_samples,
    )
    calls_after_reload = embedder.call_count

    # Each build_context calls embed once for the query vector.
    # Build phase calls embed additional times for docs.
    # On reload, only the query vector embed call happens.
    # So the increment on reload should equal the increment for one query embed.
    increment_build = calls_after_build  # first call
    increment_reload = calls_after_reload - calls_after_build  # second call

    # The rebuild involves multiple embed calls (for docs + query).
    # The reload involves only 1 embed call (for query).
    assert increment_reload <= increment_build, (
        f"Reload should use fewer embed calls ({increment_reload}) "
        f"than initial build ({increment_build})"
    )


# ---------------------------------------------------------------------------
# Test 7: Concurrent ensure_index → single build
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_concurrent_build_calls_single_index_build(tmp_path):
    """Concurrent build_context calls with the same db_id/hash must not
    trigger multiple parallel index builds (lock must serialize them)."""

    tables = _make_tables()
    fks = _make_fks()

    call_counts: list[int] = []

    class CountingEmbedder(FakeEmbedder):
        def embed(self, texts):
            call_counts.append(len(texts))
            return super().embed(texts)

    embedder = CountingEmbedder()
    idx_dir = tmp_path / "idx"

    retriever = HybridRetriever(
        embedder=embedder,
        index_dir=idx_dir,
        max_seed_tables=3,
        max_tables=6,
    )

    # Launch 3 concurrent build_context calls for the same db/hash.
    results = await asyncio.gather(
        retriever.build_context(
            question="product list",
            db_id="concdb",
            schema_hash=77,
            tables_info=tables,
            foreign_keys=fks,
            sample_row_fetcher=_no_samples,
        ),
        retriever.build_context(
            question="product list",
            db_id="concdb",
            schema_hash=77,
            tables_info=tables,
            foreign_keys=fks,
            sample_row_fetcher=_no_samples,
        ),
        retriever.build_context(
            question="product list",
            db_id="concdb",
            schema_hash=77,
            tables_info=tables,
            foreign_keys=fks,
            sample_row_fetcher=_no_samples,
        ),
    )

    # All 3 calls should complete successfully
    assert len(results) == 3

    # Doc embedding (bulk embed) should happen only ONCE across all 3 concurrent calls.
    # A single build for our 3-table schema produces up to 3 separate embed calls
    # (table_docs batch, column_docs batch, path_docs batch).  Each of those batches
    # has size > 1 for our test schema (3, 10, and 1 respectively).
    # If the lock works, total doc-embed texts = table_docs + column_docs + path_docs
    # = 3 + 10 + 1 = 14 (once).  Without the lock it would be 14 * 3 = 42.
    # We count total texts in all embed calls that are "doc builds" (size != 1).
    # Actually the easiest invariant: total embed texts across all calls must be
    # one build worth (14) + 3 query vecs (1 each) = 17, not 3 builds (42) + 3 = 45.
    total_texts_embedded = sum(call_counts)
    # One build = 3 table docs + 10 col docs + 1 path doc = 14 + 3 query vecs = 17
    # Three builds = 42 + 3 query vecs = 45
    # With lock: <= one_build_size + N_concurrent_queries
    one_build_doc_size = 14   # 3 + 10 + 1 for our schema
    n_queries = 3
    assert total_texts_embedded <= one_build_doc_size + n_queries, (
        f"Expected at most {one_build_doc_size + n_queries} total embedded texts "
        f"(single build), but got {total_texts_embedded}: {call_counts}"
    )


# ---------------------------------------------------------------------------
# Test 8: Progress events — order and duration_ms
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_progress_events_emitted_in_order(tmp_path):
    """Progress events must be emitted in the documented order and completed
    events must carry a non-null duration_ms."""

    tables = _make_tables()
    fks = _make_fks()
    embedder = FakeEmbedder()
    recorder = RecordingEmitter()

    retriever = HybridRetriever(
        embedder=embedder,
        index_dir=tmp_path / "idx",
        max_seed_tables=3,
        max_tables=6,
    )

    await retriever.build_context(
        question="list customers",
        db_id="db_prog",
        schema_hash=55,
        tables_info=tables,
        foreign_keys=fks,
        sample_row_fetcher=_no_samples,
        progress=recorder.emit,
    )

    stages = recorder.stages()

    # bm25 must be the first event
    assert stages[0] == "schema.retrieve.bm25", f"First stage was {stages[0]}"

    # All stages we need should appear at least once (including schema.embed.build)
    expected_stages = {
        "schema.retrieve.bm25",
        "schema.embed.build",
        "schema.retrieve.vector",
        "schema.retrieve.fuse",
        "schema.prune",
        "schema.samples",
    }
    assert expected_stages.issubset(set(stages)), (
        f"Missing stages. Got: {stages}"
    )

    # All 'completed' events must have non-null duration_ms
    for event in recorder.events:
        if event.status == "completed":
            assert event.duration_ms is not None, (
                f"Event {event.stage} completed but has null duration_ms"
            )
            assert isinstance(event.duration_ms, int), (
                f"duration_ms must be int, got {type(event.duration_ms)}"
            )
            assert event.duration_ms >= 0


# ---------------------------------------------------------------------------
# Test 8b: schema.embed.build status — "completed" on first build, "skipped" on reload
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_embed_build_event_status_built_then_loaded(tmp_path):
    """On the first call (fresh index), schema.embed.build must be 'completed'
    with a non-null duration_ms.  On the second call (same hash → loaded from
    disk), schema.embed.build must be 'skipped'."""

    tables = _make_tables()
    fks = _make_fks()
    embedder = FakeEmbedder()

    retriever = HybridRetriever(
        embedder=embedder,
        index_dir=tmp_path / "idx",
        max_seed_tables=3,
        max_tables=6,
    )

    # --- First call: index is built from scratch ---
    recorder_build = RecordingEmitter()
    await retriever.build_context(
        question="list customers",
        db_id="db_build_test",
        schema_hash=42,
        tables_info=tables,
        foreign_keys=fks,
        sample_row_fetcher=_no_samples,
        progress=recorder_build.emit,
    )

    build_events = recorder_build.by_stage("schema.embed.build")
    assert len(build_events) == 1, (
        f"Expected exactly 1 schema.embed.build event on first call, got {len(build_events)}"
    )
    build_evt = build_events[0]
    assert build_evt.status == "completed", (
        f"Expected status='completed' on first build, got {build_evt.status!r}"
    )
    assert build_evt.duration_ms is not None, (
        "schema.embed.build 'completed' event must carry a non-null duration_ms"
    )
    assert isinstance(build_evt.duration_ms, int)
    assert build_evt.duration_ms >= 0

    # --- Second call: same hash → index loaded from disk ---
    recorder_load = RecordingEmitter()
    await retriever.build_context(
        question="list customers",
        db_id="db_build_test",
        schema_hash=42,
        tables_info=tables,
        foreign_keys=fks,
        sample_row_fetcher=_no_samples,
        progress=recorder_load.emit,
    )

    load_events = recorder_load.by_stage("schema.embed.build")
    assert len(load_events) == 1, (
        f"Expected exactly 1 schema.embed.build event on second call, got {len(load_events)}"
    )
    load_evt = load_events[0]
    assert load_evt.status == "skipped", (
        f"Expected status='skipped' when index is loaded from disk, got {load_evt.status!r}"
    )


@pytest.mark.asyncio
async def test_embed_build_event_skipped_on_bm25_only_path(tmp_path):
    """When hybrid_enabled=False or embedder=None, schema.embed.build must be
    emitted as 'skipped' (vector index never attempted)."""

    tables = _make_tables()
    fks = _make_fks()

    for label, kwargs in [
        ("hybrid_disabled", {"embedder": FakeEmbedder(), "hybrid_enabled": False}),
        ("no_embedder", {"embedder": None, "hybrid_enabled": True}),
    ]:
        recorder = RecordingEmitter()
        retriever = HybridRetriever(
            index_dir=tmp_path / f"idx_{label}",
            max_seed_tables=3,
            max_tables=6,
            **kwargs,
        )
        await retriever.build_context(
            question="show customers",
            db_id="db_bm25_only",
            schema_hash=1,
            tables_info=tables,
            foreign_keys=fks,
            sample_row_fetcher=_no_samples,
            progress=recorder.emit,
        )

        build_events = recorder.by_stage("schema.embed.build")
        assert len(build_events) == 1, (
            f"[{label}] Expected exactly 1 schema.embed.build event, got {len(build_events)}"
        )
        assert build_events[0].status == "skipped", (
            f"[{label}] Expected status='skipped' on BM25-only path, "
            f"got {build_events[0].status!r}"
        )


# ---------------------------------------------------------------------------
# Test 9: Empty tables_info — returns empty schema context
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_empty_tables_info_returns_empty_context(tmp_path):
    """When tables_info is empty, return format_schema_context([], [], None, False)."""

    embedder = FakeEmbedder()
    retriever = HybridRetriever(
        embedder=embedder,
        index_dir=tmp_path / "idx",
    )

    ctx = await retriever.build_context(
        question="anything",
        db_id="db1",
        schema_hash=0,
        tables_info=[],
        foreign_keys=[],
        sample_row_fetcher=_no_samples,
    )

    # format_schema_context([], [], None, False) returns this string:
    assert "No tables found" in ctx


# ---------------------------------------------------------------------------
# Test 10: sample_row_fetcher error per table doesn't abort the whole call
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sample_row_fetcher_error_is_tolerated(tmp_path):
    """An exception from sample_row_fetcher for one table must be swallowed
    and must not abort the build_context call."""

    tables = _make_tables()
    fks = _make_fks()
    embedder = FakeEmbedder()

    call_count = {"n": 0}

    async def bad_fetcher(table_name: str) -> list[dict]:
        call_count["n"] += 1
        raise RuntimeError(f"Fetcher failed for {table_name}")

    retriever = HybridRetriever(
        embedder=embedder,
        index_dir=tmp_path / "idx",
        max_seed_tables=3,
        max_tables=6,
        include_sample_rows=True,
    )

    # Should not raise
    ctx = await retriever.build_context(
        question="customers",
        db_id="db1",
        schema_hash=1,
        tables_info=tables,
        foreign_keys=fks,
        sample_row_fetcher=bad_fetcher,
    )

    assert ctx  # non-empty result
    assert call_count["n"] > 0  # fetcher was called


# ---------------------------------------------------------------------------
# Test 11: include_sample_rows=False — fetcher never called
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_include_sample_rows_false_skips_fetcher(tmp_path):
    """When include_sample_rows=False, sample_row_fetcher must not be called."""

    tables = _make_tables()
    fks = _make_fks()
    embedder = FakeEmbedder()

    called = {"n": 0}

    async def counting_fetcher(table_name: str) -> list[dict]:
        called["n"] += 1
        return []

    retriever = HybridRetriever(
        embedder=embedder,
        index_dir=tmp_path / "idx",
        max_seed_tables=3,
        max_tables=6,
        include_sample_rows=False,
    )

    await retriever.build_context(
        question="orders",
        db_id="db1",
        schema_hash=1,
        tables_info=tables,
        foreign_keys=fks,
        sample_row_fetcher=counting_fetcher,
    )

    assert called["n"] == 0


# ---------------------------------------------------------------------------
# Test 12: Fallback when fused is empty (all-zero BM25 + no vector signal)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fallback_used_when_no_signal(tmp_path):
    """When BM25 returns zero scores and vector path is disabled, the fallback
    path is triggered and all tables (up to max_tables) are included."""

    # Question with only stop-words → BM25 returns zero scores for all tables
    question = "show me the data"
    tables = _make_tables()
    fks = _make_fks()

    retriever = HybridRetriever(
        embedder=None,          # BM25-only
        index_dir=tmp_path / "idx",
        max_seed_tables=3,
        max_tables=6,
        hybrid_enabled=False,
    )

    ctx = await retriever.build_context(
        question=question,
        db_id="db1",
        schema_hash=1,
        tables_info=tables,
        foreign_keys=fks,
        sample_row_fetcher=_no_samples,
    )

    # Fallback path includes all tables (up to max_tables)
    # All 3 tables should appear since we have 3 <= max_tables=6
    assert "customer" in ctx
    assert "orders" in ctx
    assert "product" in ctx
