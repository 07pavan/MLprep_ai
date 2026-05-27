"""Semantic schema compression — select the most relevant columns for LLM prompts.

Strategy (in priority order):
  1. EXACT MATCH  — columns whose name appears verbatim in the question (always included)
  2. FUZZY MATCH  — columns whose name words overlap with question keywords (scored)
  3. DTYPE BOOST  — numeric/datetime columns get a bonus for analytical questions
  4. FILL SLOTS   — if fewer than max_cols selected, pad with first columns in order
"""
from __future__ import annotations
import re
import logging
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

# Common English stop words to ignore when matching
_STOP_WORDS = frozenset({
    "a", "an", "the", "is", "are", "was", "were", "be", "been",
    "do", "does", "did", "will", "would", "could", "should", "shall",
    "have", "has", "had", "having",
    "in", "on", "at", "to", "for", "of", "with", "by", "from",
    "and", "or", "but", "not", "no", "nor",
    "it", "its", "this", "that", "these", "those",
    "i", "me", "my", "we", "our", "you", "your", "he", "she", "they",
    "what", "which", "who", "whom", "when", "where", "how", "why",
    "show", "give", "get", "find", "tell", "make", "can",
    "all", "each", "every", "any", "some", "many", "much", "more",
    "most", "other", "than",
    "very", "just", "also", "about", "between", "through", "during",
    "data", "dataset", "table", "column", "row", "value", "values",
    "please", "using", "use", "based",
})

# Words that indicate the user wants quantitative analysis
_QUANT_KEYWORDS = frozenset({
    "average", "avg", "mean", "sum", "total", "count", "max", "min",
    "median", "std", "variance", "correlation", "percent", "percentage",
    "ratio", "rate", "growth", "decline", "increase", "decrease",
    "top", "bottom", "highest", "lowest", "most", "least", "best", "worst",
})

# Words that indicate temporal analysis
_TEMPORAL_KEYWORDS = frozenset({
    "trend", "time", "date", "month", "year", "week", "day", "quarter",
    "daily", "monthly", "yearly", "weekly", "over time", "timeline",
    "forecast", "seasonal", "period",
})


def _tokenize(text: str) -> set[str]:
    """Split text into lowercase word tokens, stripping stop words."""
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {w for w in words if w not in _STOP_WORDS and len(w) > 1}


def _col_tokens(col_name: str) -> set[str]:
    """Tokenize a column name — split on underscores, camelCase, spaces."""
    # Insert space before uppercase letters (camelCase → camel Case)
    spaced = re.sub(r"([a-z])([A-Z])", r"\1 \2", col_name)
    # Replace underscores/hyphens with spaces
    spaced = spaced.replace("_", " ").replace("-", " ")
    return _tokenize(spaced)


def select_relevant_columns(
    df: pd.DataFrame,
    question: str,
    max_cols: int = 15,
) -> list[str]:
    """Pick the most relevant columns for the LLM prompt.

    Returns column names in their original DataFrame order.
    If the dataset has <= max_cols columns, returns ALL columns.
    """
    all_cols = list(df.columns)

    # No compression needed for small schemas
    if len(all_cols) <= max_cols:
        return all_cols

    q_tokens = _tokenize(question)
    q_lower = question.lower()
    wants_quant = bool(q_tokens & _QUANT_KEYWORDS)
    wants_temporal = bool(q_tokens & _TEMPORAL_KEYWORDS)

    # Score each column
    scores: dict[str, float] = {}

    for col in all_cols:
        score = 0.0
        col_lower = col.lower()
        c_tokens = _col_tokens(col)

        # Priority 1: Exact name match in question (highest weight)
        if col_lower in q_lower or col.replace("_", " ").lower() in q_lower:
            score += 100.0

        # Priority 2: Token overlap
        overlap = q_tokens & c_tokens
        if overlap:
            score += len(overlap) * 10.0

        # Priority 3: Partial substring match
        for qt in q_tokens:
            if qt in col_lower:
                score += 5.0

        # Priority 4: Dtype boost
        dtype = str(df[col].dtype)
        if wants_quant and dtype in ("int64", "float64", "int32", "float32"):
            score += 3.0
        if wants_temporal and ("datetime" in dtype or "date" in col_lower or "time" in col_lower):
            score += 3.0

        scores[col] = score

    # Select columns: all with score > 0 first, then fill remaining slots
    scored_cols = sorted(
        [c for c in all_cols if scores[c] > 0],
        key=lambda c: scores[c],
        reverse=True,
    )

    selected = set(scored_cols[:max_cols])

    # Ensure at least 1 numeric and 1 datetime column exist if available
    numeric_cols = [c for c in all_cols if str(df[c].dtype) in ("int64", "float64", "int32", "float32")]
    datetime_cols = [c for c in all_cols if "datetime" in str(df[c].dtype)]

    if numeric_cols and not any(c in selected for c in numeric_cols):
        selected.add(numeric_cols[0])
    if datetime_cols and not any(c in selected for c in datetime_cols):
        selected.add(datetime_cols[0])

    # Fill remaining slots with columns in original order
    if len(selected) < max_cols:
        for col in all_cols:
            if col not in selected:
                selected.add(col)
                if len(selected) >= max_cols:
                    break

    # Return in original DataFrame column order
    result = [c for c in all_cols if c in selected]

    logger.info(
        "Schema compression: %d/%d columns selected (question: %s)",
        len(result), len(all_cols), question[:60],
    )

    return result
