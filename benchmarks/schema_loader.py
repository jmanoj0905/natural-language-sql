"""Build schema_context strings from Spider's tables.json."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List


def load_tables(tables_json: Path) -> Dict[str, dict]:
    with tables_json.open() as f:
        raw = json.load(f)
    return {entry["db_id"]: entry for entry in raw}


def build_schema_context(db_entry: dict) -> str:
    """Render Spider tables.json entry as CREATE-TABLE-ish text for the prompt."""
    table_names: List[str] = db_entry["table_names_original"]
    columns = db_entry["column_names_original"]  # [(table_idx, col_name), ...]
    col_types: List[str] = db_entry["column_types"]
    pks = set(db_entry.get("primary_keys", []))
    fks = db_entry.get("foreign_keys", [])  # [[col_idx_from, col_idx_to], ...]

    by_table: Dict[int, List[str]] = {i: [] for i in range(len(table_names))}
    for col_idx, (tbl_idx, col_name) in enumerate(columns):
        if tbl_idx == -1:
            continue
        ctype = col_types[col_idx]
        pk_marker = " PRIMARY KEY" if col_idx in pks else ""
        by_table[tbl_idx].append(f"  {col_name} {ctype.upper()}{pk_marker}")

    fk_lines: Dict[int, List[str]] = {i: [] for i in range(len(table_names))}
    for src, dst in fks:
        src_tbl, src_col = columns[src]
        dst_tbl, dst_col = columns[dst]
        if src_tbl == -1 or dst_tbl == -1:
            continue
        fk_lines[src_tbl].append(
            f"  FOREIGN KEY ({src_col}) REFERENCES {table_names[dst_tbl]}({dst_col})"
        )

    blocks = []
    for i, tname in enumerate(table_names):
        body = by_table[i] + fk_lines[i]
        blocks.append(f"CREATE TABLE {tname} (\n" + ",\n".join(body) + "\n);")
    return "\n\n".join(blocks)
