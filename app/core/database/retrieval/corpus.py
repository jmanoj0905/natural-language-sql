"""Schema corpus: builds document lists for lexical/vector retrieval."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SchemaCorpus:
    table_docs:  list[tuple[str, str]]                # (table, doc_text)
    column_docs: list[tuple[tuple[str, str], str]]    # ((table, column), doc_text)
    path_docs:   list[tuple[tuple[str, str], str]]    # ((tableA, tableB), doc_text)


class SchemaCorpusBuilder:
    """Builds a :class:`SchemaCorpus` from raw schema metadata.

    All output is deterministic: order follows the input order of
    ``tables_info`` (tables, then columns within each table) and
    ``foreign_keys``.  No global state is mutated.
    """

    def build(
        self,
        tables_info: list[dict],   # {"name", "columns": [{"name","type",...}, ...]}
        foreign_keys: list[dict],  # {"table","column","ref_table","ref_column"}
    ) -> SchemaCorpus:
        # Build a lookup {table_name -> column list} for FK path generation.
        table_lookup: dict[str, list[dict]] = {
            t["name"]: t["columns"] for t in tables_info
        }

        table_docs  = self._build_table_docs(tables_info)
        column_docs = self._build_column_docs(tables_info)
        path_docs   = self._build_path_docs(foreign_keys, table_lookup)

        return SchemaCorpus(
            table_docs=table_docs,
            column_docs=column_docs,
            path_docs=path_docs,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_table_docs(tables_info: list[dict]) -> list[tuple[str, str]]:
        docs: list[tuple[str, str]] = []
        for table in tables_info:
            name = table["name"]
            columns = table["columns"]
            col_names = ", ".join(c["name"] for c in columns)
            col_types = ", ".join(c["type"] for c in columns)
            doc = f"{name}. columns: {col_names}. types: {col_types}"
            docs.append((name, doc))
        return docs

    @staticmethod
    def _build_column_docs(
        tables_info: list[dict],
    ) -> list[tuple[tuple[str, str], str]]:
        docs: list[tuple[tuple[str, str], str]] = []
        for table in tables_info:
            tbl_name = table["name"]
            for col in table["columns"]:
                col_name = col["name"]
                col_type = col["type"]
                doc = f"{col_name} ({col_type}) in table {tbl_name}"
                docs.append(((tbl_name, col_name), doc))
        return docs

    @staticmethod
    def _build_path_docs(
        foreign_keys: list[dict],
        table_lookup: dict[str, list[dict]],
    ) -> list[tuple[tuple[str, str], str]]:
        docs: list[tuple[tuple[str, str], str]] = []
        for fk in foreign_keys:
            table_a = fk["table"]
            col_a   = fk["column"]
            table_b = fk["ref_table"]
            col_b   = fk["ref_column"]

            # Skip if either endpoint is absent from tables_info.
            if table_a not in table_lookup or table_b not in table_lookup:
                continue

            cols_a = ", ".join(c["name"] for c in table_lookup[table_a])
            cols_b = ", ".join(c["name"] for c in table_lookup[table_b])
            doc = (
                f"join {table_a} and {table_b} on {col_a}={col_b}. "
                f"tableA columns: {cols_a}. "
                f"tableB columns: {cols_b}"
            )
            docs.append(((table_a, table_b), doc))
        return docs
