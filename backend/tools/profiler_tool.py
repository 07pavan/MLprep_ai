"""Dataset profiling tool — pure Pandas/NumPy analysis, no LLM.

Generates comprehensive dataset metadata including shape, types,
missing values, duplicates, and descriptive statistics.
"""
from __future__ import annotations
import logging
from typing import Any

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

# Sampling threshold for expensive operations like nunique
_MAX_ROWS_FOR_EXPENSIVE = 100_000


def profile_dataset(df: pd.DataFrame) -> dict[str, Any]:
    """Run a full profile on the DataFrame and return a JSON-serializable dict.

    Returns:
        {
            "rows": int,
            "columns": int,
            "memory_mb": float,
            "column_names": list[str],
            "dtypes": dict[str, str],
            "numerical_count": int,
            "categorical_count": int,
            "missing_values": list[{column, null_count, null_percentage}],
            "duplicate_rows": {"count": int, "percentage": float},
            "numerical_stats": list[{column, mean, median, std, min, max, skewness, kurtosis, q1, q3}],
        }
    """
    rows, cols = df.shape
    memory_mb = round(df.memory_usage(deep=True).sum() / (1024 * 1024), 2)

    # Column names and dtypes
    column_names = df.columns.tolist()
    dtypes = {col: str(df[col].dtype) for col in column_names}

    # Numerical vs categorical counts
    numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
    categorical_cols = df.select_dtypes(include=["object", "category", "bool"]).columns.tolist()

    # Missing values per column
    missing_values = []
    for col in column_names:
        null_count = int(df[col].isnull().sum())
        null_pct = round(null_count / rows * 100, 2) if rows > 0 else 0.0
        missing_values.append({
            "column": col,
            "null_count": null_count,
            "null_percentage": null_pct,
        })

    # Duplicate rows
    try:
        dup_count = int(df.duplicated().sum())
    except Exception:
        dup_count = 0
    dup_pct = round(dup_count / rows * 100, 2) if rows > 0 else 0.0

    # Descriptive statistics for numerical columns
    numerical_stats = []
    for col in numeric_cols:
        series = df[col].dropna()
        if series.empty:
            continue
        try:
            stats = {
                "column": col,
                "mean": round(float(series.mean()), 4),
                "median": round(float(series.median()), 4),
                "std": round(float(series.std()), 4),
                "min": round(float(series.min()), 4),
                "max": round(float(series.max()), 4),
                "skewness": round(float(series.skew()), 4),
                "kurtosis": round(float(series.kurtosis()), 4),
                "q1": round(float(series.quantile(0.25)), 4),
                "q3": round(float(series.quantile(0.75)), 4),
            }
            numerical_stats.append(stats)
        except Exception as exc:
            logger.warning("Profiler: skipping stats for column '%s': %s", col, exc)

    return {
        "rows": rows,
        "columns": cols,
        "memory_mb": memory_mb,
        "column_names": column_names,
        "dtypes": dtypes,
        "numerical_count": len(numeric_cols),
        "categorical_count": len(categorical_cols),
        "missing_values": missing_values,
        "duplicate_rows": {
            "count": dup_count,
            "percentage": dup_pct,
        },
        "numerical_stats": numerical_stats,
    }
