"""Shared fixtures for retrieval tests."""

import pytest


@pytest.fixture
def fake_tables_info():
    return [
        {
            "name": "customer",
            "columns": [
                {"name": "id", "type": "int"},
                {"name": "name", "type": "varchar"},
                {"name": "email", "type": "varchar"},
            ],
        },
        {
            "name": "orders",
            "columns": [
                {"name": "id", "type": "int"},
                {"name": "customer_id", "type": "int"},
                {"name": "total", "type": "numeric"},
            ],
        },
        {
            "name": "product",
            "columns": [
                {"name": "id", "type": "int"},
                {"name": "name", "type": "varchar"},
                {"name": "price", "type": "numeric"},
                {"name": "sku", "type": "varchar"},
            ],
        },
    ]


@pytest.fixture
def fake_foreign_keys():
    return [
        {
            "table": "orders",
            "column": "customer_id",
            "ref_table": "customer",
            "ref_column": "id",
        }
    ]
