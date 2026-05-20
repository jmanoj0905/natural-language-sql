"""Tests for app.core.database.retrieval.rrf.rrf_fuse."""

import pytest
from app.core.database.retrieval.rrf import rrf_fuse


class TestRRFFuse:
    def test_single_ranker_passthrough(self):
        """A single ranking is returned in the same order."""
        ranking = ["a", "b", "c", "d"]
        result = rrf_fuse([ranking])
        assert result == ranking

    def test_two_rankers_disjoint_top_items_both_in_top_two(self):
        """Two rankers with completely disjoint items: both top-1 items appear in top-2.

        r1 = ["alpha"]  — only contains alpha
        r2 = ["beta"]   — only contains beta
        Both score 1/(k+1) → tied → tie-break by first appearance → alpha wins.
        Both appear in the output and neither is absent.
        """
        r1 = ["alpha"]
        r2 = ["beta"]
        result = rrf_fuse([r1, r2])
        assert set(result) == {"alpha", "beta"}
        # Both were rank-1 in their respective (only) ranking → tied → alpha wins (r1 first)
        assert result[0] == "alpha"
        assert result[1] == "beta"

    def test_empty_rankings_list_returns_empty(self):
        """No rankings → empty result."""
        result = rrf_fuse([])
        assert result == []

    def test_item_in_multiple_rankings_ranks_higher_than_single(self):
        """
        'shared' appears at rank-1 in both rankings.
        'only_r1' appears only in r1 at rank-2.
        'only_r2' appears only in r2 at rank-2.
        'shared' must outrank both singletons.
        """
        r1 = ["shared", "only_r1"]
        r2 = ["shared", "only_r2"]
        result = rrf_fuse([r1, r2])
        assert result[0] == "shared"

    def test_deterministic_tie_break_earlier_ranking_wins(self):
        """
        Tie-break rule: when two items have equal fused scores because they appear
        in different rankings at the same rank position, the item from the
        earlier-listed ranking wins (i.e., the one that appears first across all
        rankings in order).

        Setup:
          r1 = ["apple"]   — 'apple' only in r1 at rank 1
          r2 = ["banana"]  — 'banana' only in r2 at rank 1

        Both receive score 1/(60+1+1) = 1/62 (k=60, i=0 → rank 1).
        Tie-break: 'apple' appears first in r1 (earlier ranking) so it wins.
        """
        r1 = ["apple"]
        r2 = ["banana"]
        result = rrf_fuse([r1, r2], k=60)
        # apple comes from r1 (index 0), banana from r2 (index 1)
        # both at rank 1 → equal score → apple wins by first-appearance order
        assert result[0] == "apple", (
            "Expected 'apple' to win the tie because it appears in the "
            "earlier-listed ranking (r1 before r2)"
        )

    def test_scores_accumulate_across_rankings(self):
        """
        'common' at rank-1 in both rankings must outscore 'unique' at rank-1
        in only one ranking.
        Score(common) = 2 * 1/(k+1); Score(unique) = 1/(k+1)
        """
        k = 60
        r1 = ["common", "unique"]
        r2 = ["common"]
        result = rrf_fuse([r1, r2], k=k)
        common_idx = result.index("common")
        unique_idx = result.index("unique")
        assert common_idx < unique_idx

    def test_single_item_single_ranking(self):
        """Trivial case: one item in one ranking."""
        result = rrf_fuse([["solo"]])
        assert result == ["solo"]

    def test_empty_sublists_handled(self):
        """Sublists may be empty — they contribute nothing."""
        result = rrf_fuse([[], ["a", "b"], []])
        assert result == ["a", "b"]

    def test_custom_k_value(self):
        """A different k shifts scores but relative ordering is preserved for non-ties."""
        r1 = ["x", "y", "z"]
        for k in [1, 10, 100]:
            result = rrf_fuse([r1], k=k)
            assert result == r1, f"Order should be preserved for k={k}"

    def test_all_items_present_in_output(self):
        """Every item that appears in any ranking must appear in the output."""
        r1 = ["a", "b", "c"]
        r2 = ["d", "e"]
        result = rrf_fuse([r1, r2])
        assert set(result) == {"a", "b", "c", "d", "e"}
