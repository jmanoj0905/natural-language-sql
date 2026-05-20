"""Tests for SchemaCorpusBuilder — plan §7.1."""
from __future__ import annotations

import pytest

from app.core.database.retrieval.corpus import SchemaCorpus, SchemaCorpusBuilder


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tables_3():
    return [
        {
            "name": "customer",
            "columns": [
                {"name": "id",    "type": "int"},
                {"name": "name",  "type": "varchar"},
                {"name": "email", "type": "varchar"},
            ],
        },
        {
            "name": "orders",
            "columns": [
                {"name": "id",          "type": "int"},
                {"name": "customer_id", "type": "int"},
                {"name": "total",       "type": "numeric"},
            ],
        },
        {
            "name": "product",
            "columns": [
                {"name": "id",    "type": "int"},
                {"name": "name",  "type": "varchar"},
                {"name": "price", "type": "numeric"},
                {"name": "sku",   "type": "varchar"},
            ],
        },
    ]


@pytest.fixture
def fk_both_exist():
    """FK where both endpoints exist in tables_3."""
    return [
        {
            "table":      "orders",
            "column":     "customer_id",
            "ref_table":  "customer",
            "ref_column": "id",
        }
    ]


@pytest.fixture
def fk_missing_endpoint():
    """FK where ref_table 'invoice' does NOT exist in tables_3."""
    return [
        {
            "table":      "orders",
            "column":     "invoice_id",
            "ref_table":  "invoice",
            "ref_column": "id",
        }
    ]


@pytest.fixture
def builder():
    return SchemaCorpusBuilder()


# ---------------------------------------------------------------------------
# Empty input
# ---------------------------------------------------------------------------

class TestEmptyInput:
    def test_empty_tables_info_gives_empty_corpus(self, builder):
        corpus = builder.build([], [])

        assert isinstance(corpus, SchemaCorpus)
        assert corpus.table_docs  == []
        assert corpus.column_docs == []
        assert corpus.path_docs   == []


# ---------------------------------------------------------------------------
# Table docs
# ---------------------------------------------------------------------------

class TestTableDocs:
    def test_count_equals_number_of_tables(self, builder, tables_3):
        corpus = builder.build(tables_3, [])
        assert len(corpus.table_docs) == 3

    def test_table_doc_key_is_table_name(self, builder, tables_3):
        corpus = builder.build(tables_3, [])
        keys = [key for key, _ in corpus.table_docs]
        assert keys == ["customer", "orders", "product"]

    def test_table_doc_text_contains_name(self, builder, tables_3):
        corpus = builder.build(tables_3, [])
        customer_doc = next(doc for key, doc in corpus.table_docs if key == "customer")
        assert "customer" in customer_doc

    def test_table_doc_text_contains_column_names(self, builder, tables_3):
        corpus = builder.build(tables_3, [])
        customer_doc = next(doc for key, doc in corpus.table_docs if key == "customer")
        assert "id" in customer_doc
        assert "name" in customer_doc
        assert "email" in customer_doc

    def test_table_doc_format(self, builder, tables_3):
        """Exact template: '{name}. columns: {c1, c2}. types: {t1, t2}'"""
        corpus = builder.build(tables_3, [])
        customer_doc = next(doc for key, doc in corpus.table_docs if key == "customer")
        assert customer_doc == "customer. columns: id, name, email. types: int, varchar, varchar"

    def test_table_doc_order_follows_tables_info_order(self, builder, tables_3):
        corpus = builder.build(tables_3, [])
        assert corpus.table_docs[0][0] == "customer"
        assert corpus.table_docs[1][0] == "orders"
        assert corpus.table_docs[2][0] == "product"


# ---------------------------------------------------------------------------
# Column docs
# ---------------------------------------------------------------------------

class TestColumnDocs:
    def test_count_equals_total_columns(self, builder, tables_3):
        # customer(3) + orders(3) + product(4) = 10
        corpus = builder.build(tables_3, [])
        assert len(corpus.column_docs) == 10

    def test_column_doc_key_is_table_column_pair(self, builder, tables_3):
        corpus = builder.build(tables_3, [])
        first_key, _ = corpus.column_docs[0]
        assert first_key == ("customer", "id")

    def test_column_doc_text_contains_name_type_table(self, builder, tables_3):
        corpus = builder.build(tables_3, [])
        # Find the email column doc for customer
        email_doc = next(
            doc for (tbl, col), doc in corpus.column_docs
            if tbl == "customer" and col == "email"
        )
        assert "email" in email_doc
        assert "varchar" in email_doc
        assert "customer" in email_doc

    def test_column_doc_exact_format(self, builder, tables_3):
        """Exact template: '{column} ({type}) in table {table}'"""
        corpus = builder.build(tables_3, [])
        email_doc = next(
            doc for (tbl, col), doc in corpus.column_docs
            if tbl == "customer" and col == "email"
        )
        assert email_doc == "email (varchar) in table customer"

    def test_column_docs_order(self, builder, tables_3):
        """Columns listed in tables_info order, tables then columns."""
        corpus = builder.build(tables_3, [])
        keys = [(tbl, col) for (tbl, col), _ in corpus.column_docs]
        expected_start = [
            ("customer", "id"),
            ("customer", "name"),
            ("customer", "email"),
            ("orders", "id"),
        ]
        assert keys[:4] == expected_start


# ---------------------------------------------------------------------------
# Path docs
# ---------------------------------------------------------------------------

class TestPathDocs:
    def test_path_doc_generated_when_both_endpoints_exist(
        self, builder, tables_3, fk_both_exist
    ):
        corpus = builder.build(tables_3, fk_both_exist)
        assert len(corpus.path_docs) == 1

    def test_path_doc_skipped_when_endpoint_missing(
        self, builder, tables_3, fk_missing_endpoint
    ):
        corpus = builder.build(tables_3, fk_missing_endpoint)
        assert corpus.path_docs == []

    def test_path_doc_key_is_tableA_tableB(
        self, builder, tables_3, fk_both_exist
    ):
        corpus = builder.build(tables_3, fk_both_exist)
        key, _ = corpus.path_docs[0]
        assert key == ("orders", "customer")

    def test_path_doc_exact_format(self, builder, tables_3, fk_both_exist):
        """Exact template per plan §4.2."""
        corpus = builder.build(tables_3, fk_both_exist)
        _, doc = corpus.path_docs[0]
        expected = (
            "join orders and customer on customer_id=id. "
            "tableA columns: id, customer_id, total. "
            "tableB columns: id, name, email"
        )
        assert doc == expected

    def test_no_path_docs_when_no_fks(self, builder, tables_3):
        corpus = builder.build(tables_3, [])
        assert corpus.path_docs == []

    def test_multiple_fks_mixed_validity(self, builder, tables_3):
        """One valid FK + one missing-endpoint FK → only 1 path doc."""
        fks = [
            {
                "table":      "orders",
                "column":     "customer_id",
                "ref_table":  "customer",
                "ref_column": "id",
            },
            {
                "table":      "orders",
                "column":     "ghost_id",
                "ref_table":  "ghost_table",
                "ref_column": "id",
            },
        ]
        corpus = builder.build(tables_3, fks)
        assert len(corpus.path_docs) == 1


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------

class TestDeterminism:
    def test_same_input_same_output(self, builder, tables_3, fk_both_exist):
        c1 = builder.build(tables_3, fk_both_exist)
        c2 = builder.build(tables_3, fk_both_exist)
        assert c1 == c2
