"""Execution-accuracy comparison for Spider."""

from __future__ import annotations

import sqlite3
from typing import List, Tuple


def _rows(cur: sqlite3.Cursor) -> List[Tuple]:
    return [tuple(r) for r in cur.fetchall()]


def execute(db_path: str, sql: str, timeout: float = 10.0) -> List[Tuple]:
    conn = sqlite3.connect(db_path, timeout=timeout)
    conn.text_factory = lambda b: b.decode("utf-8", errors="replace")
    try:
        cur = conn.cursor()
        cur.execute(sql)
        return _rows(cur)
    finally:
        conn.close()


def results_match(gold_rows: List[Tuple], pred_rows: List[Tuple], order_matters: bool) -> bool:
    if order_matters:
        return gold_rows == pred_rows
    # Multiset compare
    try:
        return sorted(gold_rows) == sorted(pred_rows)
    except TypeError:
        # Unhashable / unsortable mixed types — fall back to string repr sort
        return sorted(map(repr, gold_rows)) == sorted(map(repr, pred_rows))


def gold_has_order_by(sql: str) -> bool:
    return "order by" in sql.lower()
