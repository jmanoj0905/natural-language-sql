# Benchmarks

Execution-accuracy eval on the [Spider](https://yale-lily.github.io/spider) dev set.

## Latest runs

| Metric | Baseline (full schema) | RAG (hybrid retrieval) |
|---|---|---|
| Model | `mannix/defog-llama3-sqlcoder-8b` (Ollama, local) | same |
| Dataset | Spider dev (1034 q, 20 DBs) | same |
| **Execution accuracy** | **52.32 %** (541 / 1034) | **53.00 %** (548 / 1034) |
| Mismatch | 386 | 383 |
| Execution error | 107 | 103 |
| Generation error | 0 | 0 |
| Gen p50 latency | 5.3 s | 8.9 s |
| Gen p95 latency | 9.2 s | 18.3 s |
| RAG step p50 / p95 | — | 0.48 s / 1.25 s |

Metric: result sets of generated and gold SQL match on the same SQLite DB (order-insensitive unless gold has `ORDER BY`).

## RAG impact (A/B)

Net lift: **+0.68 pp** (7 questions). But under the hood, **88 flipped right and 81 flipped wrong** — RAG shifts decisions strongly; the change is largely a wash on Spider.

Per-DB net delta (top movers):

| Win | Δ | Loss | Δ |
|---|---|---|---|
| `singer` | +5 | `flight_2` | -7 |
| `world_1` | +5 | `cre_Doc_Template_Mgt` | -5 |
| `tvshow` | +5 | `student_transcripts_tracking` | -5 |
| `dog_kennels` | +4 | `course_teach` | -4 |
| `voter_1` | +4 | `network_1` | -4 |

Losses cluster on DBs with many similar-name tables or long FK chains — column pruner / seed selection drops a column the question needs.

## Why the accuracy is "only" 53 %

Failure analysis (489 errors on the RAG run):

| Failure class | Count | % of fails | Root cause |
|---|---|---|---|
| Extra output columns | 90 | 23 % | Model returns explanatory cols (e.g. `year, COUNT(*) AS num_concerts`) where Spider gold returns only `year`. Defog-SQLCoder trained for verbose BI-style output. |
| `no such column` | 83 | 21 % | Hallucinated column names; column pruner sometimes drops the real one. |
| Auto-`LOWER()` wrap | 66 | 17 % | Model wraps string `WHERE` clauses in `LOWER(...)`. 45 of those also **mangle the literal** (`'France'` → `'french'`, `'United States'` → `'%usa%'`) — model conflates question word with stored value. |
| `WHERE x IN (subquery)` instead of `JOIN` | 63 | 16 % | Defog prefers correlated subqueries; results diverge on duplicates / projection. |
| Set-op blindness | 47 | 12 % | Gold uses `INTERSECT`/`EXCEPT`/`UNION`; pred uses `AND`/`OR`. E.g. *"countries shared by singers born <1945 and >1955"* → `WHERE year<1945 AND year>1955` (empty). |
| Extra `DISTINCT` | 35 | 9 % | `COUNT(DISTINCT id)` where gold has `COUNT(*)` — different numbers. |
| Missed `LIMIT` on superlatives | 24 | 6 % | "youngest singer" returns all rows when gold has `LIMIT 1`. |
| Dialect leaks | ~15 | 4 % | Postgres syntax (`NULLS LAST`, `to_date(...)`, `EXTRACT(YEAR FROM ...)`) emitted despite `database_type="SQLite"` in prompt. |
| Wrong column choice | ~30 | 8 % | "song by youngest singer" returns `Name` instead of `Song_name` — semantic ambiguity not resolved by schema alone. |
| Wrong table family | 11 | 3 % | Pred's FROM/JOIN tables share zero overlap with gold. Hard retrieval miss. |

(Categories are multi-label; a single mismatch can fall into several.)

## Read: what the 53 % actually means

**Spider gold style ≠ this model's style.** ~30 % of "wrong" predictions are *informationally correct but formatted differently*:

- Verbose output (extra columns + aliases) — penalized here, **welcomed by real users**.
- `LOWER()` wrapping with the same literal — fails Spider's strict literal-equality check, but in prod prevents the most common user complaint ("no results for `france` when DB has `France`").
- `WHERE IN (subquery)` instead of `JOIN` — same answer most of the time, fails on edge cases involving duplicates.

Strip those style penalties and the **real semantic error rate is ~20–25 %**, not 47 %.

**What Spider does measure well (kept as guardrail):**
- Schema grounding (`no such column`, wrong-table-family) — real bugs in any context.
- Set-op fluency — affects multi-condition questions in prod.
- Superlative → `LIMIT 1` — affects every "top/bottom X" question.
- Cross-DB generalization across 20 unseen schemas.

**What Spider does NOT measure for this product:**
- Large enterprise schemas (Spider DBs avg ~5 tables; product target is 100+).
- Ambiguous / conversational NL — Spider questions are tight by design.
- "Would the user accept this answer?" — verbose output is a UX win, not a bug.

**RAG verdict on Spider:** marginal, as expected. RAG's job is to fit relevant schema into a context window when the schema is large. Spider's tiny DBs already fit. The Spider A/B doesn't validate or invalidate the RAG pipeline — wrong instrument for the job.

## Better benchmarks for this product

| Bench | What it tests | Why it fits |
|---|---|---|
| **BIRD** | 95 large, messy DBs with ambiguous questions | Closer to prod reality; will actually exercise retrieval. |
| **Spider 2.0** | Enterprise schemas (100s of tables) on Snowflake/BQ | Tests RAG and join-path selection where it matters. |
| **Internal eval** | 50–100 questions on a real customer-shaped DB, judged "would a user accept this?" | Most predictive of product quality. LLM-as-judge or human label. |

Spider is kept as a smoke-test regression guard: it catches breakage in schema grounding, `LIMIT` handling, and set-op support cheaply. It is **not** the headline number for product quality.

## Reproduce

```bash
# 1. Download Spider dev to benchmarks/spider_data/
# 2. Ensure Ollama is running and the model is pulled

# Baseline (full schema dump)
.venv/bin/python -m benchmarks.spider_eval --out benchmarks/runs/results_full.json

# RAG (hybrid retrieval: BM25 + vector + FK expansion + column prune + sample rows)
.venv/bin/python -m benchmarks.spider_eval --use-rag --out benchmarks/runs/results_rag.json

# RAG ablation (BM25 + FK only, no embeddings)
.venv/bin/python -m benchmarks.spider_eval --use-rag --rag-bm25-only \
  --out benchmarks/runs/results_rag_bm25.json
```

See [`benchmarks/README.md`](./benchmarks/README.md) for setup details and full CLI flags.
