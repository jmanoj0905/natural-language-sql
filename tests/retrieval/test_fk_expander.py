"""Tests for app.core.database.retrieval.fk_expander.expand_with_fks."""

import pytest
from app.core.database.retrieval.fk_expander import expand_with_fks


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _lookup(*names: str) -> dict[str, dict]:
    """Build a minimal table_lookup with the given names as keys."""
    return {name: {"name": name} for name in names}


def _fk(table: str, column: str, ref_table: str, ref_column: str) -> dict:
    return {"table": table, "column": column, "ref_table": ref_table, "ref_column": ref_column}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestExpandWithFKs:
    def test_seed_adds_one_hop_neighbors(self):
        """Seeding 'orders' brings in 'customer' via FK orders.customer_id → customer.id."""
        fks = [_fk("orders", "customer_id", "customer", "id")]
        lookup = _lookup("orders", "customer")
        result = expand_with_fks(["orders"], fks, lookup)
        assert result == ["orders", "customer"]

    def test_seed_not_in_lookup_still_expands_known_neighbor(self):
        """If a seed is present in the lookup, its known FK neighbors are included."""
        fks = [_fk("orders", "customer_id", "customer", "id")]
        lookup = _lookup("orders", "customer")
        result = expand_with_fks(["orders"], fks, lookup)
        assert "customer" in result

    def test_cycles_do_not_loop(self):
        """A ↔ B cycle: both A and B appear exactly once in the output."""
        fks = [
            _fk("a", "b_id", "b", "id"),
            _fk("b", "a_id", "a", "id"),
        ]
        lookup = _lookup("a", "b")
        result = expand_with_fks(["a"], fks, lookup)
        assert result.count("a") == 1
        assert result.count("b") == 1
        assert set(result) == {"a", "b"}

    def test_self_fk_listed_once(self):
        """A self-referential FK (employees.manager_id → employees.id) yields the table once."""
        fks = [_fk("employees", "manager_id", "employees", "id")]
        lookup = _lookup("employees")
        result = expand_with_fks(["employees"], fks, lookup)
        assert result == ["employees"]

    def test_fk_ignored_when_endpoint_not_in_lookup(self):
        """FK referencing a table absent from table_lookup is silently ignored."""
        fks = [_fk("orders", "warehouse_id", "warehouse", "id")]
        # 'warehouse' deliberately absent from lookup
        lookup = _lookup("orders")
        result = expand_with_fks(["orders"], fks, lookup)
        assert result == ["orders"]
        assert "warehouse" not in result

    def test_empty_seeds_returns_empty(self):
        """No seeds → empty result regardless of FK graph."""
        fks = [_fk("orders", "customer_id", "customer", "id")]
        lookup = _lookup("orders", "customer")
        result = expand_with_fks([], fks, lookup)
        assert result == []

    def test_seed_order_preserved(self):
        """Seeds are expanded in input order; neighbors appended after each seed."""
        fks = [
            _fk("orders", "customer_id", "customer", "id"),
            _fk("items", "product_id", "product", "id"),
        ]
        lookup = _lookup("orders", "customer", "items", "product")
        result = expand_with_fks(["orders", "items"], fks, lookup)
        # orders first, its neighbor customer next, then items, then product
        assert result.index("orders") < result.index("customer")
        assert result.index("items") < result.index("product")
        # orders before items
        assert result.index("orders") < result.index("items")

    def test_neighbor_already_seen_as_seed_not_duplicated(self):
        """If a neighbor was already added as a seed it is not re-appended."""
        fks = [_fk("orders", "customer_id", "customer", "id")]
        lookup = _lookup("orders", "customer")
        result = expand_with_fks(["orders", "customer"], fks, lookup)
        assert result.count("orders") == 1
        assert result.count("customer") == 1

    def test_empty_fks_returns_seeds_only(self):
        """With no foreign keys, only the seeds themselves are returned."""
        lookup = _lookup("orders", "customer")
        result = expand_with_fks(["orders"], [], lookup)
        assert result == ["orders"]

    def test_neighbors_sorted_alphabetically(self):
        """Multiple neighbors of a seed appear in sorted (alphabetical) order."""
        fks = [
            _fk("hub", "z_id", "zzz", "id"),
            _fk("hub", "a_id", "aaa", "id"),
            _fk("hub", "m_id", "mmm", "id"),
        ]
        lookup = _lookup("hub", "aaa", "mmm", "zzz")
        result = expand_with_fks(["hub"], fks, lookup)
        assert result == ["hub", "aaa", "mmm", "zzz"]
