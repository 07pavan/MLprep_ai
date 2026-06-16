"""Cleaning Planner Service — pure functional transformation of profiling data into a plan.

Phase 2A contract: This service NEVER touches a DataFrame.
It is a pure function: (profile_dict, quality_dict) → CleaningPlan.

Input contract:
    profile:        dict returned by profile_dataset()
    quality_report: dict returned by check_quality()

Responsibilities:
    1. Execute rule engine checks (issue → CleaningAction mapping)
    2. Combine all issues into an ordered action list
    3. Calculate overall dataset quality score (with grade)
    4. Assign severity levels: critical / high / medium / low
    5. Calculate confidence scores per action
    6. Estimate post-cleaning quality score improvement
    7. Assemble and return a validated CleaningPlan

The router is responsible for all DataFrame I/O, profiling, and quality scanning.
This service is intentionally decoupled from any I/O or pandas operations.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from services.rule_engine import apply_rules
from schemas.cleaning_plan import (
    ActionType,
    CleaningAction,
    CleaningPlan,
    CleaningSummary,
    Severity,
)

logger = logging.getLogger(__name__)


# ── Score improvement table ────────────────────────────────────────────────────
# Conservative per-action ML readiness score delta.
# Auto-applicable actions receive full credit; manual-review actions receive half.
_SCORE_DELTA: dict[ActionType, int] = {
    ActionType.mean_imputation:       4,
    ActionType.median_imputation:     4,
    ActionType.mode_imputation:       3,
    ActionType.constant_imputation:   2,
    ActionType.drop_column:           3,   # half-credit (manual)
    ActionType.remove_duplicates:     8,
    ActionType.clip_outliers:         3,
    ActionType.remove_outliers:       4,
    ActionType.target_encoding:       3,   # half-credit (manual)
    ActionType.frequency_encoding:    3,
    ActionType.cast_numeric:          3,
    ActionType.cast_datetime:         2,
    ActionType.log_transform:         2,
    ActionType.no_action:             0,
    ActionType.drop_constant:         4,   # half-credit (manual — verify not an error)
    ActionType.validate_emails:       2,   # half-credit (manual — domain rules needed)
}

# ── Quality scoring weights ────────────────────────────────────────────────────
# Severity → maximum point deduction toward the overall quality score.
# The scoring baseline is 100; deductions are summed and clamped at 0.
_SEVERITY_DEDUCTION: dict[str, int] = {
    "critical": 20,
    "high":     10,
    "medium":    5,
    "low":       2,
}

_GRADE_BANDS = [(90, "A"), (75, "B"), (60, "C"), (40, "D"), (0, "F")]


# ── Public API ────────────────────────────────────────────────────────────────

def build_cleaning_plan(
    profile: dict[str, Any],
    quality_report: dict[str, Any],
    *,
    dataset_id: Optional[str] = None,
    session_id: Optional[str] = None,
) -> CleaningPlan:
    """Generate a complete, read-only CleaningPlan from structured analysis dicts.

    Args:
        profile:        Output of ``profile_dataset()`` — structural metadata
                        including row/column counts, dtypes, missing value stats,
                        duplicate counts, and numerical statistics.
        quality_report: Output of ``check_quality()`` — list of detected issues
                        with type, severity, column, and detail strings.
        dataset_id:     Dataset registry ID (if dataset is registered).
        session_id:     Upload session ID (if plan is for a live session).

    Returns:
        A fully-validated CleaningPlan with summary and ordered action list.

    Raises:
        ValueError: If the profile indicates an empty dataset (0 rows).
    """
    rows = profile.get("rows", 0)
    cols = profile.get("columns", 0)

    if rows == 0:
        raise ValueError(
            "Cannot build a cleaning plan for an empty dataset (0 rows in profile)."
        )

    quality_issues: list[dict[str, Any]] = quality_report.get("issues", [])

    logger.info(
        "Cleaning planner: building plan for %d-row × %d-col dataset, %d issues detected",
        rows, cols, len(quality_issues),
    )

    # ── Step 1: Execute rule engine ────────────────────────────────────────────
    actions: list[CleaningAction] = apply_rules(profile, quality_issues)
    logger.info("Cleaning planner: rule engine produced %d actions", len(actions))

    # ── Step 2: Severity assignment is done inside apply_rules/rule functions ──
    #    (each CleaningAction.severity is set from the quality_issue["severity"])

    # ── Step 3: Calculate overall dataset quality score ────────────────────────
    current_score, quality_grade = _calculate_quality_score(profile, quality_issues)
    logger.info(
        "Cleaning planner: quality score = %d (%s)", current_score, quality_grade
    )

    # ── Step 4 & 5: Severity + confidence are already embedded in CleaningAction
    #    objects by the rule engine. Summarise them here.

    # ── Step 6: Estimate post-cleaning score ───────────────────────────────────
    estimated_score = _estimate_post_clean_score(current_score, actions)

    # ── Step 7: Assemble CleaningPlan ─────────────────────────────────────────
    summary = _build_summary(
        actions=actions,
        current_score=current_score,
        quality_grade=quality_grade,
        estimated_score=estimated_score,
    )

    plan = CleaningPlan(
        dataset_id=dataset_id,
        session_id=session_id,
        summary=summary,
        actions=actions,
    )

    logger.info(
        "Cleaning planner: plan ready — %d actions, score %d → %d (%s), phase=%s",
        len(actions), current_score, estimated_score, quality_grade, plan.phase,
    )
    return plan


# ── Quality Score Calculator ──────────────────────────────────────────────────

def _calculate_quality_score(
    profile: dict[str, Any],
    quality_issues: list[dict[str, Any]],
) -> tuple[int, str]:
    """Derive an overall dataset quality score (0–100) from profile + issues.

    Scoring methodology:
        Start at 100. Apply deductions per issue based on severity.
        Apply structural deductions for tiny datasets and single-column datasets.
        Clamp at [0, 100]. Map to letter grade.

    Returns:
        (score: int, grade: str) — e.g. (72, "C")
    """
    score = 100

    # ── Issue-based deductions ─────────────────────────────────────────────────
    for issue in quality_issues:
        severity = issue.get("severity", "low")
        deduction = _SEVERITY_DEDUCTION.get(severity, 2)

        # Extra deduction for critical missing values (column mostly empty)
        if issue.get("type") == "missing_values":
            from services.rule_engine import _extract_pct
            pct = _extract_pct(issue.get("details", ""))
            if pct >= 50.0:
                deduction = max(deduction, 20)   # override to maximum

        score -= deduction

    # ── Structural deductions ─────────────────────────────────────────────────
    rows = profile.get("rows", 0)
    cols = profile.get("columns", 0)

    if rows < 50:
        score -= 25
    elif rows < 100:
        score -= 15

    if cols <= 1:
        score -= 20

    # ── Clamp and grade ───────────────────────────────────────────────────────
    score = max(0, min(100, score))
    grade = "F"
    for threshold, letter in _GRADE_BANDS:
        if score >= threshold:
            grade = letter
            break

    return score, grade


# ── Estimate Score After Cleaning ────────────────────────────────────────────

def _estimate_post_clean_score(
    current_score: int,
    actions: list[CleaningAction],
) -> int:
    """Conservative estimate of quality score after all recommended actions.

    Rules:
        - Auto-applicable actions receive their full delta.
        - Non-auto actions (require user review) receive half delta.
        - Final score is capped at 100.
    """
    delta = 0
    for action in actions:
        base = _SCORE_DELTA.get(action.recommendation, 0)
        if action.auto_applicable:
            delta += base
        else:
            delta += base // 2   # conservative — requires human decision

    return min(100, current_score + delta)


# ── Summary Builder ───────────────────────────────────────────────────────────

def _build_summary(
    actions: list[CleaningAction],
    current_score: int,
    quality_grade: str,
    estimated_score: int,
) -> CleaningSummary:
    """Aggregate action counts by severity and build CleaningSummary."""
    return CleaningSummary(
        total_issues=len(actions),
        critical_issues=sum(1 for a in actions if a.severity == Severity.critical),
        high_risk_issues=sum(1 for a in actions if a.severity == Severity.high),
        medium_risk_issues=sum(1 for a in actions if a.severity == Severity.medium),
        low_risk_issues=sum(1 for a in actions if a.severity == Severity.low),
        auto_applicable_count=sum(1 for a in actions if a.auto_applicable),
        overall_quality_score=current_score,
        quality_grade=quality_grade,
        estimated_score_after_cleaning=estimated_score,
    )
