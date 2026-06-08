# Benchmarks

Execution-accuracy eval on the [Spider](https://yale-lily.github.io/spider) dev set.

## Latest run

| Metric | Value |
|---|---|
| Model | `mannix/defog-llama3-sqlcoder-8b` (Ollama, local) |
| Dataset | Spider dev (1034 questions, 20 databases) |
| **Execution accuracy** | **52.32 %** (541 / 1034) |
| p50 latency | 5.3 s |
| p95 latency | 9.2 s |
| Mismatch | 386 |
| Execution error | 107 |
| Generation error | 0 |

Metric: result sets of generated and gold SQL match on the same SQLite DB (order-insensitive unless gold has `ORDER BY`).

## Reproduce

```bash
# 1. Download Spider dev to benchmarks/spider_data/
# 2. Ensure Ollama is running and the model is pulled
.venv/bin/python -m benchmarks.spider_eval --out benchmarks/runs/results_full.json
```

See [`benchmarks/README.md`](./benchmarks/README.md) for setup details and CLI flags.
