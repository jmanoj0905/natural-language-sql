"""Build schema_context strings from Spider's tables.json."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Dict, List, Tuple


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


def to_rag_schema(db_entry: dict) -> Tuple[List[dict], List[dict]]:
    """Convert Spider tables.json entry → (tables_info, foreign_keys) for HybridRetriever."""
    table_names: List[str] = db_entry["table_names_original"]
    columns = db_entry["column_names_original"]
    col_types: List[str] = db_entry["column_types"]
    fks = db_entry.get("foreign_keys", [])

    by_table: Dict[int, List[dict]] = {i: [] for i in range(len(table_names))}
    for col_idx, (tbl_idx, col_name) in enumerate(columns):
        if tbl_idx == -1:
            continue
        by_table[tbl_idx].append({"name": col_name, "type": col_types[col_idx].upper()})

    tables_info = [
        {"name": tname, "columns": by_table[i]}
        for i, tname in enumerate(table_names)
    ]

    foreign_keys: List[dict] = []
    for src, dst in fks:
        s_t, s_c = columns[src]
        d_t, d_c = columns[dst]
        if s_t == -1 or d_t == -1:
            continue
        foreign_keys.append({
            "table": table_names[s_t],
            "column": s_c,
            "ref_table": table_names[d_t],
            "ref_column": d_c,
        })
    return tables_info, foreign_keys


def spider_schema_hash(db_entry: dict) -> int:
    """Stable content hash for HybridRetriever index cache key."""
    payload = {
        "tables": db_entry["table_names_original"],
        "columns": db_entry["column_names_original"],
        "types": db_entry["column_types"],
        "fks": db_entry.get("foreign_keys", []),
    }
    blob = json.dumps(payload, sort_keys=True).encode()
    return int(hashlib.sha256(blob).hexdigest()[:15], 16)
