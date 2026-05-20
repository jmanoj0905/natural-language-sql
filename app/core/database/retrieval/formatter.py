"""
Pure formatting function that renders selected schema tables + foreign keys
into a SQL-comment context block consumed by the AI prompt builder.

No I/O, no globals — fully deterministic given the same inputs.
"""

from __future__ import annotations


def format_schema_context(
    selected_tables: list[dict],
    foreign_keys: list[dict],
    sample_rows_by_table: dict[str, list[dict]] | None = None,
    fallback_used: bool = False,
) -> str:
    """Return a formatted schema context string for the AI prompt.

    Parameters
    ----------
    selected_tables:
        Each dict must have at minimum ``{"name": str, "columns": list}``.
        Each column dict: ``{"name": str, "type": str, "nullable"?: bool,
        "default"?: Any}``.
    foreign_keys:
        Each dict: ``{"table": str, "column": str, "ref_table": str,
        "ref_column": str}``.
    sample_rows_by_table:
        Optional mapping of table name → list of row dicts (column → value).
        When provided, sample rows are appended after each table's ``);``.
    fallback_used:
        When ``True``, prepend a notice that lexical matching found no results.

    Returns
    -------
    str
        Formatted context block.  No trailing newline.
    """
    if not selected_tables:
        return "-- No tables found in this database."

    selected_names: set[str] = {table["name"] for table in selected_tables}
    lines: list[str] = []

    # Optional fallback notice
    if fallback_used:
        lines.append(
            "-- Schema retrieval had no lexical matches; showing a bounded fallback."
        )

    # Header
    lines.append("-- AVAILABLE TABLES (use only these exact names, do not guess):")
    lines.append("--   " + ", ".join(table["name"] for table in selected_tables))
    lines.append("")

    # CREATE TABLE blocks
    for table in selected_tables:
        table_name: str = table["name"]
        lines.append(f"CREATE TABLE {table_name} (")

        col_lines: list[str] = []

        # Columns
        for col in table.get("columns", []):
            parts = [f"  {col['name']} {col['type']}"]
            if col.get("nullable") is False:
                parts.append("NOT NULL")
            if col.get("default"):
                parts.append(f"DEFAULT {col['default']}")
            col_lines.append(" ".join(parts))

        # Inline foreign keys (only when ref_table is also selected)
        for fk in foreign_keys:
            if fk["table"] == table_name and fk["ref_table"] in selected_names:
                col_lines.append(
                    f"  FOREIGN KEY ({fk['column']}) REFERENCES"
                    f" {fk['ref_table']}({fk['ref_column']})"
                )

        lines.append(",\n".join(col_lines))
        lines.append(");")

        # Sample rows
        if sample_rows_by_table is not None:
            rows = sample_rows_by_table.get(table_name, [])
            if rows:
                lines.append(f"-- Sample rows from {table_name}:")
                for row in rows:
                    row_str = ", ".join(f"{k}={repr(v)}" for k, v in row.items())
                    lines.append(f"--   {row_str}")

        lines.append("")  # blank line after each table block

    # Relationships footer
    matching_fks = [
        fk
        for fk in foreign_keys
        if fk["table"] in selected_names and fk["ref_table"] in selected_names
    ]
    if matching_fks:
        lines.append("-- RELATIONSHIPS (use these for JOINs):")
        for fk in matching_fks:
            lines.append(
                f"--   {fk['table']}.{fk['column']} -> "
                f"{fk['ref_table']}.{fk['ref_column']}"
            )

    # Strip any trailing empty lines before joining so the output has no
    # trailing newline regardless of whether a relationships footer was added.
    while lines and lines[-1] == "":
        lines.pop()

    return "\n".join(lines)
