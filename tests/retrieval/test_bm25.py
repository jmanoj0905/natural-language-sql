"""Tests for BM25Ranker (§7.1)."""

import pytest

from app.core.database.retrieval.bm25 import BM25Ranker, TableScore


class TestBM25RankerEmptyCorpus:
    """Empty corpus yields an empty ranking."""

    def test_empty_tables_returns_empty_list(self):
        ranker = BM25Ranker()
        result = ranker.rank_tables("show me orders", [])
        assert result == []


class TestBM25RankerTableNameMatch:
    """Question that mentions a table name ranks that table #1."""

    def test_orders_question_ranks_orders_first(self, fake_tables_info):
        ranker = BM25Ranker()
        result = ranker.rank_tables("show me the orders", fake_tables_info)
        assert result[0].name == "orders"

    def test_result_is_list_of_table_scores(self, fake_tables_info):
        ranker = BM25Ranker()
        result = ranker.rank_tables("show me the orders", fake_tables_info)
        assert all(isinstance(item, TableScore) for item in result)
        assert len(result) == len(fake_tables_info)

    def test_top_score_is_positive(self, fake_tables_info):
        ranker = BM25Ranker()
        result = ranker.rank_tables("show me the orders", fake_tables_info)
        assert result[0].score > 0


class TestBM25RankerStopwords:
    """Stop words must not affect BM25 scores."""

    def test_stopwords_do_not_change_ranking(self, fake_tables_info):
        ranker = BM25Ranker()
        # "show", "me", "the" are all stop words — stripping them should leave
        # the ranking identical.
        result_with_stops = ranker.rank_tables("show me the orders", fake_tables_info)
        result_without_stops = ranker.rank_tables("orders", fake_tables_info)
        assert [r.name for r in result_with_stops] == [r.name for r in result_without_stops]

    def test_pure_stopwords_question_gives_zero_scores(self, fake_tables_info):
        ranker = BM25Ranker()
        result = ranker.rank_tables("show me the", fake_tables_info)
        assert all(item.score == 0 for item in result)


class TestBM25RankerPluralNormalisation:
    """Plural 'customers' should match the 'customer' table."""

    def test_plural_customers_matches_customer_table(self, fake_tables_info):
        ranker = BM25Ranker()
        result = ranker.rank_tables("list all customers", fake_tables_info)
        assert result[0].name == "customer"

    def test_plural_products_matches_product_table(self, fake_tables_info):
        ranker = BM25Ranker()
        result = ranker.rank_tables("show products", fake_tables_info)
        assert result[0].name == "product"
