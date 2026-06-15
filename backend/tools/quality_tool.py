"""Data quality inspection tool — pure Pandas/NumPy analysis, no LLM.

Detects missing values, duplicates, high cardinality, outliers,
data type mismatches, constant (zero-variance) columns, and
invalid email addresses. Returns a structured list of issues.
"""
from __future__ import annotations
import logging
from typing import Any

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

# ── Thresholds ────────────────────────────────────────────────────────────────
_MISSING_CRITICAL = 50   # % above which missing data is critical
_MISSING_HIGH = 20
_MISSING_MEDIUM = 5

_HIGH_CARDINALITY_ABS = 100       # absolute unique count threshold
_HIGH_CARDINALITY_PCT = 50        # % of rows threshold

_OUTLIER_IQR_FACTOR = 1.5

_TYPE_MISMATCH_THRESHOLD = 0.80   # 80% parseable → likely wrong dtype

_MAX_ROWS_FOR_OUTLIER = 200_000   # sample for IQR calculation

# Email regex — RFC-5321 simplified (catches obvious malformed addresses)
_EMAIL_COLUMN_KEYWORDS = ("email", "e_mail", "mail", "correo")  # heuristic column name match
_EMAIL_VALID_RE = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"                # minimal valid pattern
_EMAIL_INVALID_THRESHOLD = 0.05   # flag if >5% of non-null values are malformed
_EMAIL_COLUMN_SAMPLE_PCT = 0.20   # only check columns where ≥20% look like emails

# Constant column: flag if nunique ≤ this many values (after dropping nulls)
_CONSTANT_MAX_UNIQUE = 1


def check_quality(df: pd.DataFrame) -> dict[str, Any]:
    """Run all quality checks and return a structured report.

    Returns:
        {
            "total_issues": int,
            "issues": [
                {
                    "type": str,
                    "column": str | None,
                    "severity": "critical" | "high" | "medium" | "low",
                    "details": str,
                    "recommendation": str,
                }
            ]
        }
    """
    issues: list[dict] = []

    issues.extend(_check_missing(df))
    issues.extend(_check_duplicates(df))
    issues.extend(_check_high_cardinality(df))
    issues.extend(_check_outliers(df))
    issues.extend(_check_type_mismatches(df))
    issues.extend(_check_constant_columns(df))
    issues.extend(_check_invalid_emails(df))

    # Sort: critical first, then high, medium, low
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    issues.sort(key=lambda x: severity_order.get(x["severity"], 99))

    return {
        "total_issues": len(issues),
        "issues": issues,
    }


# ── Individual checks ─────────────────────────────────────────────────────────

def _check_missing(df: pd.DataFrame) -> list[dict]:
    """Detect columns with missing values and suggest imputation."""
    rows = len(df)
    if rows == 0:
        return []

    results = []
    for col in df.columns:
        null_count = int(df[col].isnull().sum())
        if null_count == 0:
            continue

        pct = round(null_count / rows * 100, 2)

        if pct >= _MISSING_CRITICAL:
            severity = "critical"
        elif pct >= _MISSING_HIGH:
            severity = "high"
        elif pct >= _MISSING_MEDIUM:
            severity = "medium"
        else:
            severity = "low"

        # Suggest imputation strategy
        if pct >= _MISSING_CRITICAL:
            recommendation = f"Consider dropping column '{col}' ({pct}% missing)"
        elif pd.api.types.is_numeric_dtype(df[col]):
            recommendation = f"Use median imputation for '{col}' ({pct}% missing)"
        else:
            recommendation = f"Use mode imputation for '{col}' ({pct}% missing)"

        results.append({
            "type": "missing_values",
            "column": col,
            "severity": severity,
            "details": f"{null_count} missing values ({pct}%)",
            "recommendation": recommendation,
        })

    return results


def _check_duplicates(df: pd.DataFrame) -> list[dict]:
    """Count duplicate rows."""
    rows = len(df)
    if rows == 0:
        return []

    try:
        dup_count = int(df.duplicated().sum())
    except Exception:
        return []

    if dup_count == 0:
        return []

    pct = round(dup_count / rows * 100, 2)

    if pct > 10:
        severity = "high"
    elif pct > 1:
        severity = "medium"
    else:
        severity = "low"

    return [{
        "type": "duplicate_rows",
        "column": None,
        "severity": severity,
        "details": f"{dup_count} duplicate rows ({pct}%)",
        "recommendation": "Drop duplicate rows with df.drop_duplicates()",
    }]


def _check_high_cardinality(df: pd.DataFrame) -> list[dict]:
    """Detect categorical columns with too many unique values."""
    rows = len(df)
    if rows == 0:
        return []

    cat_cols = df.select_dtypes(include=["object", "category"]).columns
    results = []

    for col in cat_cols:
        try:
            nunique = int(df[col].nunique())
        except Exception:
            continue

        pct_unique = round(nunique / rows * 100, 2) if rows > 0 else 0

        if nunique > _HIGH_CARDINALITY_ABS or pct_unique > _HIGH_CARDINALITY_PCT:
            results.append({
                "type": "high_cardinality",
                "column": col,
                "severity": "medium",
                "details": f"{nunique} unique values ({pct_unique}% of rows)",
                "recommendation": f"Consider encoding, binning, or dropping '{col}'",
            })

    return results


def _check_outliers(df: pd.DataFrame) -> list[dict]:
    """Use IQR method to detect outliers in numeric columns."""
    rows = len(df)
    if rows == 0:
        return []

    numeric_cols = df.select_dtypes(include=["number"]).columns
    sample = df if rows <= _MAX_ROWS_FOR_OUTLIER else df.sample(_MAX_ROWS_FOR_OUTLIER, random_state=0)
    results = []

    for col in numeric_cols:
        series = sample[col].dropna()
        if len(series) < 4:
            continue

        q1 = float(series.quantile(0.25))
        q3 = float(series.quantile(0.75))
        iqr = q3 - q1

        if iqr == 0:
            continue

        lower = q1 - _OUTLIER_IQR_FACTOR * iqr
        upper = q3 + _OUTLIER_IQR_FACTOR * iqr
        outlier_count = int(((series < lower) | (series > upper)).sum())

        if outlier_count == 0:
            continue

        pct = round(outlier_count / len(series) * 100, 2)

        if pct > 10:
            severity = "high"
        elif pct > 5:
            severity = "medium"
        else:
            severity = "low"

        results.append({
            "type": "outliers",
            "column": col,
            "severity": severity,
            "details": f"{outlier_count} outliers ({pct}%) outside IQR [{round(lower, 2)}, {round(upper, 2)}]",
            "recommendation": f"Investigate or clip outliers in '{col}'",
        })

    return results


def _check_type_mismatches(df: pd.DataFrame) -> list[dict]:
    """Detect object columns that are mostly numeric or datetime."""
    rows = len(df)
    if rows == 0:
        return []

    object_cols = df.select_dtypes(include=["object"]).columns
    results = []

    for col in object_cols:
        non_null = df[col].dropna()
        if len(non_null) == 0:
            continue

        # Check if mostly numeric
        numeric_parsed = pd.to_numeric(non_null, errors="coerce")
        numeric_pct = numeric_parsed.notna().sum() / len(non_null)

        if numeric_pct >= _TYPE_MISMATCH_THRESHOLD:
            results.append({
                "type": "type_mismatch",
                "column": col,
                "severity": "medium",
                "details": f"Column is object dtype but {round(numeric_pct * 100, 1)}% values are numeric",
                "recommendation": f"Cast '{col}' to numeric with pd.to_numeric()",
            })
            continue

        # Check if mostly datetime
        try:
            # Quick check: datetimes must contain digits and separators. Skip slow parsing if they don't.
            sample_str = non_null.head(100).astype(str)
            has_date_format = (sample_str.str.contains(r"\d") & sample_str.str.contains(r"[-/:]")).mean()
            if has_date_format >= 0.5:
                datetime_parsed = pd.to_datetime(non_null, errors="coerce")
                datetime_pct = datetime_parsed.notna().sum() / len(non_null)
                if datetime_pct >= _TYPE_MISMATCH_THRESHOLD:
                    results.append({
                        "type": "type_mismatch",
                        "column": col,
                        "severity": "medium",
                        "details": f"Column is object dtype but {round(datetime_pct * 100, 1)}% values are datetime",
                        "recommendation": f"Cast '{col}' to datetime with pd.to_datetime()",
                    })
        except Exception:
            pass

    return results


# ── Constant column check ─────────────────────────────────────────────────────

def _check_constant_columns(df: pd.DataFrame) -> list[dict]:
    """Detect columns with only one distinct non-null value (zero variance).

    Such columns carry no predictive signal and should be dropped before
    training. They also cause issues for normalisation/scaling steps.

    Severity:
        high   → all rows have the same value (including columns that are all-null)
        medium → column has some nulls but the non-null portion is constant
    """
    rows = len(df)
    if rows == 0:
        return []

    results = []
    for col in df.columns:
        non_null = df[col].dropna()
        if len(non_null) == 0:
            continue   # all-null columns are caught by _check_missing

        try:
            nunique = int(non_null.nunique())
        except Exception:
            continue

        if nunique > _CONSTANT_MAX_UNIQUE:
            continue

        has_nulls = df[col].isnull().any()
        severity = "medium" if has_nulls else "high"
        unique_val = non_null.iloc[0] if len(non_null) > 0 else "N/A"

        results.append({
            "type": "constant_column",
            "column": col,
            "severity": severity,
            "details": (
                f"Column '{col}' has only 1 unique value: '{unique_val}'. "
                f"Zero variance — provides no predictive signal."
            ),
            "recommendation": (
                f"Drop constant column '{col}' before training. "
                "Constant features cannot help any ML model learn."
            ),
        })

    return results


# ── Invalid email check ───────────────────────────────────────────────────────

def _check_invalid_emails(df: pd.DataFrame) -> list[dict]:
    """Detect object columns that appear to be email fields with malformed values.

    Detection strategy:
        1. Identify candidate columns by name keyword (email, mail) OR by
           checking that ≥20% of non-null values contain an '@' symbol.
        2. For candidate columns, count values that do NOT match the minimal
           RFC-5321 pattern ``user@domain.tld``.
        3. Report if >5% of non-null values are malformed.

    Severity:
        high   → >25% malformed
        medium → 5–25% malformed
    """
    rows = len(df)
    if rows == 0:
        return []

    object_cols = df.select_dtypes(include=["object"]).columns
    results = []

    for col in object_cols:
        non_null = df[col].dropna().astype(str)
        if len(non_null) == 0:
            continue

        # ── Is this an email column? ──────────────────────────────────────────
        col_lower = col.lower()
        name_match = any(kw in col_lower for kw in _EMAIL_COLUMN_KEYWORDS)
        # Structural check: what fraction contain '@'?
        at_pct = non_null.str.contains("@", regex=False).mean()
        is_email_col = name_match or (at_pct >= _EMAIL_COLUMN_SAMPLE_PCT)

        if not is_email_col:
            continue

        # ── Count malformed addresses ─────────────────────────────────────────
        valid_mask = non_null.str.match(_EMAIL_VALID_RE, na=False)
        invalid_count = int((~valid_mask).sum())
        invalid_pct = round(invalid_count / len(non_null) * 100, 2)

        if invalid_pct <= _EMAIL_INVALID_THRESHOLD * 100:
            continue

        severity = "high" if invalid_pct > 25.0 else "medium"

        results.append({
            "type": "invalid_emails",
            "column": col,
            "severity": severity,
            "details": (
                f"{invalid_count} invalid email addresses ({invalid_pct}% of non-null values) "
                f"in column '{col}'."
            ),
            "recommendation": (
                f"Validate and clean email column '{col}'. "
                "Malformed emails cause silent failures in downstream pipelines "
                "and should be flagged or imputed before training."
            ),
        })

    return results
