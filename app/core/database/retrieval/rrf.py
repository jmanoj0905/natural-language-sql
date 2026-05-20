"""Reciprocal Rank Fusion — pure module, no I/O.

Reference: Cormack, Clarke & Buettcher (2009) "Reciprocal Rank Fusion outperforms
Condorcet and individual Rank Learning Methods".
"""

from __future__ import annotations


def rrf_fuse(rankings: list[list[str]], k: int = 60) -> list[str]:
    """Fuse multiple ranked lists into one using Reciprocal Rank Fusion.

    Scoring:
        score(item) = Σ  1.0 / (k + rank_i)
                      i

    where rank_i is the 1-indexed position of *item* in ranking i
    (rank 1 → 1/(k+1), rank 2 → 1/(k+2), ...).

    Tie-break:
        Items with equal fused scores are ordered by *first appearance* across
        all rankings in input order.  Concretely, the item encountered earliest
        when scanning rankings[0] left-to-right, then rankings[1], etc., wins.
        This is stable because we track insertion order via an ordered dict.

    Args:
        rankings: List of ranked lists.  May contain duplicate items within a
                  single ranking (first occurrence governs that ranking's rank).
        k:        Rank constant (default 60).

    Returns:
        A deduplicated list of all items sorted by descending fused score, with
        ties broken by first-appearance order (earlier = better).
    """
    if not rankings:
        return []

    # scores[item] = accumulated RRF score
    scores: dict[str, float] = {}
    # first_seen order — insertion order of dict is guaranteed in Python 3.7+
    first_seen: dict[str, None] = {}

    for ranking in rankings:
        seen_in_this_ranking: set[str] = set()
        rank = 0  # 0-indexed; converted to 1-indexed inside loop
        for item in ranking:
            if item in seen_in_this_ranking:
                continue  # only first occurrence counts per ranking
            seen_in_this_ranking.add(item)
            rank += 1  # now 1-indexed rank for this item
            scores[item] = scores.get(item, 0.0) + 1.0 / (k + rank)
            if item not in first_seen:
                first_seen[item] = None

    # Build a stable first-appearance index for tie-breaking
    first_seen_index: dict[str, int] = {item: i for i, item in enumerate(first_seen)}

    return sorted(
        scores.keys(),
        key=lambda item: (-scores[item], first_seen_index[item]),
    )
