# Spider Benchmark

Execution-accuracy eval for the NL→SQL engine on the Spider dev set.

## Setup

1. Download Spider: https://yale-lily.github.io/spider
2. Unzip so structure is:
   ```
   benchmarks/spider/
     dev.json
     tables.json
     database/<db_id>/<db_id>.sqlite
   ```
3. Ensure Ollama is running and the configured model is pulled:
   ```bash
   ollama pull mannix/defog-llama3-sqlcoder-8b
   ```

## Run

```bash
# Quick 100-question slice
.venv/bin/python -m benchmarks.spider_eval --limit 100

# Full dev set
.venv/bin/python -m benchmarks.spider_eval

# Different model
.venv/bin/python -m benchmarks.spider_eval --model qwen2.5-coder:7b --limit 100

# Output to file
.venv/bin/python -m benchmarks.spider_eval --limit 100 --out results.json
```

## Metric

**Execution accuracy**: run generated SQL and gold SQL on the same SQLite DB, compare result sets
(order-insensitive unless gold has `ORDER BY`).

Reports: accuracy %, p50/p95 latency, error breakdown (gen-fail, exec-fail, mismatch).

## Notes

- Spider DBs are SQLite — eval bypasses the app's PG/MySQL adapters and calls `prompts.py` +
  `ollama_client.py` directly, then executes via stdlib `sqlite3`.
- Prompt uses `database_type="SQLite"` so dialect hints match.
