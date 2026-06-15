"""ML Readiness scoring engine — deterministic, no LLM.

Starts at 100 and deducts points based on data quality issues.
Returns a score, grade, strengths, problems, and recommendations.
"""
from __future__ import annotations
import logging
from typing import Any

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

# ── Deduction thresholds ──────────────────────────────────────────────────────
_MISSING_COL_THRESHOLD = 30       # % missing per column to trigger deduction
_MISSING_COL_DEDUCTION = 10       # points per offending column
_MISSING_COL_MAX_DEDUCTION = 30   # cap

_DUPLICATE_THRESHOLD = 5          # % duplicate rows
_DUPLICATE_DEDUCTION = 10

_HIGH_CARD_THRESHOLD = 50         # unique values in a categorical column
_HIGH_CARD_DEDUCTION = 5
_HIGH_CARD_MAX_DEDUCTION = 15

_OUTLIER_THRESHOLD = 10           # % outliers in a numeric column
_OUTLIER_DEDUCTION = 5
_OUTLIER_MAX_DEDUCTION = 15

_TINY_DATASET = 100               # fewer rows → deduction
_TINY_DEDUCTION = 15
_VERY_TINY_DATASET = 50
_VERY_TINY_DEDUCTION = 25

_SINGLE_COL_DEDUCTION = 20

_IQR_FACTOR = 1.5

# ── Grade bands ───────────────────────────────────────────────────────────────
_GRADE_MAP = [
    (90, "A"),
    (75, "B"),
    (60, "C"),
    (40, "D"),
    (0, "F"),
]


def score_ml_readiness(df: pd.DataFrame) -> dict[str, Any]:
    """Compute an ML readiness score for the given DataFrame.

    Returns:
        {
            "score": int (0–100),
            "grade": str (A/B/C/D/F),
            "strengths": list[str],
            "problems": list[str],
            "recommendations": list[str],
        }
    """
    score = 100
    strengths: list[str] = []
    problems: list[str] = []
    recommendations: list[str] = []

    rows, cols = df.shape

    # ── Check 1: Missing values ───────────────────────────────────────────
    missing_deduction = 0
    bad_missing_cols = []
    for col in df.columns:
        null_pct = df[col].isnull().sum() / rows * 100 if rows > 0 else 0
        if null_pct >= _MISSING_COL_THRESHOLD:
            bad_missing_cols.append((col, round(null_pct, 1)))
            missing_deduction += _MISSING_COL_DEDUCTION

    missing_deduction = min(missing_deduction, _MISSING_COL_MAX_DEDUCTION)
    if bad_missing_cols:
        score -= missing_deduction
        for col, pct in bad_missing_cols:
            problems.append(f"Column '{col}' has {pct}% missing values")
        recommendations.append("Impute or drop columns with >30% missing values")
    else:
        strengths.append("No columns with excessive missing values (>30%)")

    # ── Check 2: Duplicate rows ───────────────────────────────────────────
    try:
        dup_pct = df.duplicated().sum() / rows * 100 if rows > 0 else 0
    except Exception:
        dup_pct = 0

    if dup_pct > _DUPLICATE_THRESHOLD:
        score -= _DUPLICATE_DEDUCTION
        problems.append(f"{round(dup_pct, 1)}% duplicate rows detected")
        recommendations.append("Remove duplicate rows before training")
    else:
        strengths.append("Low duplicate row percentage")

    # ── Check 3: High cardinality ─────────────────────────────────────────
    card_deduction = 0
    cat_cols = df.select_dtypes(include=["object", "category"]).columns
    high_card_cols = []
    for col in cat_cols:
        try:
            nunique = df[col].nunique()
        except Exception:
            continue
        if nunique > _HIGH_CARD_THRESHOLD:
            high_card_cols.append((col, nunique))
            card_deduction += _HIGH_CARD_DEDUCTION

    card_deduction = min(card_deduction, _HIGH_CARD_MAX_DEDUCTION)
    if high_card_cols:
        score -= card_deduction
        for col, n in high_card_cols:
            problems.append(f"Column '{col}' has high cardinality ({n} unique values)")
        recommendations.append("Encode or bin high-cardinality categorical columns")
    else:
        if len(cat_cols) > 0:
            strengths.append("Categorical columns have manageable cardinality")

    # ── Check 4: Outliers ─────────────────────────────────────────────────
    outlier_deduction = 0
    numeric_cols = df.select_dtypes(include=["number"]).columns
    outlier_cols = []
    for col in numeric_cols:
        series = df[col].dropna()
        if len(series) < 4:
            continue
        q1 = float(series.quantile(0.25))
        q3 = float(series.quantile(0.75))
        iqr = q3 - q1
        if iqr == 0:
            continue
        lower = q1 - _IQR_FACTOR * iqr
        upper = q3 + _IQR_FACTOR * iqr
        outlier_pct = ((series < lower) | (series > upper)).sum() / len(series) * 100
        if outlier_pct > _OUTLIER_THRESHOLD:
            outlier_cols.append((col, round(outlier_pct, 1)))
            outlier_deduction += _OUTLIER_DEDUCTION

    outlier_deduction = min(outlier_deduction, _OUTLIER_MAX_DEDUCTION)
    if outlier_cols:
        score -= outlier_deduction
        for col, pct in outlier_cols:
            problems.append(f"Column '{col}' has {pct}% outliers")
        recommendations.append("Clip or remove outliers in flagged columns")
    else:
        if len(numeric_cols) > 0:
            strengths.append("No numeric columns with excessive outliers (>10%)")

    # ── Check 5: Dataset size ─────────────────────────────────────────────
    if rows < _VERY_TINY_DATASET:
        score -= _VERY_TINY_DEDUCTION
        problems.append(f"Very small dataset ({rows} rows)")
        recommendations.append("Collect more data — fewer than 50 rows is usually insufficient for ML")
    elif rows < _TINY_DATASET:
        score -= _TINY_DEDUCTION
        problems.append(f"Small dataset ({rows} rows)")
        recommendations.append("Consider collecting more data — fewer than 100 rows may limit model performance")
    else:
        strengths.append(f"Adequate dataset size ({rows} rows)")

    # ── Check 6: Single column ────────────────────────────────────────────
    if cols <= 1:
        score -= _SINGLE_COL_DEDUCTION
        problems.append("Dataset has only 1 column — no features to learn from")
        recommendations.append("Add feature columns to enable meaningful ML training")
    else:
        strengths.append(f"Multiple features available ({cols} columns)")

    # Clamp score
    score = max(0, min(100, score))

    # Determine grade
    grade = "F"
    for threshold, letter in _GRADE_MAP:
        if score >= threshold:
            grade = letter
            break

    return {
        "score": score,
        "grade": grade,
        "strengths": strengths,
        "problems": problems,
        "recommendations": recommendations,
    }
