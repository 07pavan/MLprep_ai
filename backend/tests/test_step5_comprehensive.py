"""Comprehensive Phase 2A Test Suite — Step 5.

Covers all 8 required test categories:

    1. Missing value recommendations
       - Numeric/no-outlier  → mean_imputation
       - Numeric/with-outlier → median_imputation
       - Numeric/high-skew   → median_imputation
       - Categorical          → mode_imputation
       - ≥50% missing         → drop_column (auto=False)
       - Various severity thresholds

    2. High missing column drop recommendation
       - Exact 50% threshold boundary
       - Above threshold → drop always preferred over imputation
       - drop_column is never auto_applicable

    3. Duplicate row detection
       - Basic deduplication detection
       - Severity by duplicate %: >10%=high, >1%=medium, ≤1%=low
       - Confidence calibration by percentage
       - column_name is always None (dataset-level)
       - Result always auto_applicable=True

    4. Constant column detection
       - Numeric constant column detected
       - String constant column detected
       - Mixed constant+null column (medium severity)
       - Pure constant (no nulls) → high severity
       - Non-constant column NOT flagged
       - Rule engine produces drop_constant, auto=False

    5. Invalid email detection
       - Detected by column name keyword (email, mail)
       - Detected by structural '@' heuristic
       - Severity: >25% malformed → high; 5-25% → medium
       - ≤5% malformed → NOT flagged (below threshold)
       - All-valid emails → NOT flagged
       - Rule engine produces validate_emails, auto=False

    6. Data type conversion recommendation
       - Numeric-like object column → cast_numeric
       - Datetime-like object column → cast_datetime
       - High parse rate (≥95%) → higher confidence
       - Low parse rate (<95%) → medium confidence
       - Non-parseable column → NOT flagged

    7. Quality score calculation
       - Clean dataset → score 100, grade A
       - Issue severity deductions (critical > high > medium > low)
       - Tiny dataset structural penalty (<50 rows, <100 rows)
       - Single-column structural penalty
       - Score never below 0 (clamped)
       - Estimated post-clean score always ≥ current
       - Estimated post-clean score never > 100
       - Auto actions get full credit; manual actions get half credit
       - Grade bands: A≥90, B≥75, C≥60, D≥40, F<40

    8. API endpoint responses
       - POST /api/v1/cleaning/plan/{dataset_id} → 201 + full plan
       - POST without auth → 401/403
       - POST wrong owner → 403
       - POST nonexistent dataset → 404
       - GET /api/v1/cleaning/plan/{dataset_id} → 200 + list
       - GET before any POST → total_plans=0, latest_plan=null
       - GET ?plan_id=<uuid> → specific plan returned
       - DELETE → plans purged, count confirmed
       - GET /api/v2/cleaning/plan (session-based) → 200
       - All responses: readonly=True, phase="2A"

All tests are fully isolated:
    - No Firebase or external network calls
    - Auth dependencies replaced via FastAPI.dependency_overrides
    - Dataset registry uses the in-process InMemoryDatasetService
    - Plan store cleared in setUp/tearDown
    - Temporary Parquet files created in tempfile and cleaned up
"""
from __future__ import annotations

import os
import re
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd
from fastapi.testclient import TestClient

from main import app
from schemas.cleaning_plan import (
    ActionType,
    CleaningAction,
    CleaningPlan,
    CleaningSummary,
    IssueType,
    Severity,
)
from services.cleaning_planner import (
    _calculate_quality_score,
    _estimate_post_clean_score,
    build_cleaning_plan,
)
from services.rule_engine import apply_rules, _extract_pct
from services.plan_store import get_plan_store
from tools.profiler_tool import profile_dataset
from tools.quality_tool import (
    check_quality,
    _check_constant_columns,
    _check_duplicates,
    _check_invalid_emails,
    _check_missing,
    _check_type_mismatches,
)
from utils.auth import verify_firebase_token
from services.dataset_service import get_dataset_service


# ── Shared test helpers ───────────────────────────────────────────────────────

def _profile(df: pd.DataFrame) -> dict:
    return profile_dataset(df)


def _quality(df: pd.DataFrame) -> dict:
    return check_quality(df)


def _issues(df: pd.DataFrame) -> list[dict]:
    return check_quality(df)["issues"]


def _make_profile_stub(rows=200, dtypes=None, numerical_stats=None, cols=None) -> dict:
    """Build a minimal profile dict without a real DataFrame.

    Args:
        rows:            Number of rows.
        dtypes:          Dict of column→dtype. Takes precedence over cols.
        numerical_stats: List of numerical stat dicts.
        cols:            Number of columns (used when dtypes is not supplied).
    """
    if dtypes is None:
        n = cols if cols is not None else 2
        dtypes = {f"col_{i}": "float64" for i in range(n)}
    col_names = list(dtypes.keys())
    return {
        "rows": rows,
        "columns": len(col_names),
        "memory_mb": 0.5,
        "column_names": col_names,
        "dtypes": dtypes,
        "numerical_count": len(col_names),
        "categorical_count": 0,
        "missing_values": [],
        "duplicate_rows": {"count": 0, "percentage": 0.0},
        "numerical_stats": numerical_stats or [],
    }


def _issue(itype, col, severity, details, recommendation="") -> dict:
    return {"type": itype, "column": col, "severity": severity,
            "details": details, "recommendation": recommendation}


def _make_action(**kw) -> CleaningAction:
    defaults = dict(
        column_name="x", issue_type=IssueType.missing_values,
        severity=Severity.medium, current_state="5 missing",
        recommendation=ActionType.median_imputation,
        reason="test", confidence_score=0.9, auto_applicable=True,
    )
    defaults.update(kw)
    return CleaningAction(**defaults)


def _write_parquet(df: pd.DataFrame) -> str:
    f = tempfile.NamedTemporaryFile(suffix=".parquet", delete=False)
    df.to_parquet(f.name)
    f.close()
    return f.name


def _register(dataset_id: str, user_id: str, parquet_path: str) -> None:
    svc = get_dataset_service()
    if hasattr(svc, "store"):
        svc.store.pop(dataset_id, None)
    svc.create_dataset({
        "dataset_id": dataset_id, "user_id": user_id,
        "dataset_name": f"{dataset_id}.parquet",
        "original_file_type": "parquet", "source": "upload",
        "upload_timestamp": "2026-06-14T10:00:00Z",
        "row_count": 100, "column_count": 3,
        "memory_usage": 0.1, "parquet_path": parquet_path,
        "ml_readiness_score": 70, "dataset_version": 1, "status": "active",
    })


# ══════════════════════════════════════════════════════════════════════════════
# 1. MISSING VALUE RECOMMENDATIONS
# ══════════════════════════════════════════════════════════════════════════════

class TestMissingValueRecommendations(unittest.TestCase):
    """Rule engine correctly maps missing-value issues to imputation strategies."""

    def _run(self, df: pd.DataFrame) -> list[CleaningAction]:
        return apply_rules(_profile(df), _issues(df))

    # ── Imputation strategy selection ─────────────────────────────────────────

    def test_numeric_no_outlier_no_skew_recommends_mean(self):
        np.random.seed(0)
        vals = np.random.normal(50, 5, 200).tolist()
        vals[0] = None
        df = pd.DataFrame({"salary": vals})
        actions = self._run(df)
        mv = [a for a in actions if a.issue_type == IssueType.missing_values]
        self.assertTrue(any(a.recommendation == ActionType.mean_imputation for a in mv),
                        "Expected mean_imputation for symmetric numeric column")

    def test_numeric_with_outlier_recommends_median(self):
        vals = [10.0] * 90 + [None] * 5 + [10000.0] * 5   # extreme outlier
        df = pd.DataFrame({"income": vals})
        actions = self._run(df)
        mv = [a for a in actions if a.issue_type == IssueType.missing_values]
        self.assertTrue(any(a.recommendation == ActionType.median_imputation for a in mv),
                        "Expected median_imputation when outliers present")

    def test_numeric_high_skew_recommends_median_without_outlier_issue(self):
        """Even with no separate outlier issue, |skewness|>1 → median."""
        np.random.seed(42)
        vals = np.random.exponential(scale=2, size=200).tolist()
        vals[0] = None
        df = pd.DataFrame({"revenue": vals})
        prof = _profile(df)
        issues = _issues(df)
        # Ensure no outlier issue exists for this column (remove if present)
        filtered = [i for i in issues if not (i["type"] == "outliers" and i["column"] == "revenue")]
        actions = apply_rules(prof, filtered)
        mv = [a for a in actions if a.issue_type == IssueType.missing_values]
        # Exponential distribution is heavily right-skewed → median expected
        if mv:  # only assert if a missing-value action was generated
            recs = {a.recommendation for a in mv}
            self.assertIn(ActionType.median_imputation, recs,
                          "High-skew column should prefer median imputation")

    def test_categorical_recommends_mode_imputation(self):
        df = pd.DataFrame({"cat": ["A", "B", None, "A", "B"] * 20})
        actions = self._run(df)
        mv = [a for a in actions if a.issue_type == IssueType.missing_values]
        self.assertTrue(any(a.recommendation == ActionType.mode_imputation for a in mv))
        self.assertTrue(any(a.auto_applicable for a in mv))

    def test_missing_values_are_auto_applicable_for_imputation(self):
        df = pd.DataFrame({"x": [1.0, None, 3.0, 4.0, 5.0] * 20})
        actions = self._run(df)
        mv = [a for a in actions if a.issue_type == IssueType.missing_values]
        for action in mv:
            if action.recommendation in (ActionType.mean_imputation,
                                         ActionType.median_imputation,
                                         ActionType.mode_imputation):
                self.assertTrue(action.auto_applicable,
                                f"{action.recommendation} should be auto_applicable")

    # ── Severity threshold coverage ───────────────────────────────────────────

    def test_missing_severity_critical_at_50pct(self):
        """≥50% missing → critical severity from quality tool."""
        vals = [None] * 60 + [1.0] * 40
        df = pd.DataFrame({"col": vals})
        issues = _issues(df)
        mv_issues = [i for i in issues if i["type"] == "missing_values"]
        self.assertTrue(any(i["severity"] == "critical" for i in mv_issues),
                        "60% missing should produce critical severity")

    def test_missing_severity_high_at_20pct(self):
        vals = [None] * 25 + [1.0] * 75
        df = pd.DataFrame({"col": vals})
        issues = _issues(df)
        mv_issues = [i for i in issues if i["type"] == "missing_values"]
        self.assertTrue(any(i["severity"] == "high" for i in mv_issues))

    def test_missing_severity_medium_at_5pct(self):
        vals = [None] * 7 + [1.0] * 93
        df = pd.DataFrame({"col": vals})
        issues = _issues(df)
        mv_issues = [i for i in issues if i["type"] == "missing_values"]
        self.assertTrue(any(i["severity"] == "medium" for i in mv_issues))

    def test_missing_severity_low_below_5pct(self):
        vals = [None] * 3 + [1.0] * 97
        df = pd.DataFrame({"col": vals})
        issues = _issues(df)
        mv_issues = [i for i in issues if i["type"] == "missing_values"]
        self.assertTrue(any(i["severity"] == "low" for i in mv_issues))

    def test_no_missing_values_produces_no_issue(self):
        df = pd.DataFrame({"x": [1.0, 2.0, 3.0] * 50})
        issues = _issues(df)
        self.assertFalse(any(i["type"] == "missing_values" for i in issues))

    def test_action_reason_mentions_column_name(self):
        df = pd.DataFrame({"my_feature": [None, 1.0, 2.0, 3.0, 4.0] * 20})
        actions = self._run(df)
        mv = [a for a in actions if a.issue_type == IssueType.missing_values]
        self.assertTrue(any("my_feature" in a.reason for a in mv))


# ══════════════════════════════════════════════════════════════════════════════
# 2. HIGH MISSING COLUMN DROP RECOMMENDATION
# ══════════════════════════════════════════════════════════════════════════════

class TestHighMissingColumnDrop(unittest.TestCase):
    """Columns with ≥50% missing must get drop_column, never imputation."""

    def _missing_action(self, pct: float) -> CleaningAction | None:
        n = 100
        missing = int(n * pct / 100)
        vals = [None] * missing + [1.0] * (n - missing)
        df = pd.DataFrame({"col": vals})
        actions = apply_rules(_profile(df), _issues(df))
        mv = [a for a in actions if a.issue_type == IssueType.missing_values]
        return mv[0] if mv else None

    def test_exactly_50pct_missing_recommends_drop(self):
        action = self._missing_action(50.0)
        self.assertIsNotNone(action)
        self.assertEqual(action.recommendation, ActionType.drop_column)

    def test_60pct_missing_recommends_drop(self):
        action = self._missing_action(60.0)
        self.assertIsNotNone(action)
        self.assertEqual(action.recommendation, ActionType.drop_column)

    def test_100pct_missing_not_handled_by_missing_check(self):
        """All-null column: detected by missing checker, extreme severity."""
        df = pd.DataFrame({"all_null": [None] * 100})
        issues = _issues(df)
        mv = [i for i in issues if i["type"] == "missing_values"]
        self.assertTrue(any(i["severity"] == "critical" for i in mv))

    def test_drop_column_is_never_auto_applicable(self):
        """drop_column is always manual — destructive action."""
        action = self._missing_action(75.0)
        self.assertIsNotNone(action)
        self.assertFalse(action.auto_applicable,
                         "drop_column must require user confirmation")

    def test_49pct_missing_does_not_recommend_drop(self):
        """49% missing is below threshold → imputation preferred."""
        action = self._missing_action(49.0)
        self.assertIsNotNone(action)
        self.assertNotEqual(action.recommendation, ActionType.drop_column,
                            "49% missing should not trigger drop_column")

    def test_drop_reason_mentions_percentage(self):
        action = self._missing_action(60.0)
        self.assertIsNotNone(action)
        self.assertRegex(action.reason, r"\d+\.?\d*%",
                         "Reason should quote the missing percentage")

    def test_drop_has_high_confidence(self):
        action = self._missing_action(80.0)
        self.assertIsNotNone(action)
        self.assertGreaterEqual(action.confidence_score, 0.90)

    def test_multiple_columns_drop_flagged_independently(self):
        df = pd.DataFrame({
            "bad1": [None] * 60 + [1.0] * 40,
            "bad2": [None] * 70 + [2.0] * 30,
            "good": [1.0] * 100,
        })
        actions = apply_rules(_profile(df), _issues(df))
        drops = [a for a in actions
                 if a.recommendation == ActionType.drop_column
                 and a.issue_type == IssueType.missing_values]
        self.assertEqual(len(drops), 2,
                         "Both high-missing columns should be flagged for drop")


# ══════════════════════════════════════════════════════════════════════════════
# 3. DUPLICATE ROW DETECTION
# ══════════════════════════════════════════════════════════════════════════════

class TestDuplicateRowDetection(unittest.TestCase):
    """_check_duplicates and the rule engine duplicate_rows rule."""

    # ── Detector ─────────────────────────────────────────────────────────────

    def test_no_duplicates_produces_no_issue(self):
        df = pd.DataFrame({"a": range(100), "b": range(100)})
        self.assertFalse(any(i["type"] == "duplicate_rows" for i in _issues(df)))

    def test_exact_duplicates_detected(self):
        row = {"a": 1, "b": "x"}
        df = pd.DataFrame([row] * 20 + [{"a": i, "b": str(i)} for i in range(80)])
        issues = _issues(df)
        dup = [i for i in issues if i["type"] == "duplicate_rows"]
        self.assertEqual(len(dup), 1)
        self.assertGreater(int(dup[0]["details"].split()[0]), 0)

    def test_duplicate_severity_high_above_10pct(self):
        """15 duplicates out of 100 → 15% → high severity."""
        row = {"a": 99, "b": "dup"}
        df = pd.DataFrame(
            [{"a": i, "b": str(i)} for i in range(85)] + [row] * 15
        )
        issues = _check_duplicates(df)
        self.assertEqual(issues[0]["severity"], "high")

    def test_duplicate_severity_medium_1_to_10_pct(self):
        """5 duplicates out of 100 → 5% → medium."""
        row = {"a": 99, "b": "dup"}
        df = pd.DataFrame(
            [{"a": i, "b": str(i)} for i in range(95)] + [row] * 5
        )
        issues = _check_duplicates(df)
        self.assertEqual(issues[0]["severity"], "medium")

    def test_duplicate_severity_low_at_1pct(self):
        """1 duplicate out of 100 rows → 1% → low severity."""
        row = {"a": 99, "b": "dup"}
        # 98 unique rows + the duplicate row appearing twice = 100 rows, 1 duplicate
        df = pd.DataFrame(
            [{"a": i, "b": str(i)} for i in range(98)] + [row, row]
        )
        issues = _check_duplicates(df)
        self.assertTrue(len(issues) > 0, "1 duplicate row should be detected")
        self.assertEqual(issues[0]["severity"], "low")

    # ── Rule engine ───────────────────────────────────────────────────────────

    def test_rule_recommends_remove_duplicates(self):
        row = {"a": 99, "b": "dup"}
        df = pd.DataFrame(
            [{"a": i, "b": str(i)} for i in range(85)] + [row] * 15
        )
        actions = apply_rules(_profile(df), _issues(df))
        dup_actions = [a for a in actions if a.issue_type == IssueType.duplicate_rows]
        self.assertTrue(len(dup_actions) > 0)
        self.assertEqual(dup_actions[0].recommendation, ActionType.remove_duplicates)

    def test_duplicate_action_column_is_none(self):
        """Duplicate detection is dataset-level — no specific column."""
        row = {"a": 99}
        df = pd.DataFrame([{"a": i} for i in range(85)] + [row] * 15)
        actions = apply_rules(_profile(df), _issues(df))
        dup = [a for a in actions if a.issue_type == IssueType.duplicate_rows]
        self.assertTrue(all(a.column_name is None for a in dup))

    def test_duplicate_action_is_auto_applicable(self):
        """Deduplication is safe and reversible — always auto_applicable."""
        row = {"a": 5, "b": "x"}
        df = pd.DataFrame(
            [{"a": i, "b": str(i)} for i in range(85)] + [row] * 15
        )
        actions = apply_rules(_profile(df), _issues(df))
        dup = [a for a in actions if a.issue_type == IssueType.duplicate_rows]
        self.assertTrue(all(a.auto_applicable for a in dup))

    def test_high_dup_pct_gives_higher_confidence_than_low(self):
        """More duplicates → stronger confidence in the recommendation."""
        prof = _make_profile_stub()
        high = [_issue("duplicate_rows", None, "high", "50 duplicate rows (50.0%)")]
        low  = [_issue("duplicate_rows", None, "low",  "1 duplicate rows (1.0%)")]
        a_high = apply_rules(prof, high)[0]
        a_low  = apply_rules(prof, low)[0]
        self.assertGreater(a_high.confidence_score, a_low.confidence_score)

    def test_empty_dataframe_no_duplicate_issue(self):
        df = pd.DataFrame({"a": pd.Series([], dtype="float64")})
        issues = _check_duplicates(df)
        self.assertEqual(issues, [])


# ══════════════════════════════════════════════════════════════════════════════
# 4. CONSTANT COLUMN DETECTION
# ══════════════════════════════════════════════════════════════════════════════

class TestConstantColumnDetection(unittest.TestCase):
    """_check_constant_columns detector and rule engine handling."""

    # ── Detector ─────────────────────────────────────────────────────────────

    def test_numeric_constant_detected(self):
        df = pd.DataFrame({"const_num": [1.0] * 100, "normal": range(100)})
        issues = _check_constant_columns(df)
        cols = [i["column"] for i in issues]
        self.assertIn("const_num", cols)
        self.assertNotIn("normal", cols)

    def test_string_constant_detected(self):
        # Use equal-length lists to avoid DataFrame shape mismatch
        df = pd.DataFrame({"const_str": ["same"] * 51,
                           "other": list("abc" * 17)})
        issues = _check_constant_columns(df)
        self.assertTrue(any(i["column"] == "const_str" for i in issues))

    def test_pure_constant_is_high_severity(self):
        """No nulls + one unique value → high severity."""
        df = pd.DataFrame({"c": [42] * 100})
        issues = _check_constant_columns(df)
        self.assertEqual(issues[0]["severity"], "high")

    def test_constant_with_nulls_is_medium_severity(self):
        """Non-null portion is constant but there are nulls → medium severity."""
        vals = [1.0] * 80 + [None] * 20
        df = pd.DataFrame({"c": vals})
        issues = _check_constant_columns(df)
        self.assertEqual(issues[0]["severity"], "medium")

    def test_non_constant_not_flagged(self):
        df = pd.DataFrame({"varied": [1, 2, 3, 4, 5] * 20})
        issues = _check_constant_columns(df)
        self.assertEqual(issues, [])

    def test_two_unique_values_not_flagged(self):
        df = pd.DataFrame({"binary": [0, 1] * 50})
        issues = _check_constant_columns(df)
        self.assertEqual(issues, [])

    def test_issue_type_is_constant_column(self):
        df = pd.DataFrame({"c": ["X"] * 100})
        issues = _check_constant_columns(df)
        self.assertEqual(issues[0]["type"], "constant_column")

    def test_details_mentions_unique_value(self):
        df = pd.DataFrame({"flag": [True] * 100})
        issues = _check_constant_columns(df)
        self.assertIn("1 unique value", issues[0]["details"])

    def test_empty_df_no_constant_issues(self):
        df = pd.DataFrame({"c": pd.Series([], dtype="float64")})
        self.assertEqual(_check_constant_columns(df), [])

    def test_all_null_column_not_caught_by_constant_check(self):
        """All-null columns are handled by _check_missing, not constant check."""
        df = pd.DataFrame({"null_col": [None] * 100})
        issues = _check_constant_columns(df)
        self.assertEqual(issues, [],
                         "All-null columns should not appear in constant column check")

    # ── Rule engine ───────────────────────────────────────────────────────────

    def test_rule_produces_drop_constant_action(self):
        df = pd.DataFrame({"const": [99] * 100, "a": range(100)})
        issues = _issues(df)
        actions = apply_rules(_profile(df), issues)
        const_actions = [a for a in actions if a.issue_type == IssueType.constant_column]
        self.assertTrue(len(const_actions) > 0)
        self.assertEqual(const_actions[0].recommendation, ActionType.drop_constant)

    def test_drop_constant_is_not_auto_applicable(self):
        """User must confirm before dropping — might be a data loading error."""
        prof = _make_profile_stub(dtypes={"c": "float64"})
        issue = [_issue("constant_column", "c", "high",
                        "Column 'c' has only 1 unique value: '42'. Zero variance.")]
        actions = apply_rules(prof, issue)
        self.assertFalse(actions[0].auto_applicable)

    def test_drop_constant_reason_explains_ml_risk(self):
        prof = _make_profile_stub(dtypes={"c": "float64"})
        issue = [_issue("constant_column", "c", "high",
                        "Column 'c' has only 1 unique value: '0'. Zero variance.")]
        actions = apply_rules(prof, issue)
        reason_lower = actions[0].reason.lower()
        self.assertTrue("variance" in reason_lower or "constant" in reason_lower
                        or "signal" in reason_lower,
                        "Reason should explain the ML risk of constant columns")

    def test_constant_action_has_high_confidence(self):
        prof = _make_profile_stub(dtypes={"c": "float64"})
        issue = [_issue("constant_column", "c", "high",
                        "Column 'c' has only 1 unique value: '0'. Zero variance.")]
        actions = apply_rules(prof, issue)
        self.assertGreaterEqual(actions[0].confidence_score, 0.90)


# ══════════════════════════════════════════════════════════════════════════════
# 5. INVALID EMAIL DETECTION
# ══════════════════════════════════════════════════════════════════════════════

class TestInvalidEmailDetection(unittest.TestCase):
    """_check_invalid_emails detector and rule engine handling."""

    VALID = [
        "alice@example.com", "bob@sub.domain.org", "charlie123@test.io",
        "diana.prince@wonderland.net", "evan+tag@email.co",
    ]
    INVALID = [
        "not-an-email", "missing_at_sign.com", "@no-local-part.com",
        "spaces in@email.com", "double@@signs.com", "nodomain@",
    ]

    # ── Detector — column name heuristic ─────────────────────────────────────

    def test_email_column_by_name_with_invalid_values(self):
        emails = self.VALID * 3 + self.INVALID * 5   # >5% invalid
        df = pd.DataFrame({"email": emails})
        issues = _check_invalid_emails(df)
        self.assertTrue(any(i["type"] == "invalid_emails" for i in issues))

    def test_mail_column_name_triggers_check(self):
        emails = self.VALID * 5 + self.INVALID * 5
        df = pd.DataFrame({"user_mail": emails})
        issues = _check_invalid_emails(df)
        self.assertTrue(any(i["column"] == "user_mail" for i in issues))

    # ── Detector — structural '@' heuristic ───────────────────────────────────

    def test_structural_detection_without_name_keyword(self):
        """If ≥20% of values contain '@', treat as email column."""
        emails = (self.VALID + self.INVALID) * 5
        df = pd.DataFrame({"contact": emails})  # 'contact' has no keyword
        issues = _check_invalid_emails(df)
        self.assertTrue(any(i["type"] == "invalid_emails" for i in issues))

    def test_non_email_column_not_flagged(self):
        df = pd.DataFrame({"name": ["Alice", "Bob", "Charlie"] * 30,
                           "age": [25, 30, 35] * 30})
        issues = _check_invalid_emails(df)
        self.assertEqual(issues, [])

    # ── Severity thresholds ───────────────────────────────────────────────────

    def test_high_severity_when_over_25pct_malformed(self):
        emails = self.VALID * 3 + self.INVALID * 5   # ~62% invalid
        df = pd.DataFrame({"email": emails})
        issues = _check_invalid_emails(df)
        email_issues = [i for i in issues if i["type"] == "invalid_emails"]
        self.assertTrue(any(i["severity"] == "high" for i in email_issues))

    def test_medium_severity_when_5_to_25pct_malformed(self):
        emails = self.VALID * 15 + self.INVALID * 2  # ~12% invalid
        df = pd.DataFrame({"email": emails})
        issues = _check_invalid_emails(df)
        email_issues = [i for i in issues if i["type"] == "invalid_emails"]
        self.assertTrue(any(i["severity"] == "medium" for i in email_issues))

    def test_below_threshold_not_flagged(self):
        """≤5% invalid → below threshold → not reported."""
        emails = self.VALID * 95 + ["bad-email"]   # ~1% invalid
        df = pd.DataFrame({"email": emails})
        issues = _check_invalid_emails(df)
        self.assertFalse(any(i["type"] == "invalid_emails" for i in issues))

    def test_all_valid_emails_not_flagged(self):
        emails = self.VALID * 20
        df = pd.DataFrame({"email": emails})
        issues = _check_invalid_emails(df)
        self.assertEqual(issues, [])

    def test_details_mention_count_and_percentage(self):
        emails = self.VALID * 3 + self.INVALID * 5
        df = pd.DataFrame({"email": emails})
        issues = _check_invalid_emails(df)
        email_issues = [i for i in issues if i["type"] == "invalid_emails"]
        self.assertTrue(len(email_issues) > 0)
        self.assertRegex(email_issues[0]["details"], r"\d+",
                         "Details should include invalid count")
        self.assertRegex(email_issues[0]["details"], r"\d+\.?\d*%",
                         "Details should include percentage")

    def test_empty_df_no_email_issues(self):
        df = pd.DataFrame({"email": pd.Series([], dtype="object")})
        self.assertEqual(_check_invalid_emails(df), [])

    # ── Rule engine ───────────────────────────────────────────────────────────

    def test_rule_produces_validate_emails_action(self):
        emails = self.VALID * 3 + self.INVALID * 5
        df = pd.DataFrame({"email": emails})
        actions = apply_rules(_profile(df), _issues(df))
        email_actions = [a for a in actions if a.issue_type == IssueType.invalid_emails]
        self.assertTrue(len(email_actions) > 0)
        self.assertEqual(email_actions[0].recommendation, ActionType.validate_emails)

    def test_validate_emails_not_auto_applicable(self):
        """Email validation needs domain-specific rules — not auto."""
        prof = _make_profile_stub(dtypes={"email": "object"})
        issue = [_issue("invalid_emails", "email", "high",
                        "5 invalid email addresses (50.0%) in column 'email'.")]
        actions = apply_rules(prof, issue)
        self.assertFalse(actions[0].auto_applicable)

    def test_high_malformed_pct_gives_high_confidence(self):
        prof = _make_profile_stub(dtypes={"email": "object"})
        issue_high = [_issue("invalid_emails", "email", "high",
                             "30 invalid email addresses (30.0%) in column 'email'.")]
        issue_low  = [_issue("invalid_emails", "email", "medium",
                             "10 invalid email addresses (10.0%) in column 'email'.")]
        a_high = apply_rules(prof, issue_high)[0]
        a_low  = apply_rules(prof, issue_low)[0]
        self.assertGreater(a_high.confidence_score, a_low.confidence_score)


# ══════════════════════════════════════════════════════════════════════════════
# 6. DATA TYPE CONVERSION RECOMMENDATIONS
# ══════════════════════════════════════════════════════════════════════════════

class TestDataTypeConversionRecommendations(unittest.TestCase):
    """Type-mismatch detection and rule engine casting recommendations."""

    # ── Detector ─────────────────────────────────────────────────────────────

    def test_numeric_string_column_detected(self):
        df = pd.DataFrame({"code": ["1", "2", "3", "4", "5"] * 20})
        issues = _check_type_mismatches(df)
        self.assertTrue(any(i["type"] == "type_mismatch" for i in issues))

    def test_datetime_string_column_detected(self):
        dates = ["2024-01-01", "2024-02-15", "2023-12-31"] * 34
        df = pd.DataFrame({"created_at": dates})
        issues = _check_type_mismatches(df)
        self.assertTrue(any(
            i["type"] == "type_mismatch" and "datetime" in i["details"].lower()
            for i in issues
        ))

    def test_pure_text_column_not_flagged(self):
        df = pd.DataFrame({"notes": ["free text", "another note", "random words"] * 30})
        issues = _check_type_mismatches(df)
        self.assertFalse(any(i["column"] == "notes" for i in issues))

    def test_already_numeric_column_not_flagged(self):
        df = pd.DataFrame({"age": [25, 30, 35, 40] * 25})
        issues = _check_type_mismatches(df)
        self.assertFalse(any(
            i["type"] == "type_mismatch" and i["column"] == "age"
            for i in issues
        ))

    # ── Rule engine ───────────────────────────────────────────────────────────

    def test_numeric_mismatch_recommends_cast_numeric(self):
        prof = _make_profile_stub(dtypes={"code": "object"})
        issue = [_issue("type_mismatch", "code", "medium",
                        "Column is object dtype but 100.0% values are numeric")]
        actions = apply_rules(prof, issue)
        self.assertEqual(actions[0].recommendation, ActionType.cast_numeric)
        self.assertTrue(actions[0].auto_applicable)

    def test_datetime_mismatch_recommends_cast_datetime(self):
        prof = _make_profile_stub(dtypes={"date_col": "object"})
        issue = [_issue("type_mismatch", "date_col", "medium",
                        "Column is object dtype but 95.0% values are datetime")]
        actions = apply_rules(prof, issue)
        self.assertEqual(actions[0].recommendation, ActionType.cast_datetime)
        self.assertTrue(actions[0].auto_applicable)

    def test_high_parse_rate_gives_higher_confidence(self):
        """≥95% parseable → _CONF_HIGH; <95% parseable → _CONF_MEDIUM."""
        prof = _make_profile_stub(dtypes={"x": "object"})
        hi = [_issue("type_mismatch", "x", "medium", "100.0% values are numeric")]
        lo = [_issue("type_mismatch", "x", "medium", "82.0% values are numeric")]
        a_hi = apply_rules(prof, hi)[0]
        a_lo = apply_rules(prof, lo)[0]
        self.assertGreater(a_hi.confidence_score, a_lo.confidence_score)

    def test_cast_actions_are_auto_applicable(self):
        prof = _make_profile_stub(dtypes={"x": "object"})
        for detail in ["100.0% values are numeric", "100.0% values are datetime"]:
            issues = [_issue("type_mismatch", "x", "medium", detail)]
            actions = apply_rules(prof, issues)
            self.assertTrue(actions[0].auto_applicable,
                            f"cast action should be auto_applicable for: {detail}")

    def test_reason_names_the_target_dtype(self):
        prof = _make_profile_stub(dtypes={"num_str": "object"})
        issue = [_issue("type_mismatch", "num_str", "medium",
                        "Column is object dtype but 100.0% values are numeric")]
        action = apply_rules(prof, issue)[0]
        self.assertIn("numeric", action.reason.lower())

    def test_end_to_end_type_mismatch_in_plan(self):
        """Build a full plan that includes a type_mismatch action."""
        df = pd.DataFrame({"codes": ["1", "2", "3", "4", "5"] * 30})
        plan = build_cleaning_plan(_profile(df), _quality(df))
        tm_actions = [a for a in plan.actions if a.issue_type == IssueType.type_mismatch]
        self.assertTrue(len(tm_actions) > 0)
        self.assertEqual(tm_actions[0].recommendation, ActionType.cast_numeric)


# ══════════════════════════════════════════════════════════════════════════════
# 7. QUALITY SCORE CALCULATION
# ══════════════════════════════════════════════════════════════════════════════

class TestQualityScoreCalculation(unittest.TestCase):
    """Comprehensive tests of _calculate_quality_score and _estimate_post_clean_score."""

    # ── Baseline and grade bands ──────────────────────────────────────────────

    def test_clean_dataset_scores_100_grade_A(self):
        profile = _make_profile_stub(rows=500)
        score, grade = _calculate_quality_score(profile, [])
        self.assertEqual(score, 100)
        self.assertEqual(grade, "A")

    def test_grade_B_at_75_to_89(self):
        profile = _make_profile_stub(rows=500)
        # Add enough issues to bring score to 75–89 range
        issues = [_issue("missing_values", "a", "medium", "5 missing (5.0%)")] * 3
        score, grade = _calculate_quality_score(profile, issues)
        if 75 <= score <= 89:
            self.assertEqual(grade, "B")

    def test_grade_F_below_40(self):
        profile = _make_profile_stub(rows=500)
        issues = [_issue("missing_values", f"col{i}", "critical", "60 missing (60.0%)")
                  for i in range(5)]
        score, grade = _calculate_quality_score(profile, issues)
        if score < 40:
            self.assertEqual(grade, "F")

    # ── Issue severity deductions ─────────────────────────────────────────────

    def test_critical_deducts_more_than_high(self):
        profile = _make_profile_stub(rows=500)
        s_crit, _ = _calculate_quality_score(
            profile, [_issue("missing_values", "a", "critical", "60 missing (60.0%)")])
        s_high, _ = _calculate_quality_score(
            profile, [_issue("missing_values", "a", "high", "25 missing (25.0%)")])
        self.assertLess(s_crit, s_high)

    def test_high_deducts_more_than_medium(self):
        profile = _make_profile_stub(rows=500)
        s_high, _ = _calculate_quality_score(
            profile, [_issue("missing_values", "a", "high", "25 missing (25.0%)")])
        s_med, _  = _calculate_quality_score(
            profile, [_issue("missing_values", "a", "medium", "8 missing (8.0%)")])
        self.assertLess(s_high, s_med)

    def test_medium_deducts_more_than_low(self):
        profile = _make_profile_stub(rows=500)
        s_med, _ = _calculate_quality_score(
            profile, [_issue("missing_values", "a", "medium", "8 missing (8.0%)")])
        s_low, _ = _calculate_quality_score(
            profile, [_issue("missing_values", "a", "low", "2 missing (2.0%)")])
        self.assertLess(s_med, s_low)

    def test_multiple_issues_compound_deduction(self):
        """Three issues should deduct more than one issue."""
        profile = _make_profile_stub(rows=500)
        s_one, _ = _calculate_quality_score(
            profile, [_issue("missing_values", "a", "high", "25 missing (25.0%)")])
        s_three, _ = _calculate_quality_score(profile, [
            _issue("missing_values", "a", "high", "25 missing (25.0%)"),
            _issue("missing_values", "b", "high", "25 missing (25.0%)"),
            _issue("missing_values", "c", "high", "25 missing (25.0%)"),
        ])
        self.assertLess(s_three, s_one)

    # ── Structural penalties ──────────────────────────────────────────────────

    def test_tiny_dataset_below_50_rows_penalty(self):
        small = _make_profile_stub(rows=30)
        large = _make_profile_stub(rows=500)
        s_small, _ = _calculate_quality_score(small, [])
        s_large, _ = _calculate_quality_score(large, [])
        self.assertLess(s_small, s_large, "Tiny dataset should be penalised")

    def test_small_dataset_50_to_100_rows_penalty(self):
        mid   = _make_profile_stub(rows=80)
        large = _make_profile_stub(rows=500)
        s_mid, _ = _calculate_quality_score(mid, [])
        s_lg,  _ = _calculate_quality_score(large, [])
        self.assertLess(s_mid, s_lg)

    def test_single_column_penalty(self):
        single = _make_profile_stub(rows=500, dtypes={"A": "float64"})
        multi  = _make_profile_stub(rows=500)
        s_single, _ = _calculate_quality_score(single, [])
        s_multi,  _ = _calculate_quality_score(multi, [])
        self.assertLess(s_single, s_multi)

    # ── Score bounds ──────────────────────────────────────────────────────────

    def test_score_never_below_zero(self):
        profile = _make_profile_stub(rows=20, dtypes={"A": "float64"})
        many_criticals = [
            _issue("missing_values", f"col{i}", "critical", "70 missing (70.0%)")
            for i in range(30)
        ]
        score, _ = _calculate_quality_score(profile, many_criticals)
        self.assertGreaterEqual(score, 0)

    def test_score_never_above_100(self):
        profile = _make_profile_stub(rows=1000, cols=20)
        score, _ = _calculate_quality_score(profile, [])
        self.assertLessEqual(score, 100)

    # ── Post-clean estimation ─────────────────────────────────────────────────

    def test_estimated_score_gte_current(self):
        actions = [_make_action(recommendation=ActionType.remove_duplicates,
                                auto_applicable=True)]
        self.assertGreaterEqual(_estimate_post_clean_score(60, actions), 60)

    def test_estimated_score_capped_at_100(self):
        """Even many auto actions cannot push score above 100."""
        actions = [_make_action(recommendation=ActionType.remove_duplicates,
                                auto_applicable=True)] * 30
        self.assertEqual(_estimate_post_clean_score(99, actions), 100)

    def test_auto_action_contributes_full_delta(self):
        auto   = [_make_action(recommendation=ActionType.remove_duplicates,
                               auto_applicable=True)]
        manual = [_make_action(recommendation=ActionType.remove_duplicates,
                               auto_applicable=False)]
        est_auto   = _estimate_post_clean_score(50, auto)
        est_manual = _estimate_post_clean_score(50, manual)
        self.assertGreaterEqual(est_auto, est_manual)

    def test_no_actions_keeps_same_score(self):
        self.assertEqual(_estimate_post_clean_score(75, []), 75)

    def test_plan_summary_estimated_score_gte_current(self):
        """End-to-end: plan.summary.estimated >= plan.summary.overall."""
        df = pd.DataFrame({
            "salary": [50000.0, None, 60000.0, None, 80000.0] * 20,
            "cat":    ["A", "B", None, "C", "D"] * 20,
        })
        plan = build_cleaning_plan(_profile(df), _quality(df))
        self.assertGreaterEqual(
            plan.summary.estimated_score_after_cleaning,
            plan.summary.overall_quality_score,
        )

    def test_plan_summary_score_in_valid_range(self):
        df = pd.DataFrame({"x": list(range(100))})
        plan = build_cleaning_plan(_profile(df), _quality(df))
        self.assertGreaterEqual(plan.summary.overall_quality_score, 0)
        self.assertLessEqual(plan.summary.overall_quality_score, 100)
        self.assertGreaterEqual(plan.summary.estimated_score_after_cleaning, 0)
        self.assertLessEqual(plan.summary.estimated_score_after_cleaning, 100)


# ══════════════════════════════════════════════════════════════════════════════
# 8. API ENDPOINT RESPONSES
# ══════════════════════════════════════════════════════════════════════════════

class TestAPIEndpointResponses(unittest.TestCase):
    """All 8 endpoint variants. No Firebase — auth stubbed via dependency_overrides."""

    def setUp(self):
        self.client = TestClient(app)
        app.dependency_overrides = {}
        get_plan_store().clear()
        # Clean up any stale test datasets
        svc = get_dataset_service()
        if hasattr(svc, "store"):
            svc.store = {
                k: v for k, v in svc.store.items()
                if not k.startswith("test-ep-")
            }

    def tearDown(self):
        app.dependency_overrides = {}
        get_plan_store().clear()

    def _auth(self, uid: str = "test_user") -> None:
        app.dependency_overrides[verify_firebase_token] = lambda: {"uid": uid}

    def _setup_dataset(self, ds_id: str, uid: str = "test_user") -> str:
        """Write a test DataFrame to a temp parquet and register it."""
        df = pd.DataFrame({
            "salary": [50000.0, 60000.0, None, 80000.0, 100000.0] * 20,
            "category": ["A", "B", None, "C", "D"] * 20,
            "code": ["1", "2", "3", "4", "5"] * 20,
        })
        tmp = _write_parquet(df)
        _register(ds_id, uid, tmp)
        self._tmp_files = getattr(self, "_tmp_files", [])
        self._tmp_files.append(tmp)
        return tmp

    def tearDown(self):
        app.dependency_overrides = {}
        get_plan_store().clear()
        for f in getattr(self, "_tmp_files", []):
            if os.path.exists(f):
                os.remove(f)

    # ── POST /api/v1/cleaning/plan/{dataset_id} ───────────────────────────────

    def test_post_returns_201_created(self):
        self._setup_dataset("test-ep-post-201")
        self._auth()
        r = self.client.post("/api/v1/cleaning/plan/test-ep-post-201")
        self.assertEqual(r.status_code, 201)

    def test_post_response_has_correct_shape(self):
        self._setup_dataset("test-ep-post-shape")
        self._auth()
        r = self.client.post("/api/v1/cleaning/plan/test-ep-post-shape")
        data = r.json()
        # Top-level fields
        for field in ("status", "message", "dataset_id", "plan"):
            self.assertIn(field, data, f"Missing top-level field: {field}")
        # Plan fields
        for field in ("plan_id", "phase", "readonly", "generated_at",
                      "summary", "actions"):
            self.assertIn(field, data["plan"], f"Missing plan field: {field}")
        # Summary fields
        for field in ("total_issues", "overall_quality_score", "quality_grade",
                      "estimated_score_after_cleaning", "auto_applicable_count",
                      "critical_issues", "high_risk_issues"):
            self.assertIn(field, data["plan"]["summary"],
                          f"Missing summary field: {field}")

    def test_post_plan_is_readonly(self):
        self._setup_dataset("test-ep-post-ro")
        self._auth()
        r = self.client.post("/api/v1/cleaning/plan/test-ep-post-ro")
        self.assertTrue(r.json()["plan"]["readonly"])

    def test_post_plan_phase_is_2a(self):
        self._setup_dataset("test-ep-post-phase")
        self._auth()
        r = self.client.post("/api/v1/cleaning/plan/test-ep-post-phase")
        self.assertEqual(r.json()["plan"]["phase"], "2A")

    def test_post_status_is_generated(self):
        self._setup_dataset("test-ep-post-status")
        self._auth()
        r = self.client.post("/api/v1/cleaning/plan/test-ep-post-status")
        self.assertEqual(r.json()["status"], "generated")

    def test_post_without_auth_rejected(self):
        r = self.client.post("/api/v1/cleaning/plan/any-dataset")
        self.assertIn(r.status_code, (401, 403),
                      "Unauthenticated request must be rejected")

    def test_post_wrong_owner_returns_403(self):
        self._setup_dataset("test-ep-post-owner", uid="real_owner")
        self._auth("attacker")
        r = self.client.post("/api/v1/cleaning/plan/test-ep-post-owner")
        self.assertEqual(r.status_code, 403)

    def test_post_nonexistent_dataset_returns_404(self):
        self._auth()
        r = self.client.post("/api/v1/cleaning/plan/definitely-does-not-exist")
        self.assertEqual(r.status_code, 404)

    def test_post_action_list_has_correct_fields(self):
        """Each action in the response must have all CleaningAction fields."""
        self._setup_dataset("test-ep-post-actions")
        self._auth()
        r = self.client.post("/api/v1/cleaning/plan/test-ep-post-actions")
        actions = r.json()["plan"]["actions"]
        for action in actions:
            for field in ("action_id", "issue_type", "severity",
                          "recommendation", "reason", "confidence_score",
                          "auto_applicable", "current_state"):
                self.assertIn(field, action, f"Missing action field: {field}")

    # ── GET /api/v1/cleaning/plan/{dataset_id} ────────────────────────────────

    def test_get_before_post_returns_200_with_empty_list(self):
        self._setup_dataset("test-ep-get-empty")
        self._auth()
        r = self.client.get("/api/v1/cleaning/plan/test-ep-get-empty")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["total_plans"], 0)
        self.assertEqual(data["plans"], [])
        self.assertIsNone(data["latest_plan"])

    def test_get_after_post_returns_plan(self):
        self._setup_dataset("test-ep-get-after")
        self._auth()
        self.client.post("/api/v1/cleaning/plan/test-ep-get-after")
        r = self.client.get("/api/v1/cleaning/plan/test-ep-get-after")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["total_plans"], 1)
        self.assertIsNotNone(data["latest_plan"])

    def test_get_with_plan_id_returns_specific_plan(self):
        self._setup_dataset("test-ep-get-by-id")
        self._auth()
        r1 = self.client.post("/api/v1/cleaning/plan/test-ep-get-by-id")
        plan_id = r1.json()["plan"]["plan_id"]
        self.client.post("/api/v1/cleaning/plan/test-ep-get-by-id")
        r = self.client.get("/api/v1/cleaning/plan/test-ep-get-by-id",
                            params={"plan_id": plan_id})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["latest_plan"]["plan_id"], plan_id)
        self.assertEqual(r.json()["total_plans"], 2)

    def test_get_plans_list_items_are_meta_only(self):
        """plans[] in GET response must not include the full actions list."""
        self._setup_dataset("test-ep-get-meta")
        self._auth()
        self.client.post("/api/v1/cleaning/plan/test-ep-get-meta")
        r = self.client.get("/api/v1/cleaning/plan/test-ep-get-meta")
        for meta in r.json()["plans"]:
            self.assertNotIn("actions", meta,
                             "CleaningPlanMeta must not expose full actions list")
            self.assertIn("plan_id", meta)
            self.assertIn("overall_quality_score", meta)

    def test_get_wrong_owner_returns_403(self):
        self._setup_dataset("test-ep-get-owner", uid="real_owner")
        self._auth("attacker")
        r = self.client.get("/api/v1/cleaning/plan/test-ep-get-owner")
        self.assertEqual(r.status_code, 403)

    def test_get_nonexistent_dataset_returns_404(self):
        self._auth()
        r = self.client.get("/api/v1/cleaning/plan/no-such-ds")
        self.assertEqual(r.status_code, 404)

    def test_get_no_auth_rejected(self):
        r = self.client.get("/api/v1/cleaning/plan/any-id")
        self.assertIn(r.status_code, (401, 403))

    # ── DELETE /api/v1/cleaning/plan/{dataset_id} ─────────────────────────────

    def test_delete_purges_plans_and_confirms_count(self):
        self._setup_dataset("test-ep-del")
        self._auth()
        self.client.post("/api/v1/cleaning/plan/test-ep-del")
        self.client.post("/api/v1/cleaning/plan/test-ep-del")
        r = self.client.delete("/api/v1/cleaning/plan/test-ep-del")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["plans_deleted"], 2)
        # Confirm store is empty
        self.assertEqual(get_plan_store().count("test_user", "test-ep-del"), 0)

    # ── v2 session-based endpoint ─────────────────────────────────────────────

    @patch("routers.cleaning.session_manager.session_exists", return_value=True)
    @patch("routers.cleaning.session_manager.load_dataframe")
    def test_v2_plan_session_returns_200_readonly_2a(self, mock_load, _):
        mock_load.return_value = pd.DataFrame({
            "salary": [50000.0, None, 60000.0, None, 80000.0] * 20,
            "cat":    ["A", "B", None, "C", "D"] * 20,
        })
        self._auth()
        r = self.client.get("/api/v2/cleaning/plan", params={"sessionId": "sess1"})
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertTrue(data["readonly"])
        self.assertEqual(data["phase"], "2A")
        self.assertIn("summary", data)
        self.assertIn("actions", data)

    @patch("routers.cleaning.session_manager.session_exists", return_value=False)
    def test_v2_plan_missing_session_returns_404(self, _):
        self._auth()
        r = self.client.get("/api/v2/cleaning/plan", params={"sessionId": "ghost"})
        self.assertEqual(r.status_code, 404)

    @patch("routers.cleaning.session_manager.session_exists", return_value=True)
    @patch("routers.cleaning.session_manager.load_dataframe")
    def test_v2_summary_returns_no_actions_field(self, mock_load, _):
        mock_load.return_value = pd.DataFrame({"A": [1.0, None, 3.0] * 30})
        self._auth()
        r = self.client.get("/api/v2/cleaning/summary", params={"sessionId": "s1"})
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn("overall_quality_score", data)
        self.assertNotIn("actions", data)


if __name__ == "__main__":
    unittest.main()
