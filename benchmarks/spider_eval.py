"""Spider dev-set execution-accuracy eval.

Usage:
    python -m benchmarks.spider_eval --limit 100
    python -m benchmarks.spider_eval --model qwen2.5-coder:7b --out results.json
    python -m benchmarks.spider_eval --use-rag --out results_rag.json
    python -m benchmarks.spider_eval --use-rag --rag-bm25-only --out results_rag_bm25.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sqlite3
import statistics
import time
from pathlib import Path
from typing import Awaitable, Callable, Optional

from app.config import get_settings
from app.core.ai.ollama_client import generate_with_config
from app.core.ai.prompts import build_sql_generation_prompt, extract_sql_from_response
from benchmarks.exec_match import execute, gold_has_order_by, results_match
from benchmarks.schema_loader import (
    build_schema_context,
    load_tables,
    spider_schema_hash,
    to_rag_schema,
)

SPIDER_DIR = Path(__file__).parent / "spider_data"
RAG_INDEX_DIR = Path(__file__).parent / "runs" / "rag_index"


async def generate_sql(question: str, schema_context: str, model: str) -> str:
    prompt = build_sql_generation_prompt(
        question=question,
        schema_context=schema_context,
        database_type="SQLite",
        read_only=True,
    )
    raw = await generate_with_config(prompt, provider="ollama", model=model, api_key="")
    sql = extract_sql_from_response(raw)
    return (sql or raw).strip().rstrip(";")


def make_sample_fetcher(
    db_path: str, n: int
) -> Callable[[str], Awaitable[list[dict]]]:
    """Return an async fetcher that pulls N sample rows from a SQLite table."""

    def _fetch_sync(table: str) -> list[dict]:
        con = sqlite3.connect(db_path)
        con.row_factory = sqlite3.Row
        try:
            cur = con.execute(f'SELECT * FROM "{table}" LIMIT {n}')
            return [dict(r) for r in cur.fetchall()]
        finally:
            con.close()

    async def fetcher(table: str) -> list[dict]:
        return await asyncio.to_thread(_fetch_sync, table)

    return fetcher


def build_retriever(bm25_only: bool, include_sample_rows: bool):
    """Construct a HybridRetriever using settings defaults."""
    from app.core.ai.schema_embedder import SchemaEmbedder
    from app.core.database.retrieval.hybrid import HybridRetriever

    s = get_settings()
    embedder = None if bm25_only else SchemaEmbedder()
    return HybridRetriever(
        embedder=embedder,
        index_dir=RAG_INDEX_DIR,
        max_seed_tables=s.MAX_SEED_TABLES,
        max_tables=s.MAX_TABLES,
        max_cols_per_table=s.MAX_COLS_PER_TABLE,
        col_score_threshold=s.COLUMN_SCORE_THRESHOLD,
        rrf_k=s.RRF_K,
        include_sample_rows=include_sample_rows,
        hybrid_enabled=not bm25_only,
    )


async def run(
    limit: Optional[int],
    model: str,
    out: Optional[Path],
    use_rag: bool,
    rag_bm25_only: bool,
    rag_no_samples: bool,
    rag_sample_rows: int,
) -> None:
    dev = json.loads((SPIDER_DIR / "dev.json").read_text())
    tables = load_tables(SPIDER_DIR / "tables.json")
    if limit:
        dev = dev[:limit]

    resolved_model = model or get_settings().OLLAMA_MODEL
    mode = "rag" if use_rag else "baseline"
    if use_rag and rag_bm25_only:
        mode = "rag_bm25_only"

    retriever = build_retriever(rag_bm25_only, not rag_no_samples) if use_rag else None

    # Baseline path caches per db_id (question-independent).
    # RAG path is question-dependent, no cache.
    schema_cache: dict[str, str] = {}
    records, latencies, rag_latencies = [], [], []
    counts = {"correct": 0, "gen_fail": 0, "exec_fail": 0, "mismatch": 0, "gold_fail": 0}

    for i, ex in enumerate(dev):
        db_id = ex["db_id"]
        question = ex["question"]
        gold_sql = ex["query"]
        db_path = str(SPIDER_DIR / "database" / db_id / f"{db_id}.sqlite")

        # ---- Build schema context ----
        t_ctx = time.perf_counter()
        if use_rag:
            tables_info, fks = to_rag_schema(tables[db_id])
            fetcher = (
                None
                if rag_no_samples
                else make_sample_fetcher(db_path, rag_sample_rows)
            )
            try:
                schema_ctx = await retriever.build_context(
                    question=question,
                    db_id=db_id,
                    schema_hash=spider_schema_hash(tables[db_id]),
                    tables_info=tables_info,
                    foreign_keys=fks,
                    sample_row_fetcher=fetcher,
                )
            except Exception as e:
                counts["gen_fail"] += 1
                records.append({
                    "idx": i, "db_id": db_id, "question": question, "gold": gold_sql,
                    "status": "gen_fail", "error": f"rag_build_failed: {str(e)[:280]}",
                })
                print(f"[{i+1}/{len(dev)}] {db_id} RAG_FAIL")
                continue
        else:
            schema_ctx = schema_cache.setdefault(
                db_id, build_schema_context(tables[db_id])
            )
        rag_latency = time.perf_counter() - t_ctx
        rag_latencies.append(rag_latency)

        rec = {"idx": i, "db_id": db_id, "question": question, "gold": gold_sql}

        # ---- Generate ----
        t0 = time.perf_counter()
        try:
            pred_sql = await generate_sql(question, schema_ctx, resolved_model)
        except Exception as e:
            counts["gen_fail"] += 1
            rec |= {"status": "gen_fail", "error": str(e)[:300]}
            records.append(rec)
            print(f"[{i+1}/{len(dev)}] {db_id} GEN_FAIL")
            continue
        latency = time.perf_counter() - t0
        latencies.append(latency)
        rec["pred"] = pred_sql
        rec["latency_s"] = round(latency, 3)
        if use_rag:
            rec["rag_latency_s"] = round(rag_latency, 3)

        # ---- Execute gold ----
        try:
            gold_rows = execute(db_path, gold_sql)
        except Exception as e:
            counts["gold_fail"] += 1
            rec |= {"status": "gold_fail", "error": str(e)[:300]}
            records.append(rec)
            print(f"[{i+1}/{len(dev)}] {db_id} GOLD_FAIL ({latency:.2f}s)")
            continue

        # ---- Execute pred ----
        try:
            pred_rows = execute(db_path, pred_sql)
        except Exception as e:
            counts["exec_fail"] += 1
            rec |= {"status": "exec_fail", "error": str(e)[:300]}
            records.append(rec)
            print(f"[{i+1}/{len(dev)}] {db_id} EXEC_FAIL ({latency:.2f}s)")
            continue

        ok = results_match(gold_rows, pred_rows, order_matters=gold_has_order_by(gold_sql))
        if ok:
            counts["correct"] += 1
            rec["status"] = "correct"
        else:
            counts["mismatch"] += 1
            rec["status"] = "mismatch"
        records.append(rec)
        print(f"[{i+1}/{len(dev)}] {db_id} {rec['status'].upper()} ({latency:.2f}s)")

    total = len(dev)
    acc = counts["correct"] / total if total else 0.0
    p50 = statistics.median(latencies) if latencies else 0.0
    p95 = (
        statistics.quantiles(latencies, n=20)[18]
        if len(latencies) >= 20
        else max(latencies, default=0.0)
    )

    summary = {
        "model": resolved_model,
        "mode": mode,
        "total": total,
        "accuracy": round(acc, 4),
        "p50_latency_s": round(p50, 3),
        "p95_latency_s": round(p95, 3),
        "counts": counts,
    }
    if use_rag:
        summary["rag_p50_latency_s"] = (
            round(statistics.median(rag_latencies), 3) if rag_latencies else 0.0
        )
        summary["rag_p95_latency_s"] = (
            round(statistics.quantiles(rag_latencies, n=20)[18], 3)
            if len(rag_latencies) >= 20
            else round(max(rag_latencies, default=0.0), 3)
        )
        summary["rag_bm25_only"] = rag_bm25_only
        summary["rag_sample_rows"] = 0 if rag_no_samples else rag_sample_rows

    print("\n=== Summary ===")
    print(json.dumps(summary, indent=2))

    if out:
        out.write_text(json.dumps({"summary": summary, "records": records}, indent=2))
        print(f"\nWrote {out}")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--limit", type=int, default=None, help="Eval first N examples")
    p.add_argument("--model", type=str, default="", help="Ollama model override (empty = config default)")
    p.add_argument("--out", type=Path, default=None, help="Write detailed JSON results to this path")
    p.add_argument("--use-rag", action="store_true", help="Use HybridRetriever schema context instead of full dump")
    p.add_argument("--rag-bm25-only", action="store_true", help="RAG without vector embeddings (BM25 + FK only)")
    p.add_argument("--rag-no-samples", action="store_true", help="Skip sample-row fetching in RAG context")
    p.add_argument("--rag-sample-rows", type=int, default=None, help="Sample rows per table (default = SAMPLE_ROWS_COMPACT)")
    args = p.parse_args()

    if not (SPIDER_DIR / "dev.json").exists():
        raise SystemExit(
            f"Spider data not found at {SPIDER_DIR}. See benchmarks/README.md for setup."
        )

    sample_rows = (
        args.rag_sample_rows
        if args.rag_sample_rows is not None
        else get_settings().SAMPLE_ROWS_COMPACT
    )

    asyncio.run(run(
        args.limit,
        args.model,
        args.out,
        args.use_rag,
        args.rag_bm25_only,
        args.rag_no_samples,
        sample_rows,
    ))


if __name__ == "__main__":
    main()
