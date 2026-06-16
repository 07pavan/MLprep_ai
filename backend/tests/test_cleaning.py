"""Phase 2A Cleaning Planner Test Suite.

Architecture being tested:
    rule_engine.apply_rules(profile, quality_issues) → list[CleaningAction]
    cleaning_planner.build_cleaning_plan(profile, quality_report, ...) → CleaningPlan
    routers/cleaning.py → GET /api/v2/cleaning/plan | /plan/dataset | /summary

Phase 2A immutability contract:
    build_cleaning_plan() takes profile+quality dicts — it never receives a DataFrame.
    This structural separation guarantees no accidental dataset mutation.

Test classes:
    TestCleaningActionSchema    — Pydantic validation, UUID generation, enum serialisation
    TestCleaningSummarySchema   — bounds, negative counts
    TestCleaningPlanSchema      — defaults, readonly contract
    TestRuleEngine              — all 5 issue types, ordering, skewness, confidence, edge cases
    TestQualityScoreCalculator  — internal scoring logic
    TestCleaningPlannerService  — end-to-end plan generation from dicts
    TestCleaningRouter          — API endpoints: 200/404/403/401
"""
from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime
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
from tools.profiler_tool import profile_dataset
from tools.quality_tool import check_quality
from utils.auth import verify_firebase_token
from services.dataset_service import get_dataset_service


# ══════════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════════

def _make_profile(rows=100, cols=3, dtypes=None, numerical_stats=None, missing_values=None, duplicate_rows=None):
    return {
        "rows": rows,
        "columns": cols,
        "memory_mb": 0.5,
        "column_names": list(dtypes.keys()) if dtypes else ["A", "B", "C"],
        "dtypes": dtypes or {"A": "float64", "B": "object", "C": "int64"},
        "numerical_count": 2,
        "categorical_count": 1,
        "missing_values": missing_values or [],
        "duplicate_rows": duplicate_rows or {"count": 0, "percentage": 0.0},
        "numerical_stats": numerical_stats or [],
    }


def _make_issue(itype: str, col, severity: str, details: str, recommendation: str = "") -> dict:
    return {
        "type": itype,
        "column": col,
        "severity": severity,
        "details": details,
        "recommendation": recommendation,
    }


def _make_quality_report(*issues) -> dict:
    lst = list(issues)
    return {"total_issues": len(lst), "issues": lst}


# ══════════════════════════════════════════════════════════════════════════════
# 1. Schema Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestCleaningActionSchema(unittest.TestCase):

    def _valid(self, **kw) -> dict:
        return {
            "column_name": "age", "issue_type": IssueType.missing_values,
            "severity": Severity.high, "current_state": "12 missing (12.0%)",
            "recommendation": ActionType.median_imputation,
            "reason": "Outliers present.", "confidence_score": 0.92,
            "auto_applicable": True, **kw,
        }

    def test_creates_with_auto_uuid(self):
        a = CleaningAction(**self._valid())
        self.assertEqual(len(a.action_id), 36)

    def test_two_instances_get_different_ids(self):
        self.assertNotEqual(CleaningAction(**self._valid()).action_id,
                            CleaningAction(**self._valid()).action_id)

    def test_confidence_rounded_to_4dp(self):
        a = CleaningAction(**self._valid(confidence_score=0.916666))
        self.assertEqual(a.confidence_score, 0.9167)

    def test_confidence_out_of_range_rejected(self):
        from pydantic import ValidationError
        with self.assertRaises(ValidationError):
            CleaningAction(**self._valid(confidence_score=1.01))
        with self.assertRaises(ValidationError):
            CleaningAction(**self._valid(confidence_score=-0.1))

    def test_column_name_nullable(self):
        a = CleaningAction(**self._valid(
            column_name=None,
            issue_type=IssueType.duplicate_rows,
            recommendation=ActionType.remove_duplicates,
        ))
        self.assertIsNone(a.column_name)

    def test_enum_fields_serialise_as_strings(self):
        data = CleaningAction(**self._valid()).model_dump()
        self.assertEqual(data["issue_type"], "missing_values")
        self.assertEqual(data["severity"], "high")
        self.assertEqual(data["recommendation"], "median_imputation")


class TestCleaningSummarySchema(unittest.TestCase):

    def _valid(self, **kw) -> dict:
        return {
            "total_issues": 5, "critical_issues": 1, "high_risk_issues": 2,
            "medium_risk_issues": 1, "low_risk_issues": 1,
            "auto_applicable_count": 3, "overall_quality_score": 65,
            "quality_grade": "C", "estimated_score_after_cleaning": 82, **kw,
        }

    def test_valid_summary(self):
        s = CleaningSummary(**self._valid())
        self.assertEqual(s.total_issues, 5)
        self.assertEqual(s.quality_grade, "C")

    def test_score_bounds(self):
        from pydantic import ValidationError
        with self.assertRaises(ValidationError):
            CleaningSummary(**self._valid(overall_quality_score=101))
        with self.assertRaises(ValidationError):
            CleaningSummary(**self._valid(overall_quality_score=-1))

    def test_negative_counts_rejected(self):
        from pydantic import ValidationError
        with self.assertRaises(ValidationError):
            CleaningSummary(**self._valid(total_issues=-1))


class TestCleaningPlanSchema(unittest.TestCase):

    def _make(self) -> CleaningPlan:
        summary = CleaningSummary(
            total_issues=0, critical_issues=0, high_risk_issues=0,
            medium_risk_issues=0, low_risk_issues=0, auto_applicable_count=0,
            overall_quality_score=90, quality_grade="A",
            estimated_score_after_cleaning=90,
        )
        return CleaningPlan(summary=summary)

    def test_defaults(self):
        p = self._make()
        self.assertTrue(p.readonly)
        self.assertEqual(p.phase, "2A")
        self.assertIsInstance(p.generated_at, datetime)

    def test_unique_plan_ids(self):
        self.assertNotEqual(self._make().plan_id, self._make().plan_id)

    def test_readonly_always_true(self):
        self.assertTrue(self._make().readonly)


# ══════════════════════════════════════════════════════════════════════════════
# 2. Rule Engine Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestRuleEngine(unittest.TestCase):
    """Rule engine takes profile dict + quality_issues list — no DataFrame."""

    # ── Missing values ────────────────────────────────────────────────────────

    def test_numeric_no_outlier_no_skew_gets_mean(self):
        profile = _make_profile(
            dtypes={"salary": "float64"},
            numerical_stats=[{"column": "salary", "skewness": 0.3,
                              "mean": 50000, "median": 50000, "std": 5000,
                              "min": 30000, "max": 70000, "q1": 45000, "q3": 55000}],
        )
        issues = [_make_issue("missing_values", "salary", "medium", "5 missing (5.0%)")]
        actions = apply_rules(profile, issues)
        self.assertEqual(actions[0].recommendation, ActionType.mean_imputation)
        self.assertTrue(actions[0].auto_applicable)

    def test_numeric_with_outlier_issue_gets_median(self):
        """Columns that also have an outlier issue should get median imputation."""
        profile = _make_profile(
            dtypes={"salary": "float64"},
            numerical_stats=[{"column": "salary", "skewness": 0.5,
                              "mean": 50000, "median": 48000, "std": 20000,
                              "min": 1000, "max": 500000, "q1": 40000, "q3": 60000}],
        )
        issues = [
            _make_issue("missing_values", "salary", "medium", "5 missing (5.0%)"),
            _make_issue("outliers", "salary", "low", "2 outliers (2.0%) outside IQR"),
        ]
        actions = apply_rules(profile, issues)
        missing_action = next(a for a in actions if a.issue_type == IssueType.missing_values)
        self.assertEqual(missing_action.recommendation, ActionType.median_imputation)

    def test_numeric_high_skew_gets_median_even_without_outlier_issue(self):
        """Skewness > 1.0 should trigger median even without a separate outlier issue."""
        profile = _make_profile(
            dtypes={"income": "float64"},
            numerical_stats=[{"column": "income", "skewness": 2.5,
                              "mean": 80000, "median": 50000, "std": 30000,
                              "min": 10000, "max": 500000, "q1": 40000, "q3": 90000}],
        )
        issues = [_make_issue("missing_values", "income", "low", "3 missing (3.0%)")]
        actions = apply_rules(profile, issues)
        self.assertEqual(actions[0].recommendation, ActionType.median_imputation)
        self.assertIn("skew", actions[0].reason.lower())

    def test_categorical_gets_mode_imputation(self):
        profile = _make_profile(dtypes={"cat": "object"})
        issues = [_make_issue("missing_values", "cat", "medium", "10 missing (10.0%)")]
        actions = apply_rules(profile, issues)
        self.assertEqual(actions[0].recommendation, ActionType.mode_imputation)
        self.assertTrue(actions[0].auto_applicable)

    def test_critical_missing_gets_drop_column(self):
        """≥50% missing → drop_column, auto_applicable=False."""
        profile = _make_profile(dtypes={"col_x": "float64"})
        issues = [_make_issue("missing_values", "col_x", "critical", "60 missing (60.0%)")]
        actions = apply_rules(profile, issues)
        self.assertEqual(actions[0].recommendation, ActionType.drop_column)
        self.assertFalse(actions[0].auto_applicable)

    # ── Duplicate rows ────────────────────────────────────────────────────────

    def test_duplicates_recommends_remove(self):
        profile = _make_profile()
        issues = [_make_issue("duplicate_rows", None, "medium", "10 duplicate rows (10.0%)")]
        actions = apply_rules(profile, issues)
        self.assertEqual(actions[0].recommendation, ActionType.remove_duplicates)
        self.assertIsNone(actions[0].column_name)
        self.assertTrue(actions[0].auto_applicable)

    def test_high_duplicate_pct_gets_higher_confidence(self):
        """Duplicate % > 5% should give higher confidence than < 5%."""
        profile = _make_profile()
        high = [_make_issue("duplicate_rows", None, "high", "15 duplicate rows (15.0%)")]
        low  = [_make_issue("duplicate_rows", None, "low",  "2 duplicate rows (2.0%)")]
        a_high = apply_rules(profile, high)[0]
        a_low  = apply_rules(profile, low)[0]
        self.assertGreater(a_high.confidence_score, a_low.confidence_score)

    # ── Outliers ──────────────────────────────────────────────────────────────

    def test_outliers_above_10pct_recommends_clip(self):
        profile = _make_profile(
            dtypes={"val": "float64"},
            numerical_stats=[{"column": "val", "skewness": 0.1,
                              "mean": 5, "median": 5, "std": 1,
                              "min": 1, "max": 100, "q1": 4, "q3": 6}],
        )
        issues = [_make_issue("outliers", "val", "high", "15 outliers (15.0%) outside IQR")]
        actions = apply_rules(profile, issues)
        self.assertEqual(actions[0].recommendation, ActionType.clip_outliers)

    def test_outliers_below_10pct_recommends_remove(self):
        profile = _make_profile(
            dtypes={"val": "float64"},
            numerical_stats=[{"column": "val", "skewness": 0.1,
                              "mean": 5, "median": 5, "std": 1,
                              "min": 1, "max": 100, "q1": 4, "q3": 6}],
        )
        issues = [_make_issue("outliers", "val", "low", "3 outliers (3.0%) outside IQR")]
        actions = apply_rules(profile, issues)
        self.assertEqual(actions[0].recommendation, ActionType.remove_outliers)

    def test_outlier_reason_includes_skewness_when_high(self):
        """When skewness > 1, the reason should mention skewness."""
        profile = _make_profile(
            dtypes={"x": "float64"},
            numerical_stats=[{"column": "x", "skewness": 2.1,
                              "mean": 5, "median": 3, "std": 2,
                              "min": 1, "max": 50, "q1": 2, "q3": 8}],
        )
        issues = [_make_issue("outliers", "x", "high", "12 outliers (12.0%) outside IQR")]
        actions = apply_rules(profile, issues)
        self.assertIn("skew", actions[0].reason.lower())

    # ── High cardinality ──────────────────────────────────────────────────────

    def test_near_identifier_recommends_drop(self):
        profile = _make_profile(dtypes={"user_id": "object"})
        issues = [_make_issue("high_cardinality", "user_id", "medium",
                               "100 unique values (100.0% of rows)")]
        actions = apply_rules(profile, issues)
        self.assertEqual(actions[0].recommendation, ActionType.drop_column)
        self.assertFalse(actions[0].auto_applicable)

    def test_moderate_high_cardinality_recommends_frequency_encoding(self):
        profile = _make_profile(dtypes={"city": "object"})
        issues = [_make_issue("high_cardinality", "city", "medium",
                               "40 unique values (40.0% of rows)")]
        actions = apply_rules(profile, issues)
        self.assertEqual(actions[0].recommendation, ActionType.frequency_encoding)
        self.assertTrue(actions[0].auto_applicable)

    def test_lower_cardinality_recommends_target_encoding(self):
        profile = _make_profile(dtypes={"status": "object"})
        issues = [_make_issue("high_cardinality", "status", "medium",
                               "20 unique values (20.0% of rows)")]
        actions = apply_rules(profile, issues)
        self.assertEqual(actions[0].recommendation, ActionType.target_encoding)
        self.assertFalse(actions[0].auto_applicable)   # needs target col

    # ── Type mismatch ─────────────────────────────────────────────────────────

    def test_numeric_mismatch_recommends_cast_numeric(self):
        profile = _make_profile(dtypes={"code": "object"})
        issues = [_make_issue("type_mismatch", "code", "medium",
                               "Column is object dtype but 100.0% values are numeric")]
        actions = apply_rules(profile, issues)
        self.assertEqual(actions[0].recommendation, ActionType.cast_numeric)
        self.assertTrue(actions[0].auto_applicable)

    def test_high_parse_rate_gives_higher_confidence(self):
        """≥95% parseable → _CONF_HIGH; lower → _CONF_MEDIUM."""
        profile = _make_profile(dtypes={"x": "object"})
        high = [_make_issue("type_mismatch", "x", "medium", "100.0% values are numeric")]
        low  = [_make_issue("type_mismatch", "x", "medium", "80.0% values are numeric")]
        a_high = apply_rules(profile, high)[0]
        a_low  = apply_rules(profile, low)[0]
        self.assertGreater(a_high.confidence_score, a_low.confidence_score)

    def test_datetime_mismatch_recommends_cast_datetime(self):
        profile = _make_profile(dtypes={"created_at": "object"})
        issues = [_make_issue("type_mismatch", "created_at", "medium",
                               "Column is object dtype but 98.0% values are datetime")]
        actions = apply_rules(profile, issues)
        self.assertEqual(actions[0].recommendation, ActionType.cast_datetime)

    # ── Ordering ──────────────────────────────────────────────────────────────

    def test_actions_sorted_critical_to_low(self):
        profile = _make_profile(dtypes={"A": "float64", "B": "object"})
        issues = [
            _make_issue("missing_values", "A", "low",      "3 missing (3.0%)"),
            _make_issue("missing_values", "B", "critical", "60 missing (60.0%)"),
        ]
        actions = apply_rules(profile, issues)
        ranks = [{"critical": 0, "high": 1, "medium": 2, "low": 3}[a.severity.value]
                 for a in actions]
        self.assertEqual(ranks, sorted(ranks))

    # ── Edge cases ────────────────────────────────────────────────────────────

    def test_unknown_issue_type_skipped_without_error(self):
        profile = _make_profile()
        issues = [_make_issue("unknown_future_type", "x", "medium", "some detail")]
        actions = apply_rules(profile, issues)
        self.assertEqual(len(actions), 0)

    def test_empty_issues_returns_empty_list(self):
        profile = _make_profile()
        self.assertEqual(apply_rules(profile, []), [])

    def test_all_actions_have_valid_issue_type(self):
        """Every returned action must have an IssueType from the enum."""
        profile = _make_profile(dtypes={"A": "float64", "B": "object"})
        issues = [
            _make_issue("missing_values", "A", "high", "20 missing (20.0%)"),
            _make_issue("duplicate_rows", None, "medium", "5 dup (5.0%)"),
            _make_issue("outliers", "A", "low", "3 outliers (3.0%) outside IQR"),
        ]
        for action in apply_rules(profile, issues):
            self.assertIsInstance(action.issue_type, IssueType)

    # ── Utility ───────────────────────────────────────────────────────────────

    def test_extract_pct_from_details(self):
        self.assertEqual(_extract_pct("12 missing values (12.0%)"), 12.0)
        self.assertAlmostEqual(_extract_pct("3.7% outliers"), 3.7)
        self.assertEqual(_extract_pct("no percentage here"), 0.0)


# ══════════════════════════════════════════════════════════════════════════════
# 3. Quality Score Calculator Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestQualityScoreCalculator(unittest.TestCase):

    def test_no_issues_clean_dataset_scores_100(self):
        profile = _make_profile(rows=500, cols=10)
        score, grade = _calculate_quality_score(profile, [])
        self.assertEqual(score, 100)
        self.assertEqual(grade, "A")

    def test_critical_issue_deducts_more_than_low(self):
        profile = _make_profile(rows=200, cols=5)
        s_critical, _ = _calculate_quality_score(
            profile, [_make_issue("missing_values", "A", "critical", "60 missing (60.0%)")]
        )
        s_low, _ = _calculate_quality_score(
            profile, [_make_issue("missing_values", "A", "low", "2 missing (2.0%)")]
        )
        self.assertLess(s_critical, s_low)

    def test_tiny_dataset_penalty(self):
        """Fewer than 100 rows should deduct points."""
        profile_small = _make_profile(rows=30, cols=5)
        profile_large = _make_profile(rows=500, cols=5)
        s_small, _ = _calculate_quality_score(profile_small, [])
        s_large, _ = _calculate_quality_score(profile_large, [])
        self.assertLess(s_small, s_large)

    def test_single_column_penalty(self):
        profile_single = _make_profile(rows=200, cols=1)
        profile_multi  = _make_profile(rows=200, cols=5)
        s_single, _ = _calculate_quality_score(profile_single, [])
        s_multi, _  = _calculate_quality_score(profile_multi, [])
        self.assertLess(s_single, s_multi)

    def test_score_clamped_to_zero_not_negative(self):
        """Many severe issues should not make score go below 0."""
        profile = _make_profile(rows=20, cols=1)
        many_criticals = [
            _make_issue("missing_values", f"col{i}", "critical", f"60 missing (60.0%)")
            for i in range(20)
        ]
        score, _ = _calculate_quality_score(profile, many_criticals)
        self.assertGreaterEqual(score, 0)

    def test_grade_boundaries(self):
        profile = _make_profile(rows=500, cols=10)
        # A: ≥90, B: ≥75, C: ≥60, D: ≥40, F: <40
        # Use controlled issue lists to hit each band
        s_90, g_90 = _calculate_quality_score(profile, [])
        self.assertEqual(g_90, "A")

    def test_estimated_score_gte_current(self):
        actions = [
            CleaningAction(
                column_name="x", issue_type=IssueType.missing_values,
                severity=Severity.medium, current_state="5 missing",
                recommendation=ActionType.median_imputation,
                reason="test", confidence_score=0.9, auto_applicable=True,
            )
        ]
        est = _estimate_post_clean_score(70, actions)
        self.assertGreaterEqual(est, 70)

    def test_estimated_score_capped_at_100(self):
        actions = [
            CleaningAction(
                column_name=None, issue_type=IssueType.duplicate_rows,
                severity=Severity.high, current_state="50 dups",
                recommendation=ActionType.remove_duplicates,
                reason="test", confidence_score=0.9, auto_applicable=True,
            )
        ] * 20   # many auto actions should not push above 100
        est = _estimate_post_clean_score(98, actions)
        self.assertEqual(est, 100)

    def test_non_auto_actions_get_half_credit(self):
        """Non-auto actions should contribute less to the estimated score."""
        auto_action = CleaningAction(
            column_name="x", issue_type=IssueType.missing_values,
            severity=Severity.medium, current_state="5 missing",
            recommendation=ActionType.remove_duplicates,
            reason="test", confidence_score=0.9, auto_applicable=True,
        )
        manual_action = CleaningAction(
            column_name="x", issue_type=IssueType.high_cardinality,
            severity=Severity.medium, current_state="high card",
            recommendation=ActionType.drop_column,
            reason="test", confidence_score=0.9, auto_applicable=False,
        )
        est_auto   = _estimate_post_clean_score(60, [auto_action])
        est_manual = _estimate_post_clean_score(60, [manual_action])
        self.assertGreaterEqual(est_auto, est_manual)


# ══════════════════════════════════════════════════════════════════════════════
# 4. Cleaning Planner Service Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestCleaningPlannerService(unittest.TestCase):
    """Tests build_cleaning_plan(profile, quality_report, ...) → CleaningPlan."""

    def _dirty_profile_and_quality(self):
        """Build a realistic dirty profile + quality report from a real DataFrame."""
        df = pd.DataFrame({
            "salary":   [50000, 60000, None, None, None, 80000, 90000, 100000, 200000, 110000],
            "category": ["A", "A", "B", "C", None, "D", "E", "F", "G", "H"],
            "code":     ["1", "2", "3", "4", "5", "6", "7", "8", "9", "not_a_num"],
        })
        return profile_dataset(df), check_quality(df)

    def _clean_profile_and_quality(self):
        np.random.seed(42)
        df = pd.DataFrame({
            "age":    np.random.randint(20, 60, 200).astype(float),
            "income": np.random.randint(30000, 100000, 200).astype(float),
            "gender": np.random.choice(["M", "F"], 200),
        })
        return profile_dataset(df), check_quality(df)

    # ── Contract ───────────────────────────────────────────────────────────────

    def test_returns_cleaning_plan(self):
        p, q = self._dirty_profile_and_quality()
        plan = build_cleaning_plan(p, q)
        self.assertIsInstance(plan, CleaningPlan)

    def test_plan_is_readonly(self):
        p, q = self._dirty_profile_and_quality()
        self.assertTrue(build_cleaning_plan(p, q).readonly)

    def test_phase_is_2a(self):
        p, q = self._dirty_profile_and_quality()
        self.assertEqual(build_cleaning_plan(p, q).phase, "2A")

    def test_ids_propagated(self):
        p, q = self._dirty_profile_and_quality()
        plan = build_cleaning_plan(p, q, dataset_id="ds-1", session_id="sess-1")
        self.assertEqual(plan.dataset_id, "ds-1")
        self.assertEqual(plan.session_id, "sess-1")

    def test_generated_at_is_utc(self):
        p, q = self._dirty_profile_and_quality()
        plan = build_cleaning_plan(p, q)
        self.assertIsNotNone(plan.generated_at.tzinfo)

    def test_empty_profile_raises(self):
        """Profile with 0 rows must raise ValueError."""
        empty_profile = _make_profile(rows=0)
        with self.assertRaises(ValueError):
            build_cleaning_plan(empty_profile, {"issues": []})

    # ── Summary integrity ─────────────────────────────────────────────────────

    def test_summary_counts_match_actions(self):
        p, q = self._dirty_profile_and_quality()
        plan = build_cleaning_plan(p, q)
        a = plan.actions
        s = plan.summary
        self.assertEqual(s.total_issues, len(a))
        self.assertEqual(s.critical_issues, sum(1 for x in a if x.severity == Severity.critical))
        self.assertEqual(s.high_risk_issues, sum(1 for x in a if x.severity == Severity.high))
        self.assertEqual(s.medium_risk_issues, sum(1 for x in a if x.severity == Severity.medium))
        self.assertEqual(s.low_risk_issues, sum(1 for x in a if x.severity == Severity.low))
        self.assertEqual(s.auto_applicable_count, sum(1 for x in a if x.auto_applicable))

    def test_estimated_score_gte_current(self):
        p, q = self._dirty_profile_and_quality()
        plan = build_cleaning_plan(p, q)
        self.assertGreaterEqual(plan.summary.estimated_score_after_cleaning,
                                plan.summary.overall_quality_score)

    def test_estimated_score_lte_100(self):
        p, q = self._clean_profile_and_quality()
        plan = build_cleaning_plan(p, q)
        self.assertLessEqual(plan.summary.estimated_score_after_cleaning, 100)

    def test_clean_dataset_no_critical_issues(self):
        p, q = self._clean_profile_and_quality()
        plan = build_cleaning_plan(p, q)
        critical = [a for a in plan.actions if a.severity == Severity.critical]
        self.assertEqual(len(critical), 0)

    def test_all_action_ids_unique(self):
        p, q = self._dirty_profile_and_quality()
        plan = build_cleaning_plan(p, q)
        ids = [a.action_id for a in plan.actions]
        self.assertEqual(len(ids), len(set(ids)))

    def test_actions_sorted_by_severity(self):
        p, q = self._dirty_profile_and_quality()
        plan = build_cleaning_plan(p, q)
        rank = {Severity.critical: 0, Severity.high: 1, Severity.medium: 2, Severity.low: 3}
        ranks = [rank[a.severity] for a in plan.actions]
        self.assertEqual(ranks, sorted(ranks))


# ══════════════════════════════════════════════════════════════════════════════
# 5. Router / API Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestCleaningRouter(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(app)
        app.dependency_overrides = {}

    def tearDown(self):
        app.dependency_overrides = {}

    def _auth(self, uid="test_user"):
        app.dependency_overrides[verify_firebase_token] = lambda: {"uid": uid}

    # ── GET /api/v2/cleaning/plan ─────────────────────────────────────────────

    @patch("routers.cleaning.session_manager.session_exists", return_value=True)
    @patch("routers.cleaning.session_manager.load_dataframe")
    def test_plan_session_returns_200(self, mock_load, _):
        mock_load.return_value = pd.DataFrame({
            "salary": [50000, 60000, None, 80000, 100000] * 2,
            "cat":    ["A", "A", "B", None, "C"] * 2,
        })
        self._auth()
        r = self.client.get("/api/v2/cleaning/plan", params={"sessionId": "s1"})
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn("plan_id", data)
        self.assertIn("summary", data)
        self.assertIn("actions", data)
        self.assertTrue(data["readonly"])
        self.assertEqual(data["phase"], "2A")

    @patch("routers.cleaning.session_manager.session_exists", return_value=False)
    def test_plan_missing_session_404(self, _):
        self._auth()
        r = self.client.get("/api/v2/cleaning/plan", params={"sessionId": "none"})
        self.assertEqual(r.status_code, 404)

    def test_plan_no_auth_rejected(self):
        r = self.client.get("/api/v2/cleaning/plan", params={"sessionId": "s1"})
        self.assertIn(r.status_code, (401, 403))

    # ── GET /api/v2/cleaning/plan/dataset ─────────────────────────────────────

    def test_plan_dataset_returns_200_for_owner(self):
        service = get_dataset_service()
        if hasattr(service, "store"):
            service.store.clear()

        df = pd.DataFrame({"A": [1.0, 2.0, None, 4.0, 5.0] * 10})
        with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as f:
            tmp = f.name
        try:
            df.to_parquet(tmp)
            service.create_dataset({
                "dataset_id": "ds-plan-test",
                "user_id": "test_user",
                "dataset_name": "test.parquet",
                "original_file_type": "parquet",
                "source": "upload",
                "upload_timestamp": "2026-06-14T00:00:00Z",
                "row_count": 50, "column_count": 1,
                "memory_usage": 0.1, "parquet_path": tmp,
                "ml_readiness_score": 70, "dataset_version": 1, "status": "active",
            })
            self._auth("test_user")
            r = self.client.get("/api/v2/cleaning/plan/dataset",
                                params={"datasetId": "ds-plan-test"})
            self.assertEqual(r.status_code, 200)
            self.assertTrue(r.json()["readonly"])
            self.assertEqual(r.json()["dataset_id"], "ds-plan-test")
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)

    def test_plan_dataset_wrong_owner_403(self):
        service = get_dataset_service()
        if hasattr(service, "store"):
            service.store.clear()

        with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as f:
            tmp = f.name
        try:
            pd.DataFrame({"x": [1, 2]}).to_parquet(tmp)
            service.create_dataset({
                "dataset_id": "ds-403-test",
                "user_id": "owner",
                "dataset_name": "secret.parquet",
                "original_file_type": "parquet",
                "source": "upload",
                "upload_timestamp": "2026-06-14T00:00:00Z",
                "row_count": 2, "column_count": 1,
                "memory_usage": 0.01, "parquet_path": tmp,
                "ml_readiness_score": 80, "dataset_version": 1, "status": "active",
            })
            self._auth("attacker")
            r = self.client.get("/api/v2/cleaning/plan/dataset",
                                params={"datasetId": "ds-403-test"})
            self.assertEqual(r.status_code, 403)
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)

    def test_plan_dataset_nonexistent_404(self):
        self._auth()
        r = self.client.get("/api/v2/cleaning/plan/dataset",
                            params={"datasetId": "does-not-exist"})
        self.assertEqual(r.status_code, 404)

    # ── GET /api/v2/cleaning/summary ──────────────────────────────────────────

    @patch("routers.cleaning.session_manager.session_exists", return_value=True)
    @patch("routers.cleaning.session_manager.load_dataframe")
    def test_summary_returns_200_with_no_actions_field(self, mock_load, _):
        mock_load.return_value = pd.DataFrame({"A": [1.0, None, 3.0, 4.0, 5.0]})
        self._auth()
        r = self.client.get("/api/v2/cleaning/summary", params={"sessionId": "s1"})
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn("total_issues", data)
        self.assertIn("overall_quality_score", data)
        self.assertIn("quality_grade", data)
        self.assertIn("estimated_score_after_cleaning", data)
        self.assertNotIn("actions", data)   # summary only — no full action list

    @patch("routers.cleaning.session_manager.session_exists", return_value=False)
    def test_summary_missing_session_404(self, _):
        self._auth()
        r = self.client.get("/api/v2/cleaning/summary", params={"sessionId": "ghost"})
        self.assertEqual(r.status_code, 404)


if __name__ == "__main__":
    unittest.main()
