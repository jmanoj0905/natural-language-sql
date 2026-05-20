# RAG Pipeline Improvements — Bundle A (Foundation)

**Date:** 2026-05-20
**Status:** Design — awaiting implementation
**Scope:** Smarter schema retrieval for natural-language → SQL generation.

## 1. Goals

Improve table/column selection accuracy and context efficiency in the RAG pipeline that feeds the local Ollama SQL generator.

Concretely:

1. Fix vocabulary mismatch (e.g., "customer" in question vs `client` table) by adding semantic embeddings alongside BM25.
2. Handle wide tables by pruning irrelevant columns before they reach the prompt.
3. Include one sample row per selected table in the compact (retrieval-based) context.
4. Collapse duplicated formatting code so a single formatter renders schema context for every code path.
5. Keep latency low (< 200ms warm retrieval) and remain backwards-compatible behind a feature flag during rollout.

**Non-goals (deferred):**

- Query-history few-shot retrieval (Bundle B).
- Schema linking + self-correction loop (Bundle C).
- Streaming SSE for RAG sub-stages (separate spec; this design only exposes the hook).
- Cross-encoder reranking, GPU embeddings, multi-tenant index scoping.

## 2. Architecture

```
NL question
   │
   ▼
SchemaInspector.get_relevant_schema_summary  (entry — signature unchanged)
   │
   ▼
HybridRetriever.build_context              (single retriever, replaces SchemaGraphRetriever)
   │
   ├─► BM25Ranker          (lexical signal)
   ├─► VectorIndex.search  (semantic signal — tables, columns, FK paths)
   ├─► rrf_fuse            (combine rankings)
   ├─► expand_with_fks     (1-hop FK expansion of seeds)
   ├─► ColumnPruner        (drop irrelevant columns per table)
   ├─► sample row fetcher  (existing _get_sample_rows, 1 row)
   └─► format_schema_context (single formatter; also used by full path)

Embedding pipeline (one-time per schema_hash):
   SchemaCorpusBuilder → SchemaEmbedder (all-MiniLM-L6-v2) → VectorIndex → disk (.npz)
```

`HYBRID_RETRIEVAL_ENABLED=true` (default) → full pipeline.
`HYBRID_RETRIEVAL_ENABLED=false` → BM25 + FK expand + formatter only; same code path with vector + pruner skipped. This is the fallback mode; there is no second retriever class.

## 3. File layout

New:

```
app/core/ai/
  schema_embedder.py             # SentenceTransformer singleton (all-MiniLM-L6-v2)

app/core/database/retrieval/
  __init__.py
  bm25.py                        # BM25Ranker — extracted from current SchemaGraphRetriever
  fk_expander.py                 # expand_with_fks(seeds, fks, lookup)
  rrf.py                         # rrf_fuse(rankings, k=60)
  corpus.py                      # SchemaCorpusBuilder → SchemaCorpus
  vector_index.py                # VectorIndex (numpy arrays + ids; save/load/search)
  column_pruner.py               # ColumnPruner
  formatter.py                   # format_schema_context (used by hybrid AND full path)
  hybrid.py                      # HybridRetriever (composes the above)
  progress.py                    # ProgressEvent + ProgressEmitter type alias

tests/retrieval/
  conftest.py
  test_bm25.py
  test_rrf.py
  test_fk_expander.py
  test_corpus.py
  test_column_pruner.py
  test_formatter.py
  test_vector_index.py
  test_schema_embedder.py        # slow tier, marked @pytest.mark.slow
  test_hybrid.py                 # uses FakeEmbedder
tests/
  test_schema_inspector_hybrid.py
  test_sql_generator_hybrid.py   # may be new file or extend existing
```

Deleted:

```
app/core/database/schema_retriever.py        # superseded by retrieval/ package
```

Reduced:

```
app/core/database/schema_inspector.py        # CREATE-TABLE building moves to retrieval/formatter.py
```

## 4. Components

### 4.1 `SchemaEmbedder` (app/core/ai/schema_embedder.py)

```python
class SchemaEmbedder:
    MODEL = "all-MiniLM-L6-v2"
    DIM = 384

    def __init__(self) -> None: ...        # lazy import; model loads on first embed()
    def embed(self, texts: list[str]) -> np.ndarray:  # (N, 384), L2-normalized
```

Module-level `get_schema_embedder()` returns a singleton via `lru_cache`.

If `sentence-transformers` import fails: log + raise a typed `EmbedderUnavailableError`. Caller in `HybridRetriever` catches and degrades to BM25-only behavior for that build.

### 4.2 Retrieval package (app/core/database/retrieval/)

**`bm25.py`** — `BM25Ranker.rank_tables(question, tables_info) -> list[TableScore]`. Logic ported from current `SchemaGraphRetriever._rank_tables` + tokenizer helpers. No behavior change.

**`fk_expander.py`** — `expand_with_fks(seeds, foreign_keys, table_lookup) -> list[str]`. Pure function; ported from current `_expand_with_foreign_keys`.

**`rrf.py`** — `rrf_fuse(rankings: list[list[str]], k: int = 60) -> list[str]`. Standard `1 / (k + rank)` summation. Tie-break by ordered first appearance.

**`corpus.py`** — `SchemaCorpusBuilder.build(tables_info, foreign_keys) -> SchemaCorpus`.

```python
@dataclass(frozen=True)
class SchemaCorpus:
    table_docs:  list[tuple[str, str]]                  # (table, doc_text)
    column_docs: list[tuple[tuple[str, str], str]]      # ((table, column), doc_text)
    path_docs:   list[tuple[tuple[str, str], str]]      # ((tableA, tableB), doc_text)
```

Doc text templates:

- **Table:** `"{name}. columns: {col1, col2, ...}. types: {t1, t2, ...}"`.
- **Column:** `"{column} ({type}) in table {table}"`.
- **Path:** `"join {tableA} and {tableB} on {colA}={colB}. tableA columns: {...}. tableB columns: {...}"`.

Path docs generated only for FK pairs where both endpoints exist in `tables_info`.

**`vector_index.py`** — `VectorIndex`:

```python
class VectorIndex:
    table_vecs:   np.ndarray   # (N_t, 384)
    column_vecs:  np.ndarray   # (N_c, 384)
    path_vecs:    np.ndarray   # (N_p, 384)
    table_ids:    list[str]
    column_ids:   list[tuple[str, str]]
    path_ids:     list[tuple[str, str]]
    schema_hash:  int
    model_name:   str

    def save(self, path: Path) -> None
    @classmethod
    def load(cls, path: Path) -> "VectorIndex"
    def search(self, q: np.ndarray, k: int, kind: Literal["tables","columns","paths"]) -> list[tuple[Any, float]]
```

Persistence:

- Format: `np.savez_compressed`.
- Path: `{EMBEDDING_INDEX_DIR}/{db_id}__{schema_hash}__{model_name}.npz`.
  Including `model_name` in the filename guards against silent staleness if the embedder model is upgraded in a future release.
- On rebuild, glob-delete stale `{db_id}__*.npz` files except the latest (cap last 3 by mtime).

Search: cosine similarity (vectors are pre-normalized → dot product).

**`column_pruner.py`** — `ColumnPruner.prune(question, q_vec, selected_tables, index) -> list[dict]`. For each table:

- If `len(columns) <= MAX_COLS_PER_TABLE`: return all columns unchanged.
- Else: score columns by cosine(q_vec, column_vec). Keep:
  - PK columns (always).
  - FK columns (always; needed for joins).
  - Top-N by score (until cap reached).
  - Any column with score ≥ `COLUMN_SCORE_THRESHOLD`.

PK detection: pull during `_get_all_tables_info` (extend query — already cheap) and include in `tables_info`.

**`formatter.py`** — `format_schema_context(selected_tables, foreign_keys, sample_rows_by_table, fallback_used) -> str`.

Single function emits:

```
-- AVAILABLE TABLES (use only these exact names, do not guess):
--   t1, t2, t3

CREATE TABLE t1 (
  col1 type NOT NULL,
  col2 type,
  FOREIGN KEY (col1) REFERENCES t2(id)
);
-- Sample rows from t1:
--   col1=1, col2='x'

...

-- RELATIONSHIPS (use these for JOINs):
--   t1.col1 -> t2.id
```

Used by:

- `HybridRetriever.build_context` (compact / retrieval path).
- `SchemaInspector.get_schema_summary` (full path; replaces inline CREATE-TABLE building).

**`hybrid.py`** — `HybridRetriever`:

```python
class HybridRetriever:
    def __init__(
        self,
        embedder: SchemaEmbedder | None,
        index_dir: Path,
        max_seed_tables: int = 5,
        max_tables: int = 12,
        max_cols_per_table: int = 15,
        col_score_threshold: float = 0.25,
        rrf_k: int = 60,
        include_sample_rows: bool = True,
        hybrid_enabled: bool = True,
    ): ...

    async def build_context(
        self,
        *,
        question: str,
        db_id: str,
        schema_hash: int,
        tables_info: list[dict],
        foreign_keys: list[dict],
        sample_row_fetcher: Callable[[str], Awaitable[list[dict]]] | None,
        progress: ProgressEmitter | None = None,
    ) -> str: ...
```

Order of operations:

1. `bm25_rank = BM25Ranker.rank_tables(question, tables_info)`.
2. If `hybrid_enabled` and embedder available:
   - `index = await ensure_index(db_id, schema_hash, tables_info, foreign_keys)`.
   - `q_vec = embedder.embed([question])[0]`.
   - `table_rank = index.search(q_vec, k=20, kind="tables")`.
   - `path_rank = index.search(q_vec, k=10, kind="paths")` → expand each path to its two tables, merge.
   - `fused = rrf_fuse([bm25_rank, table_rank, expanded_path_rank], k=rrf_k)`.
3. Else: `fused = bm25_rank`.
4. `seeds = fused[:max_seed_tables]`.
5. `selected = expand_with_fks(seeds, foreign_keys, table_lookup)[:max_tables]`.
6. `pruned = ColumnPruner.prune(question, q_vec, selected, index)` (only when vectors available; else passthrough).
7. `samples = {t: await sample_row_fetcher(t) for t in selected}` if `include_sample_rows` and fetcher given.
8. `return format_schema_context(pruned, foreign_keys, samples, fallback_used=False)`.

Each step wraps an `await progress(...)` call when `progress` is provided.

`ensure_index` uses an `asyncio.Lock` keyed by `db_id` so concurrent first-queries don't double-build.

### 4.3 `progress.py`

```python
@dataclass(frozen=True)
class ProgressEvent:
    stage: str         # e.g. "schema.retrieve.bm25"
    status: str        # "in_progress" | "completed" | "skipped" | "error"
    message: str = ""
    duration_ms: int | None = None
    meta: dict | None = None

ProgressEmitter = Callable[[ProgressEvent], Awaitable[None]]
```

Emitted stages in Bundle A:

- `schema.introspect`
- `schema.embed.build` (skipped if index loaded from disk)
- `schema.retrieve` (sub-events: `.bm25`, `.vector`, `.fuse`)
- `schema.prune`
- `schema.samples`

If `progress=None`, components are silent. The streaming endpoint (future spec) supplies an emitter that converts events to SSE.

### 4.4 `SchemaInspector` wiring

`get_relevant_schema_summary` delegates to `HybridRetriever`:

```python
async def get_relevant_schema_summary(self, connection, question, db_id="default", max_tables=12, progress=None):
    db_type, _ = self._get_db_info(db_id)
    tables_info = await self._get_all_tables_info(connection, 50, db_id)
    foreign_keys = await self._get_foreign_keys(connection, db_id)
    schema_hash = await self.get_schema_version(connection, db_id)

    async def fetch_sample(table_name: str) -> list[dict]:
        return await self._get_sample_rows(connection, table_name, 1, db_type)

    return await self._hybrid.build_context(
        question=question,
        db_id=db_id,
        schema_hash=schema_hash,
        tables_info=tables_info,
        foreign_keys=foreign_keys,
        sample_row_fetcher=fetch_sample,
        progress=progress,
    )
```

`get_schema_summary` (full path) now calls `format_schema_context` instead of inlining CREATE TABLE building. Sample-row count for full path stays `SCHEMA_CACHE_SAMPLE_ROWS` (existing).

`clear_cache_for_database(db_id)` additionally deletes `{EMBEDDING_INDEX_DIR}/{db_id}__*.npz`.

### 4.5 Config (app/config.py)

| Var | Default | Meaning |
|-----|---------|---------|
| `HYBRID_RETRIEVAL_ENABLED` | `true` | Master switch. `false` → BM25-only. |
| `MAX_SEED_TABLES` | `5` | Seeds after RRF, before FK expansion. |
| `MAX_TABLES` | `12` | Final cap after FK expansion. |
| `MAX_COLS_PER_TABLE` | `15` | Column pruning cap. Tables with ≤ this are passed through. |
| `COLUMN_SCORE_THRESHOLD` | `0.25` | Min cosine to keep a column beyond top-N. |
| `RRF_K` | `60` | RRF constant. |
| `INCLUDE_SAMPLE_ROWS_COMPACT` | `true` | Include sample row in compact context. |
| `SAMPLE_ROWS_COMPACT` | `1` | Sample rows per selected table. |
| `EMBEDDING_INDEX_DIR` | `~/.nlsql/embeddings` | On-disk index location. |

### 4.6 Dependencies

`requirements.txt` adds:

```
sentence-transformers>=2.7
numpy>=1.26
```

Model auto-downloads to `~/.cache/huggingface` on first `embed()`. Document the `HF_HUB_OFFLINE=1` workaround in README for air-gapped installs.

## 5. Data flow (query path)

1. `POST /api/v1/query/natural` → `SQLGenerator.generate_sql`.
2. Intent detection (existing).
3. `SchemaInspector.get_relevant_schema_summary(connection, question, db_id)`.
   1. TTL cache lookup keyed by `(db_id, max_tables, q_hash)`. Hit → return.
   2. Introspect tables + FKs (own cache).
   3. `HybridRetriever.build_context(...)`:
      - `ensure_index(db_id, schema_hash)` — load `.npz` or build + save.
      - Embed question, run BM25 + vector + path searches, RRF fuse.
      - FK-expand seeds, prune columns, fetch 1 sample row per table.
      - Format with `format_schema_context`.
   4. Cache result.
4. `build_sql_generation_prompt(question, schema_context, db_type, intent_context)`.
5. `OllamaClient.generate(prompt)`.
6. Extract + validate + execute (existing).

Timing budget on a 50-table DB:

| Step | Cold | Warm |
|------|------|------|
| Schema introspection | ~100-300ms | cached |
| Index build (corpus + embed ~630 docs) | ~2-3s (one-time per schema_hash) | n/a |
| Index load | n/a | ~5ms |
| Question embed | n/a | ~5ms |
| Cosine searches × 3 | n/a | <5ms |
| RRF + FK expand + prune | n/a | <2ms |
| Sample rows (×12 tables) | ~50-100ms | TTL-cached |
| **Retrieval total** | **~2.2-3.4s (first query only)** | **~70-120ms** |
| LLM SQL gen (sqlcoder) | 1-3s | 1-3s |

## 6. Migration plan

Each step is an independent commit; the app stays working at every step.

| # | Change | User-visible effect |
|---|--------|---------------------|
| 1 | Add `retrieval/bm25.py`, `retrieval/formatter.py`, `retrieval/fk_expander.py`. Existing `SchemaGraphRetriever` delegates to them. Full path `get_schema_summary` calls `format_schema_context`. | None. |
| 2 | Add `retrieval/rrf.py`, `corpus.py`, `column_pruner.py`, `vector_index.py`, `progress.py`. Pure; unused in production path yet. | None. |
| 3 | Add `sentence-transformers` and `numpy` to `requirements.txt`. Add `schema_embedder.py` with lazy singleton. | None — model not invoked. |
| 4 | Add `retrieval/hybrid.py`. Wire `SchemaInspector` to `HybridRetriever`. Ship with `HYBRID_RETRIEVAL_ENABLED=false`. | None — behind flag. |
| 5 | Flip default to `HYBRID_RETRIEVAL_ENABLED=true`. | Improved retrieval; first query per DB takes ~2-3s extra (one-time embed). |
| 6 | Delete `schema_retriever.py`. `HYBRID_RETRIEVAL_ENABLED=false` keeps working (BM25-only branch inside `HybridRetriever`). | None. |
| 7 | Extend `POST /schema/cache/clear` to also delete `.npz` files for that db_id. | Cache clear wipes vector index too. |

## 7. Testing

### 7.1 Unit tests (pure, no DB, no model)

`tests/retrieval/test_bm25.py`

- Empty corpus → empty ranking.
- Question matches table name only → that table ranks #1.
- Stopwords filtered ("show me the orders" matches `orders`).
- Plural normalization ("customers" matches `customer`).

`tests/retrieval/test_rrf.py`

- Single ranker passthrough.
- Two rankers, disjoint top-1 → both in top-2.
- Deterministic tie-break.

`tests/retrieval/test_fk_expander.py`

- Seed adds 1-hop neighbors.
- Cycles do not loop.
- Self-FKs handled.

`tests/retrieval/test_corpus.py`

- Table doc contains name + columns.
- Path doc generated only when both endpoints exist.
- Column doc has `name + type + table`.

`tests/retrieval/test_column_pruner.py`

- PK/FK always kept even at low cosine.
- Tables with ≤ `MAX_COLS_PER_TABLE` returned unchanged.
- Threshold `τ` enforced.

`tests/retrieval/test_formatter.py`

- Output contains `CREATE TABLE`, `FOREIGN KEY`, `-- RELATIONSHIPS`.
- Sample row line present when row provided.
- Same input → byte-identical output.

`tests/retrieval/test_vector_index.py`

- `save → load` round-trip preserves arrays and ids.
- `search(q, k)` returns top-k by cosine descending.
- Corrupt file → `load` raises; caller rebuilds.

### 7.2 Embedder tests (slow tier)

`tests/retrieval/test_schema_embedder.py` — `@pytest.mark.slow`.

- `embed(["x"])` shape `(1, 384)`, L2-norm ≈ 1.
- "customer" vs "client" cosine > 0.5.
- Unrelated strings cosine < 0.5.
- `get_schema_embedder()` is a singleton.

CI fast suite skips `slow`; `pytest -m slow` runs them locally.

### 7.3 HybridRetriever integration (FakeEmbedder)

`tests/retrieval/test_hybrid.py`

- Strong lexical match: BM25 dominates fused ranking.
- Synonym mismatch ("client" vs `customer`): vector signal lifts the right table when BM25 misses.
- Path match: "orders per customer city" → seeds include both endpoints via path retrieval.
- `hybrid_enabled=false` → output identical to BM25-only path with same inputs.
- Index rebuild when `schema_hash` changes.
- Index reload when `(db_id, schema_hash)` matches existing file.
- Concurrent `ensure_index` calls → single build (lock).
- `progress` callback receives events in order with non-null `duration_ms` on `completed`.

### 7.4 SchemaInspector wiring

`tests/test_schema_inspector_hybrid.py`

- `get_relevant_schema_summary` calls `HybridRetriever` once per cache window.
- `clear_cache_for_database` removes TTL entries and `.npz` files.
- Stale `{db_id}__<old_hash>.npz` pruned on rebuild; latest 3 kept.

### 7.5 End-to-end smoke

`tests/test_sql_generator_hybrid.py`

- Stub embedder + Ollama client.
- Semantic-mismatch question routes to the correct table.
- Prompt contains pruned columns (≤ `MAX_COLS_PER_TABLE`) + 1 sample row line per table.
- `HYBRID_RETRIEVAL_ENABLED=false` produces prior-behavior prompt (regression guard).

### 7.6 Fixtures (tests/retrieval/conftest.py)

- `fake_tables_info` — 3 tables, ~10 columns total.
- `fake_foreign_keys` — 2 FK edges.
- `fake_embedder` — deterministic dict → vector.
- `tmp_index_dir` — isolates `VectorIndex` disk I/O.

### 7.7 TDD order

1. `bm25.py` + tests (extract first; prove parity with old retriever).
2. `formatter.py` + tests (extract; full path now uses it).
3. `fk_expander.py`, `rrf.py`, `corpus.py`, `column_pruner.py`.
4. `vector_index.py` + round-trip tests.
5. `schema_embedder.py` + slow-tier tests.
6. `hybrid.py` integration with `FakeEmbedder`.
7. `progress.py` + emitter wiring in hybrid.
8. Wire `SchemaInspector`, delete `schema_retriever.py`.
9. End-to-end smoke.

## 8. Risks & mitigations

| Risk | Severity | Mitigation |
|------|----------|------------|
| `sentence-transformers` install fails on a niche OS | Medium | Pin known-good versions. Startup check imports embedder; on failure, log warning and auto-flip `HYBRID_RETRIEVAL_ENABLED=false` for the process. |
| First-query latency spike (model load + corpus embed) | Low | Document in README. Optionally preload in `lifespan` (configurable). Subsequent queries load `.npz` in ~5ms. |
| `.npz` files accumulate over schema evolution | Low | Prune stale `{db_id}__*.npz` on rebuild, keep last 3 by mtime. |
| HF model download blocked offline | Medium | Document `HF_HUB_OFFLINE=1`. Add `install.sh` step that pre-warms the model cache. |
| Memory: model holds ~80MB in process | Low | Acceptable; single-process backend. |
| Column pruner drops a needed column | Medium | PK + FK always kept. Threshold tunable. Top-N floor ensures min coverage. Fallback via `HYBRID_RETRIEVAL_ENABLED=false`. |
| RRF `k=60` not optimal for tiny DBs | Low | Configurable. Quality knob, not correctness. |
| Embedding stale after schema change | Low | `schema_hash` is part of cache key; new hash → new file. |
| Concurrent first-query → double build | Low | Per-`db_id` `asyncio.Lock` around `ensure_index`. |
| Sample row fetch on every retrieval (12 × LIMIT 1) | Low | TTL-cached at same key. Existing pattern. |

## 9. Open questions

1. **Preload embedder on startup?** Recommend lazy (first-query takes the hit once); revisit if users hit it on every restart.
2. **Question normalization before embed?** Recommend none — MiniLM handles casing/punctuation.
3. **Index rebuild on app upgrade?** Filename includes `model_name` → safe for future model swaps.
4. **Multi-DB embedding sharing?** Out of scope — each `db_id` has its own index file.

## 10. Success criteria

- All new unit tests pass.
- Existing tests still pass (`tests/test_sanitizer.py`, `tests/test_validator.py`, etc.).
- Manual smoke on a test DB with a synonym mismatch (e.g., a `client` table queried as "customers"): the prompt sent to Ollama contains `client`. With `HYBRID_RETRIEVAL_ENABLED=false` it does not. This is the regression check that vectors are doing work.
- Retrieval p50 < 200ms warm (excludes one-time cold build).
- No new steady-state error logs.

## 11. Extension points (deferred specs)

The Bundle A code is shaped so future work plugs in without restructuring:

- **Streaming SSE for RAG sub-stages** — the `progress` parameter on `HybridRetriever.build_context` and its sub-components is the hook. The future stream endpoint passes an emitter that converts `ProgressEvent` to SSE.
- **Query-history few-shot (Bundle B)** — `SchemaEmbedder` and `VectorIndex` are reusable for a separate question-history index.
- **Self-correction loop (Bundle C)** — `HybridRetriever.build_context` accepts a fresh `question` each call, so a corrector that rewrites the question after a failed SQL execution can call it again with no API change.
- **Token-stream / row-stream** — independent of retrieval; touches `ollama_client.py` and `executor.py`. Out of scope for Bundle A.
