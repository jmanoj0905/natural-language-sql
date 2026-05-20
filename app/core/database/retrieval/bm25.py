"""BM25 lexical ranking for database tables.

Ported directly from ``app.core.database.schema_retriever`` — pure refactor,
no behaviour change.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from math import log
from typing import Any


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TOKEN_PATTERN = re.compile(r"[a-zA-Z][a-zA-Z0-9]*")

STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "by",
    "for",
    "from",
    "give",
    "list",
    "me",
    "of",
    "on",
    "show",
    "the",
    "to",
    "what",
    "with",
}


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TableScore:
    name: str
    score: int


# ---------------------------------------------------------------------------
# Module-level helpers (pure functions)
# ---------------------------------------------------------------------------


def _normalize_token(token: str) -> str:
    """Apply minimal stemming: strip plural suffixes."""
    if len(token) > 3 and token.endswith("ies"):
        return f"{token[:-3]}y"
    if len(token) > 3 and token.endswith("s"):
        return token[:-1]
    return token


def _tokenize(text: str) -> list[str]:
    """Tokenize *text* into lower-cased, stop-word-filtered, normalised tokens."""
    tokens: list[str] = []
    for raw_token in TOKEN_PATTERN.findall(text):
        token = raw_token.lower()
        tokens.extend(
            _normalize_token(part)
            for part in token.split("_")
            if part and part not in STOP_WORDS
        )
    return tokens


def _table_document_tokens(table: dict[str, Any]) -> list[str]:
    """Build a weighted token list for a table (name weighted x3, columns x2)."""
    tokens = _tokenize(table["name"]) * 3
    for column in table.get("columns", []):
        tokens.extend(_tokenize(column["name"]) * 2)
        tokens.extend(_tokenize(column["type"]))
    return tokens


def _bm25_score(
    query_terms: list[str],
    document_terms: list[str],
    all_documents: list[list[str]],
    document_count: int,
    average_length: float,
    k1: float = 1.5,
    b: float = 0.75,
) -> float:
    """Return the BM25 relevance score for *document_terms* given *query_terms*."""
    if not query_terms or not document_terms:
        return 0.0

    term_frequencies = Counter(document_terms)
    document_length = len(document_terms)
    score = 0.0

    for term in set(query_terms):
        matching_documents = sum(1 for document in all_documents if term in document)
        if matching_documents == 0:
            continue

        idf = log(
            1
            + (document_count - matching_documents + 0.5)
            / (matching_documents + 0.5)
        )
        frequency = term_frequencies[term]
        denominator = frequency + k1 * (
            1 - b + b * (document_length / max(average_length, 1))
        )
        score += idf * ((frequency * (k1 + 1)) / denominator)

    return score


# ---------------------------------------------------------------------------
# Public class
# ---------------------------------------------------------------------------


class BM25Ranker:
    """Rank database tables against a natural-language question using BM25."""

    def rank_tables(
        self,
        question: str,
        tables_info: list[dict[str, Any]],
    ) -> list[TableScore]:
        """Return *tables_info* sorted by BM25 relevance (highest first).

        Identical output to the old ``SchemaGraphRetriever._rank_tables``.
        """
        if not tables_info:
            return []

        question_terms = _tokenize(question)
        table_documents = {
            table["name"]: _table_document_tokens(table)
            for table in tables_info
        }
        document_count = max(len(table_documents), 1)
        average_length = (
            sum(len(tokens) for tokens in table_documents.values()) / document_count
        )

        scores: list[TableScore] = []
        for table in tables_info:
            table_name = table["name"]
            raw_score = _bm25_score(
                query_terms=question_terms,
                document_terms=table_documents[table_name],
                all_documents=list(table_documents.values()),
                document_count=document_count,
                average_length=average_length,
            )
            scores.append(TableScore(name=table_name, score=round(raw_score * 1000)))

        return sorted(scores, key=lambda item: (-item.score, item.name))
