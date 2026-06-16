"""Rule Engine — deterministic, stateless mapper from quality findings to CleaningActions.

Phase 2A contract: this module is READ-ONLY.
It produces CleaningAction objects from structured dicts — NO pandas DataFrame needed.

Input contract:
    profile:        dict returned by profile_dataset()
    quality_issues: list from check_quality()["issues"]

Design decisions:
    - Dtype context is read from profile["dtypes"] (column → dtype string).
    - Outlier co-occurrence is derived from the issues list itself.
    - Confidence scores are calibrated by measurable heuristics:
        * missing %  → higher % → higher confidence in drop recommendation
        * outlier %  → above/below 10% pivot → clip vs remove decision
        * cardinality % → above/below 80% pivot → drop vs encode decision
    - auto_applicable=False for all destructive or domain-sensitive actions.
    - Unknown issue types are silently skipped (future-proof).
"""
from __future__ import annotations

import logging
import re
from typing import Any

from schemas.cleaning_plan import (
    ActionType,
    CleaningAction,
    IssueType,
    Severity,
)

logger = logging.getLogger(__name__)

# ── Confidence calibration ─────────────────────────────────────────────────────
_CONF_HIGH   = 0.92   # strong signal, well-established heuristic
_CONF_MEDIUM = 0.75   # good signal, some context-dependence
_CONF_LOW    = 0.55   # weak signal, domain expertise advisable

# ── Decision thresholds ────────────────────────────────────────────────────────
_DROP_COLUMN_MISSING_PCT  = 50.0   # % missing above which drop_column beats imputation
_CLIP_OUTLIER_PCT         = 10.0   # % outliers above which clip beats remove
_ID_CARDINALITY_PCT       = 80.0   # % unique above which column behaves like an ID
_HIGH_CARDINALITY_PCT     = 30.0   # % unique above which frequency_encoding beats target

# dtype strings that indicate a numeric column
_NUMERIC_DTYPE_PREFIXES = ("int", "float", "uint", "complex")


# ── Public API ────────────────────────────────────────────────────────────────

def apply_rules(
    profile: dict[str, Any],
    quality_issues: list[dict[str, Any]],
) -> list[CleaningAction]:
    """Map quality issues to ordered CleaningAction recommendations.

    Args:
        profile:       Output from ``profile_dataset()`` — provides dtype info,
                       numerical stats, and column metadata.
        quality_issues: Output from ``check_quality(df)["issues"]`` — structured
                       list of detected data issues.

    Returns:
        List of CleaningAction objects sorted by severity (critical → low).
        Unknown issue types are silently skipped.
    """
    # Pre-index profile data for O(1) lookup inside each rule
    dtypes: dict[str, str] = profile.get("dtypes", {})
    numerical_stats: dict[str, dict] = {
        s["column"]: s for s in profile.get("numerical_stats", [])
    }

    # Identify which columns also carry outlier issues
    # (affects imputation strategy for co-occurring missing values)
    outlier_columns: set[str] = {
        issue["column"]
        for issue in quality_issues
        if issue.get("type") == "outliers" and issue.get("column")
    }

    actions: list[CleaningAction] = []

    for issue in quality_issues:
        try:
            action = _dispatch(
                issue=issue,
                dtypes=dtypes,
                numerical_stats=numerical_stats,
                outlier_columns=outlier_columns,
            )
            if action is not None:
                actions.append(action)
        except Exception as exc:
            logger.warning(
                "Rule engine: skipped issue type='%s' col='%s' — %s",
                issue.get("type"), issue.get("column"), exc,
            )

    # Sort: critical → high → medium → low
    _rank = {Severity.critical: 0, Severity.high: 1, Severity.medium: 2, Severity.low: 3}
    actions.sort(key=lambda a: _rank.get(a.severity, 99))
    return actions


# ── Dispatcher ────────────────────────────────────────────────────────────────

def _dispatch(
    issue: dict[str, Any],
    dtypes: dict[str, str],
    numerical_stats: dict[str, dict],
    outlier_columns: set[str],
) -> CleaningAction | None:
    """Route a single quality issue to the correct rule function."""
    itype = issue.get("type", "")

    if itype == "missing_values":
        return _rule_missing_values(issue, dtypes, outlier_columns, numerical_stats)
    if itype == "duplicate_rows":
        return _rule_duplicate_rows(issue)
    if itype == "outliers":
        return _rule_outliers(issue, numerical_stats)
    if itype == "high_cardinality":
        return _rule_high_cardinality(issue)
    if itype == "type_mismatch":
        return _rule_type_mismatch(issue)
    if itype == "constant_column":
        return _rule_constant_column(issue)
    if itype == "invalid_emails":
        return _rule_invalid_emails(issue)

    logger.debug("Rule engine: no rule registered for issue type '%s' — skipping", itype)
    return None


# ── Rule Functions ────────────────────────────────────────────────────────────

def _rule_missing_values(
    issue: dict[str, Any],
    dtypes: dict[str, str],
    outlier_columns: set[str],
    numerical_stats: dict[str, dict],
) -> CleaningAction:
    """Decide: drop_column | median_imputation | mean_imputation | mode_imputation.

    Decision tree:
        1. ≥50% missing → drop_column (auto_applicable=False, high confidence)
        2. numeric + has outliers → median_imputation (robust, high confidence)
        3. numeric + no outliers → mean_imputation (medium confidence)
              Sub-rule: if |skewness| > 1.0 → median still preferred
        4. categorical → mode_imputation (medium confidence)
    """
    col      = issue["column"]
    details  = issue["details"]
    severity = Severity(issue["severity"])
    pct      = _extract_pct(details)

    # ── Branch 1: Mostly empty → drop ─────────────────────────────────────────
    if pct >= _DROP_COLUMN_MISSING_PCT:
        return CleaningAction(
            column_name=col,
            issue_type=IssueType.missing_values,
            severity=severity,
            current_state=details,
            recommendation=ActionType.drop_column,
            reason=(
                f"Column '{col}' is {pct:.1f}% missing. Imputing over half the values "
                "would fabricate the majority of the column's distribution, introducing "
                "severe statistical bias. Dropping is strongly recommended unless this "
                "column is domain-critical."
            ),
            confidence_score=_CONF_HIGH,
            auto_applicable=False,   # destructive — requires explicit user approval
        )

    # ── Branch 2/3/4: Imputation ───────────────────────────────────────────────
    dtype_str  = dtypes.get(col, "object").lower()
    is_numeric = dtype_str.startswith(_NUMERIC_DTYPE_PREFIXES)

    if is_numeric:
        # Check skewness from numerical stats to choose mean vs median
        skewness = abs(numerical_stats.get(col, {}).get("skewness", 0.0) or 0.0)
        use_median = col in outlier_columns or skewness > 1.0

        if use_median:
            reason_parts = []
            if col in outlier_columns:
                reason_parts.append("outliers are present in this column")
            if skewness > 1.0:
                reason_parts.append(f"the distribution is skewed (|skewness|={skewness:.2f})")
            reason_context = " and ".join(reason_parts) if reason_parts else "robust imputation preferred"

            return CleaningAction(
                column_name=col,
                issue_type=IssueType.missing_values,
                severity=severity,
                current_state=details,
                recommendation=ActionType.median_imputation,
                reason=(
                    f"Numerical column '{col}' has {pct:.1f}% missing values. "
                    f"Median imputation is selected because {reason_context}. "
                    "The median is resistant to extreme values and skewed distributions."
                ),
                confidence_score=_CONF_HIGH,
                auto_applicable=True,
            )
        else:
            return CleaningAction(
                column_name=col,
                issue_type=IssueType.missing_values,
                severity=severity,
                current_state=details,
                recommendation=ActionType.mean_imputation,
                reason=(
                    f"Numerical column '{col}' has {pct:.1f}% missing values. "
                    "No outliers detected and distribution appears approximately symmetric "
                    f"(|skewness|={skewness:.2f}). Mean imputation is appropriate."
                ),
                confidence_score=_CONF_MEDIUM,
                auto_applicable=True,
            )
    else:
        return CleaningAction(
            column_name=col,
            issue_type=IssueType.missing_values,
            severity=severity,
            current_state=details,
            recommendation=ActionType.mode_imputation,
            reason=(
                f"Categorical column '{col}' has {pct:.1f}% missing values. "
                "Mode imputation (most frequent value) preserves the existing category "
                "distribution and avoids introducing an artificial new category."
            ),
            confidence_score=_CONF_MEDIUM,
            auto_applicable=True,
        )


def _rule_duplicate_rows(issue: dict[str, Any]) -> CleaningAction:
    """Recommend remove_duplicates — always auto-applicable, always high confidence."""
    details  = issue["details"]
    severity = Severity(issue["severity"])
    pct      = _extract_pct(details)

    # Calibrate confidence by severity of duplication
    confidence = _CONF_HIGH if pct > 5.0 else _CONF_MEDIUM

    return CleaningAction(
        column_name=None,
        issue_type=IssueType.duplicate_rows,
        severity=severity,
        current_state=details,
        recommendation=ActionType.remove_duplicates,
        reason=(
            f"Dataset contains {details}. Duplicate rows artificially inflate the "
            "effective sample size, cause data leakage between train/test splits, "
            "and bias model evaluation metrics. Removing duplicates is a standard "
            "pre-processing step with no information loss."
        ),
        confidence_score=confidence,
        auto_applicable=True,
    )


def _rule_outliers(
    issue: dict[str, Any],
    numerical_stats: dict[str, dict],
) -> CleaningAction:
    """Recommend clip_outliers (high %) or remove_outliers (low %).

    Decision pivot at 10%:
        > 10% outliers → clip to IQR fence (preserves row count)
        ≤ 10% outliers → remove rows (cleaner, minimal data loss)

    Uses skewness from profile to strengthen the recommendation reason.
    """
    col      = issue["column"]
    details  = issue["details"]
    severity = Severity(issue["severity"])
    pct      = _extract_pct(details)

    stats    = numerical_stats.get(col, {})
    skewness = abs(stats.get("skewness", 0.0) or 0.0)
    skew_note = f" Distribution is skewed (|skewness|={skewness:.2f})." if skewness > 1.0 else ""

    if pct > _CLIP_OUTLIER_PCT:
        return CleaningAction(
            column_name=col,
            issue_type=IssueType.outliers,
            severity=severity,
            current_state=details,
            recommendation=ActionType.clip_outliers,
            reason=(
                f"Column '{col}' has {pct:.1f}% outliers detected by IQR method.{skew_note} "
                f"Removing {pct:.1f}% of rows would significantly reduce the training set. "
                "Clipping values to the IQR fence [Q1−1.5×IQR, Q3+1.5×IQR] bounds "
                "the distribution while preserving all rows."
            ),
            confidence_score=_CONF_MEDIUM,
            auto_applicable=True,
        )
    else:
        return CleaningAction(
            column_name=col,
            issue_type=IssueType.outliers,
            severity=severity,
            current_state=details,
            recommendation=ActionType.remove_outliers,
            reason=(
                f"Column '{col}' has {pct:.1f}% outliers detected by IQR method.{skew_note} "
                f"Removing {pct:.1f}% of rows is a safe trade-off at this level — "
                "the data loss is minimal and the resulting distribution will be "
                "significantly cleaner for model training."
            ),
            confidence_score=_CONF_HIGH,
            auto_applicable=True,
        )


def _rule_high_cardinality(issue: dict[str, Any]) -> CleaningAction:
    """Recommend drop_column | frequency_encoding | target_encoding.

    Decision tree:
        > 80% unique → near-identifier → drop_column (auto=False, destructive)
        > 30% unique → frequency_encoding (auto=True, target-independent)
        ≤ 30% unique → target_encoding (auto=False, requires target selection)
    """
    col      = issue["column"]
    details  = issue["details"]
    severity = Severity(issue["severity"])
    pct      = _extract_pct(details)

    if pct > _ID_CARDINALITY_PCT:
        return CleaningAction(
            column_name=col,
            issue_type=IssueType.high_cardinality,
            severity=severity,
            current_state=details,
            recommendation=ActionType.drop_column,
            reason=(
                f"Column '{col}' has {pct:.1f}% unique values — it functions as a "
                "near-unique identifier (e.g. name, ID, UUID). Such columns carry "
                "no learnable pattern and cause severe overfitting. "
                "Dropping is strongly recommended unless you intend to use it as a join key."
            ),
            confidence_score=_CONF_HIGH,
            auto_applicable=False,   # dropping a column is irreversible without versioning
        )
    elif pct > _HIGH_CARDINALITY_PCT:
        return CleaningAction(
            column_name=col,
            issue_type=IssueType.high_cardinality,
            severity=severity,
            current_state=details,
            recommendation=ActionType.frequency_encoding,
            reason=(
                f"Column '{col}' has {pct:.1f}% unique values. Frequency encoding "
                "replaces each category with its occurrence count or proportion. "
                "It is a robust, target-independent strategy that preserves ordinal "
                "cardinality information without introducing target leakage."
            ),
            confidence_score=_CONF_MEDIUM,
            auto_applicable=True,
        )
    else:
        return CleaningAction(
            column_name=col,
            issue_type=IssueType.high_cardinality,
            severity=severity,
            current_state=details,
            recommendation=ActionType.target_encoding,
            reason=(
                f"Column '{col}' has {pct:.1f}% unique values — moderate-to-high "
                "cardinality. Target encoding (replacing categories with mean target "
                "value) is effective at this level, but requires a defined target "
                "column and should use cross-validation folds to prevent leakage."
            ),
            confidence_score=_CONF_LOW,
            auto_applicable=False,   # requires target column specification
        )


def _rule_type_mismatch(issue: dict[str, Any]) -> CleaningAction:
    """Recommend cast_numeric or cast_datetime based on detected target type."""
    col      = issue["column"]
    details  = issue["details"]
    severity = Severity(issue["severity"])

    # Parse target type from the quality tool's details string
    details_lower = details.lower()
    if "datetime" in details_lower:
        action = ActionType.cast_datetime
        target = "datetime"
        benefit = (
            "Enables time-based feature engineering (year, month, day-of-week extraction) "
            "and prevents invalid string comparisons during model training."
        )
    else:
        action = ActionType.cast_numeric
        target = "numeric"
        benefit = (
            "Allows the model to use the true ordinal and continuous relationships "
            "in the data. String comparison of numbers is meaningless for ML."
        )

    # Extract parse success rate for confidence calibration
    numeric_pct = _extract_pct(details)
    confidence = _CONF_HIGH if numeric_pct >= 95.0 else _CONF_MEDIUM

    return CleaningAction(
        column_name=col,
        issue_type=IssueType.type_mismatch,
        severity=severity,
        current_state=details,
        recommendation=action,
        reason=(
            f"Column '{col}' is stored as object/string dtype but "
            f"{numeric_pct:.1f}% of its values are parseable as {target}. "
            f"{benefit}"
        ),
        confidence_score=confidence,
        auto_applicable=True,
    )


# ── Utilities ─────────────────────────────────────────────────────────────────

def _extract_pct(text: str) -> float:
    """Extract the first percentage value from a details string.

    Examples:
        '12 missing values (12.0%)' → 12.0
        '2 outliers (16.7%) outside IQR' → 16.7
        'no numbers here' → 0.0
    """
    match = re.search(r"([\d.]+)%", text)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            pass
    return 0.0


# ── Constant column rule ──────────────────────────────────────────────────────

def _rule_constant_column(issue: dict[str, Any]) -> CleaningAction:
    """Recommend drop_constant for zero-variance (constant) columns.

    A constant column has only one unique value across all rows.
    It carries zero predictive signal and causes errors in:
        - StandardScaler (division by zero)
        - LDA / PCA (singular matrix)
        - Feature importance scoring

    Always auto_applicable=False — user should confirm the column is truly
    useless and not a data ingestion error.
    """
    col      = issue["column"]
    details  = issue["details"]
    severity = Severity(issue["severity"])

    return CleaningAction(
        column_name=col,
        issue_type=IssueType.constant_column,
        severity=severity,
        current_state=details,
        recommendation=ActionType.drop_constant,
        reason=(
            f"Column '{col}' contains only one distinct value across all rows. "
            "Zero-variance features provide no discriminative power to any ML model "
            "and cause arithmetic failures in normalisation steps (e.g. StandardScaler "
            "divides by standard deviation, which is 0 for constant columns). "
            "Verify this is not a data loading error before dropping."
        ),
        confidence_score=_CONF_HIGH,
        auto_applicable=False,   # confirm it is not a loading artefact
    )


# ── Invalid email rule ────────────────────────────────────────────────────────

def _rule_invalid_emails(issue: dict[str, Any]) -> CleaningAction:
    """Recommend validate_emails for columns with malformed email addresses.

    Malformed emails (missing '@', no domain, whitespace) are silent failures:
        - Feature extraction on email domain breaks on malformed strings
        - Email-based joins/lookups silently drop or mismap rows
        - Sending pipelines fail at runtime

    auto_applicable=False — email validation requires domain-specific rules
    (some 'invalid' emails may be internal IDs or legacy formats).
    """
    col      = issue["column"]
    details  = issue["details"]
    severity = Severity(issue["severity"])
    pct      = _extract_pct(details)

    # Confidence scales with the malformed percentage
    confidence = _CONF_HIGH if pct > 25.0 else _CONF_MEDIUM

    return CleaningAction(
        column_name=col,
        issue_type=IssueType.invalid_emails,
        severity=severity,
        current_state=details,
        recommendation=ActionType.validate_emails,
        reason=(
            f"Column '{col}' contains {pct:.1f}% malformed email addresses "
            "(values that do not match the pattern user@domain.tld). "
            "Malformed emails cause silent failures in domain-extraction features, "
            "email-based record linkage, and downstream sending pipelines. "
            "Recommend flagging invalid rows for manual review or imputation."
        ),
        confidence_score=confidence,
        auto_applicable=False,   # domain-specific validation rules needed
    )
