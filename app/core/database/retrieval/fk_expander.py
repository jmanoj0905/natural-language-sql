"""FK graph expander — pure module, no I/O.

Ported from SchemaRetriever._expand_with_foreign_keys (schema_retriever.py:106-131).
"""

from __future__ import annotations

from collections import defaultdict


def expand_with_fks(
    seeds: list[str],
    foreign_keys: list[dict],            # {"table","column","ref_table","ref_column"}
    table_lookup: dict[str, dict],       # name -> table info dict (used only for membership)
) -> list[str]:
    """Return an ordered list of table names starting from *seeds*, expanded by 1 hop.

    Algorithm (mirrors original):
    1. Build an undirected adjacency map from *foreign_keys*.
       An FK edge is only added when **both** endpoints are present in *table_lookup*.
    2. Walk *seeds* in order.  For each seed:
       - append it (if not yet seen),
       - then append its sorted neighbors (each skipped if already seen).
    3. Return the ordered result.
    """
    neighbors: dict[str, set[str]] = defaultdict(set)
    for fk in foreign_keys:
        table = fk["table"]
        ref_table = fk["ref_table"]
        if table in table_lookup and ref_table in table_lookup:
            neighbors[table].add(ref_table)
            neighbors[ref_table].add(table)

    selected: list[str] = []
    seen: set[str] = set()
    for seed in seeds:
        if seed not in seen:
            selected.append(seed)
            seen.add(seed)
        for neighbor in sorted(neighbors.get(seed, set())):
            if neighbor not in seen:
                selected.append(neighbor)
                seen.add(neighbor)

    return selected
