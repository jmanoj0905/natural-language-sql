"""Query planning module for intent detection and query decomposition."""

import re
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from enum import Enum

from app.utils.logger import get_logger

logger = get_logger(__name__)


class QueryIntent(Enum):
    """Enum for query intent types."""

    SINGLE_DB_READ = "single_db_read"
    SINGLE_DB_WRITE = "single_db_write"
    MULTI_DB_READ = "multi_db_read"
    MULTI_DB_WRITE = "multi_db_write"
    COMPOUND_READ_WRITE = "compound_read_write"
    COMPLEX_FILTER = "complex_filter"
    AGGREGATION = "aggregation"
    MULTI_STEP = "multi_step"
    UNKNOWN = "unknown"


@dataclass
class QueryStep:
    """A single step in a multi-step query plan."""

    step: int
    question: str
    database_id: Optional[str] = None
    database_nickname: Optional[str] = None
    generated_sql: Optional[str] = None
    action: str = "read"
    status: str = "pending"
    depends_on: List[int] = field(default_factory=list)


@dataclass
class QueryPlan:
    """Query plan with detected intent and metadata."""

    intent: QueryIntent
    database_refs: List[str]
    steps: List[QueryStep]
    needs_decomposition: bool
    original_question: str
    suggestions: List[str] = field(default_factory=list)


class QueryIntentDetector:
    """
    Detects query intent and extracts database references from natural language.
    """

    # Patterns for detecting database references in natural language
    DB_PATTERNS = [
        r"\b(this|that|main|primary|default)\s*(?:db|database|instance)?\b",
        r"\b(postgres|postgresql|pg|psql)\s*(?:db|database)?\b",
        r"\b(mysql|my\s*sql)\s*(?:db|database)?\b",
        r"\b(prod(?:uction)?|dev(?:elopment)?|staging|test)\s*(?:db|database)?\b",
        r"\b(\w+)\s*(?:db|database)\b",
    ]

    # Patterns for compound query detection
    COMPOUND_PATTERNS = [
        r"\band\s+then\b",
        r"\bafter\s+that\b",
        r"\bfirst\s+.*\s+then\b",
        r"\balso\b.*\bshow\b",
        r"\band\s+show\b",
        r"\band\s+display\b",
        r"\bthen\s+(?:show|display|list|get|fetch)",
    ]

    # Patterns for complex filter detection
    COMPLEX_FILTER_PATTERNS = [
        r"\bonly\s+if\b",
        r"\bbut\s+only\b",
        r"\bif\s+.*\s+and\s+.*\b",
        r"\bwhere\s+.*\s+and\s+.*\s+and\s+",
        r"\bsimilar\s+to\b",
        r"\blike\b.*\bor\b.*\blike\b",
        r"\b(amazon|ebay|walmart|etsy|shopify)\b.*\b(clothes|shoes|electronics|books)\b",
    ]

    # Patterns for aggregation keywords
    AGGREGATION_KEYWORDS = [
        r"\b(count|sum|average|avg|total|min|max)\b",
        r"\bhow\s+many\b",
        r"\bhow\s+much\b",
        r"\btotal\s+of\b",
        r"\ball\s+the\b.*\btogether\b",
    ]

    def __init__(self):
        self.compound_regex = re.compile(
            "|".join(self.COMPOUND_PATTERNS), re.IGNORECASE
        )
        self.complex_filter_regex = re.compile(
            "|".join(self.COMPLEX_FILTER_PATTERNS), re.IGNORECASE
        )
        self.aggregation_regex = re.compile(
            "|".join(self.AGGREGATION_KEYWORDS), re.IGNORECASE
        )

    def detect_intent(
        self, question: str, registered_dbs: Optional[List[str]] = None
    ) -> QueryPlan:
        """
        Detect query intent and create a query plan.

        Args:
            question: The natural language question
            registered_dbs: List of registered database IDs/nicknames

        Returns:
            QueryPlan with detected intent and metadata
        """
        question = question.strip()
        registered_dbs = registered_dbs or []

        db_refs = self._extract_database_refs(question, registered_dbs)
        is_compound = bool(self.compound_regex.search(question))
        has_complex_filter = bool(self.complex_filter_regex.search(question))
        is_aggregation = bool(self.aggregation_regex.search(question))

        # Determine if it's a multi-step query
        is_multi_step = is_compound or len(db_refs) > 1

        if is_multi_step:
            intent = QueryIntent.MULTI_STEP
        else:
            intent = self._determine_intent(
                question=question,
                db_refs=db_refs,
                is_compound=is_compound,
                has_complex_filter=has_complex_filter,
                is_aggregation=is_aggregation,
            )

        steps = []
        # Only decompose for analysis, but don't execute multi-step
        if is_compound:
            raw_steps = self._decompose_compound_query(question)
            for raw_step in raw_steps:
                steps.append(
                    QueryStep(
                        step=raw_step["step"],
                        question=raw_step["question"],
                        action=raw_step["action"],
                        status="pending",
                    )
                )
        else:
            steps = [
                QueryStep(
                    step=1,
                    question=question,
                    action="read",
                    status="pending",
                )
            ]

        # Generate suggestions for breaking up the query
        suggestions = []
        if is_multi_step and is_compound:
            suggestions = self._generate_query_suggestions(question, steps)

        return QueryPlan(
            intent=intent,
            database_refs=db_refs,
            steps=steps,
            needs_decomposition=is_multi_step,
            original_question=question,
            suggestions=suggestions,
        )

    def _extract_database_refs(
        self, question: str, registered_dbs: List[str]
    ) -> List[str]:
        """
        Extract database references from natural language.

        Args:
            question: The natural language question
            registered_dbs: List of registered database IDs

        Returns:
            List of detected database references
        """
        refs = []
        question_lower = question.lower()

        # Check against registered database nicknames
        for db in registered_dbs:
            db_lower = db.lower()
            if db_lower in question_lower:
                refs.append(db)

        # Check for generic database references
        for pattern in self.DB_PATTERNS:
            matches = re.finditer(pattern, question, re.IGNORECASE)
            for match in matches:
                matched_text = match.group(0).strip()
                # Exclude if it's just a common word
                if matched_text.lower() not in ["this", "that", "and", "also"]:
                    refs.append(matched_text)

        # Deduplicate while preserving order
        seen = set()
        unique_refs = []
        for ref in refs:
            if ref.lower() not in seen:
                seen.add(ref.lower())
                unique_refs.append(ref)

        return unique_refs

    def _determine_intent(
        self,
        question: str,
        db_refs: List[str],
        is_compound: bool,
        has_complex_filter: bool,
        is_aggregation: bool,
    ) -> QueryIntent:
        """Determine the primary query intent."""

        question_upper = question.upper()
        is_write = any(
            kw in question_upper
            for kw in [
                "UPDATE",
                "INCREASE",
                "DECREASE",
                "DELETE",
                "INSERT",
                "ADD",
                "SET",
                "CHANGE",
            ]
        )

        # Multi-database
        if len(db_refs) > 1:
            if is_write:
                return QueryIntent.MULTI_DB_WRITE
            return QueryIntent.MULTI_DB_READ

        # Compound read-write
        if is_compound:
            return QueryIntent.COMPOUND_READ_WRITE

        # Complex filter
        if has_complex_filter:
            return QueryIntent.COMPLEX_FILTER

        # Aggregation
        if is_aggregation:
            return QueryIntent.AGGREGATION

        # Single database
        if is_write:
            return QueryIntent.SINGLE_DB_WRITE
        return QueryIntent.SINGLE_DB_READ

    def _decompose_compound_query(self, question: str) -> List[Dict[str, Any]]:
        """
        Decompose a compound query into sequential steps.

        Args:
            question: The compound natural language question

        Returns:
            List of steps with action and question parts
        """
        steps = []

        # Split on common compound separators (including "finally")
        parts = re.split(
            r"\b(?:and\s+then|after\s+that|then|finally|also|,)\s+(?:show|display|list|get|fetch)?",
            question,
            flags=re.IGNORECASE,
        )

        # Clean up parts
        parts = [p.strip() for p in parts if p.strip()]

        if len(parts) <= 1:
            # Try splitting on "and" more carefully
            parts = re.split(r"\s+and\s+", question, maxsplit=1)
            parts = [p.strip() for p in parts if p.strip()]

        if len(parts) <= 1:
            # Try splitting on comma
            parts = re.split(r",", question, maxsplit=2)
            parts = [p.strip() for p in parts if p.strip()]

        for i, part in enumerate(parts, 1):
            steps.append(
                {"step": i, "action": self._detect_step_action(part), "question": part}
            )

        return (
            steps if steps else [{"step": 1, "action": "execute", "question": question}]
        )

    def _detect_step_action(self, part: str) -> str:
        """Detect the action type for a query part."""
        part_upper = part.upper()
        if any(
            kw in part_upper
            for kw in ["UPDATE", "INCREASE", "DECREASE", "DELETE", "INSERT"]
        ):
            return "write"
        return "read"

    def _generate_query_suggestions(
        self, question: str, steps: List[QueryStep]
    ) -> List[str]:
        """Generate suggestions for breaking up a compound query."""
        suggestions = []

        if len(steps) > 1:
            suggestions.append(
                f"Detected {len(steps)} separate parts in your query. "
                "For best results, run them separately:"
            )
            for i, step in enumerate(steps, 1):
                clean_question = step.question.strip() if step.question else ""
                if clean_question:
                    suggestions.append(f'  {i}. "{clean_question}"')

        suggestions.append(
            "Tip: You can run each query one at a time and use the results as reference for the next."
        )

        return suggestions


# Global instance
_intent_detector: Optional[QueryIntentDetector] = None


def get_intent_detector() -> QueryIntentDetector:
    """Get the global intent detector instance."""
    global _intent_detector
    if _intent_detector is None:
        _intent_detector = QueryIntentDetector()
    return _intent_detector
