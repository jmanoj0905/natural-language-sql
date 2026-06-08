"""Spider dev-set execution-accuracy eval.

Usage:
    python -m benchmarks.spider_eval --limit 100
    python -m benchmarks.spider_eval --model qwen2.5-coder:7b --out results.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import time
from pathlib import Path
from typing import Optional

from app.core.ai.ollama_client import generate_with_config
from app.core.ai.prompts import build_sql_generation_prompt, extract_sql_from_response
from benchmarks.exec_match import execute, gold_has_order_by, results_match
from benchmarks.schema_loader import build_schema_context, load_tables

SPIDER_DIR = Path(__file__).parent / "spider_data"


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


async def run(limit: Optional[int], model: str, out: Optional[Path]) -> None:
    dev = json.loads((SPIDER_DIR / "dev.json").read_text())
    tables = load_tables(SPIDER_DIR / "tables.json")
    if limit:
        dev = dev[:limit]

    schema_cache: dict[str, str] = {}
    records, latencies = [], []
    counts = {"correct": 0, "gen_fail": 0, "exec_fail": 0, "mismatch": 0, "gold_fail": 0}

    for i, ex in enumerate(dev):
        db_id = ex["db_id"]
        question = ex["question"]
        gold_sql = ex["query"]
        db_path = str(SPIDER_DIR / "database" / db_id / f"{db_id}.sqlite")

        schema_ctx = schema_cache.setdefault(db_id, build_schema_context(tables[db_id]))

        rec = {"idx": i, "db_id": db_id, "question": question, "gold": gold_sql}
        t0 = time.perf_counter()
        try:
            pred_sql = await generate_sql(question, schema_ctx, model)
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

        try:
            gold_rows = execute(db_path, gold_sql)
        except Exception as e:
            counts["gold_fail"] += 1
            rec |= {"status": "gold_fail", "error": str(e)[:300]}
            records.append(rec)
            print(f"[{i+1}/{len(dev)}] {db_id} GOLD_FAIL ({latency:.2f}s)")
            continue

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
        "model": model,
        "total": total,
        "accuracy": round(acc, 4),
        "p50_latency_s": round(p50, 3),
        "p95_latency_s": round(p95, 3),
        "counts": counts,
    }
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
    args = p.parse_args()

    if not (SPIDER_DIR / "dev.json").exists():
        raise SystemExit(
            f"Spider data not found at {SPIDER_DIR}. See benchmarks/README.md for setup."
        )
    asyncio.run(run(args.limit, args.model, args.out))


if __name__ == "__main__":
    main()
