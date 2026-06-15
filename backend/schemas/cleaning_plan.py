"""Cleaning Plan Pydantic schemas — production-grade, read-only planning contracts.

These schemas define the data contract for Phase 2A.
IMPORTANT: Phase 2A ONLY generates plans. No dataset mutation occurs here.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


# ── Enumerations ──────────────────────────────────────────────────────────────

class IssueType(str, Enum):
    """Canonical issue type identifiers produced by the quality scanner."""
    missing_values      = "missing_values"
    duplicate_rows      = "duplicate_rows"
    outliers            = "outliers"
    high_cardinality    = "high_cardinality"
    type_mismatch       = "type_mismatch"
    low_variance        = "low_variance"
    skewed_distribution = "skewed_distribution"
    constant_column     = "constant_column"   # added for zero-variance columns
    invalid_emails      = "invalid_emails"     # added for malformed email detection


class Severity(str, Enum):
    """Risk level of an identified data issue."""
    critical = "critical"
    high     = "high"
    medium   = "medium"
    low      = "low"


class ActionType(str, Enum):
    """Recommended remediation action for a data issue."""
    mean_imputation       = "mean_imputation"
    median_imputation     = "median_imputation"
    mode_imputation       = "mode_imputation"
    constant_imputation   = "constant_imputation"
    drop_column           = "drop_column"
    remove_duplicates     = "remove_duplicates"
    clip_outliers         = "clip_outliers"
    remove_outliers       = "remove_outliers"
    target_encoding       = "target_encoding"
    frequency_encoding    = "frequency_encoding"
    cast_numeric          = "cast_numeric"
    cast_datetime         = "cast_datetime"
    log_transform         = "log_transform"
    no_action             = "no_action"
    drop_constant         = "drop_constant"    # added for constant/zero-variance columns
    validate_emails       = "validate_emails"  # added for malformed email cleanup


# ── Core Action Model ─────────────────────────────────────────────────────────

class CleaningAction(BaseModel):
    """A single, atomic recommended cleaning action for one data issue.

    Phase 2A guarantees this is purely advisory — no data is altered.
    """
    action_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique identifier for this action within the plan.",
    )
    column_name: Optional[str] = Field(
        default=None,
        description="Target column name. None for dataset-level actions (e.g. duplicates).",
    )
    issue_type: IssueType = Field(
        description="Categorised type of the detected data issue.",
    )
    severity: Severity = Field(
        description="Risk level of this issue for downstream ML training.",
    )
    current_state: str = Field(
        description="Human-readable description of the issue as found in the data.",
        examples=["42 missing values (8.4% of rows)"],
    )
    recommendation: ActionType = Field(
        description="Recommended remediation action to resolve the issue.",
    )
    reason: str = Field(
        description="Clear, plain-language explanation of why this action is recommended.",
        examples=["Numerical column with outliers — median is more robust than mean."],
    )
    confidence_score: float = Field(
        ge=0.0, le=1.0,
        description="Model confidence that this recommendation is appropriate (0–1).",
        examples=[0.92],
    )
    auto_applicable: bool = Field(
        description=(
            "True when the action can be applied automatically without domain expertise. "
            "False requires manual review (e.g. drop_column, target_encoding)."
        ),
    )

    @field_validator("confidence_score")
    @classmethod
    def round_confidence(cls, v: float) -> float:
        return round(v, 4)


# ── Summary Model ─────────────────────────────────────────────────────────────

class CleaningSummary(BaseModel):
    """Aggregate statistics for a cleaning plan."""
    total_issues: int = Field(
        ge=0,
        description="Total number of detected data issues across all columns.",
    )
    critical_issues: int = Field(
        ge=0,
        description="Count of critical-severity issues requiring immediate attention.",
    )
    high_risk_issues: int = Field(
        ge=0,
        description="Count of high-severity issues that will significantly harm ML performance.",
    )
    medium_risk_issues: int = Field(
        ge=0,
        description="Count of medium-severity issues with moderate impact.",
    )
    low_risk_issues: int = Field(
        ge=0,
        description="Count of low-severity issues that are minor or cosmetic.",
    )
    auto_applicable_count: int = Field(
        ge=0,
        description="Number of actions that can be applied automatically without review.",
    )
    overall_quality_score: int = Field(
        ge=0, le=100,
        description=(
            "Composite dataset quality score (0–100). "
            "100 = perfect, 0 = severely degraded. "
            "Computed from current ML readiness scoring engine."
        ),
    )
    quality_grade: str = Field(
        description="Letter grade derived from quality score: A (≥90), B (≥75), C (≥60), D (≥40), F (<40).",
        examples=["B"],
    )
    estimated_score_after_cleaning: int = Field(
        ge=0, le=100,
        description=(
            "Estimated ML readiness score if all recommended actions are applied. "
            "Computed conservatively by the rule engine."
        ),
    )


# ── Top-Level Plan ────────────────────────────────────────────────────────────

class CleaningPlan(BaseModel):
    """A complete, read-only intelligent cleaning plan for one dataset.

    Phase 2A contract: this object MUST NEVER be used to mutate data.
    Cleaning execution is reserved for Phase 2B.
    """
    plan_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique identifier for this plan instance.",
    )
    dataset_id: Optional[str] = Field(
        default=None,
        description="Registry dataset ID (if the dataset is registered). None for session-only uploads.",
    )
    session_id: Optional[str] = Field(
        default=None,
        description="Session ID when the plan is generated for a live upload session.",
    )
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp when this plan was generated.",
    )
    summary: CleaningSummary = Field(
        description="Aggregate statistics and quality scores for the plan.",
    )
    actions: list[CleaningAction] = Field(
        default_factory=list,
        description="Ordered list of recommended cleaning actions (highest severity first).",
    )
    phase: str = Field(
        default="2A",
        description="Platform phase that produced this plan.",
    )
    readonly: bool = Field(
        default=True,
        description="Always True in Phase 2A. Signals that no data modification has occurred.",
    )


# ── v1 REST API Response Models ───────────────────────────────────────────────
# Used exclusively by POST /api/v1/cleaning/plan/{dataset_id}
#                  and GET  /api/v1/cleaning/plan/{dataset_id}

class PlanStatus(str, Enum):
    """Lifecycle status of a stored cleaning plan."""
    generated = "generated"   # freshly created
    retrieved = "retrieved"   # returned from store
    not_found = "not_found"   # no plan exists for this dataset


class CleaningPlanMeta(BaseModel):
    """Lightweight plan reference returned in list responses.

    Does not include the full actions list — use the plan_id to fetch the
    complete CleaningPlan.
    """
    plan_id: str = Field(
        description="Unique plan identifier. Use as query param to fetch the full plan.",
    )
    dataset_id: str = Field(
        description="Registry dataset ID this plan was generated for.",
    )
    generated_at: datetime = Field(
        description="UTC timestamp when this plan was generated.",
    )
    total_issues: int = Field(
        ge=0,
        description="Total number of detected issues.",
    )
    overall_quality_score: int = Field(
        ge=0, le=100,
        description="Dataset quality score at the time of plan generation (0–100).",
    )
    quality_grade: str = Field(
        description="Letter grade: A (≥90) · B (≥75) · C (≥60) · D (≥40) · F (<40).",
        examples=["C"],
    )
    estimated_score_after_cleaning: int = Field(
        ge=0, le=100,
        description="Estimated quality score if all recommended actions are applied.",
    )
    auto_applicable_count: int = Field(
        ge=0,
        description="Number of actions that can be applied automatically.",
    )
    readonly: bool = Field(
        default=True,
        description="Always True in Phase 2A.",
    )

    @classmethod
    def from_plan(cls, plan: "CleaningPlan") -> "CleaningPlanMeta":
        """Build a lightweight CleaningPlanMeta from a full CleaningPlan."""
        return cls(
            plan_id=plan.plan_id,
            dataset_id=plan.dataset_id or "",
            generated_at=plan.generated_at,
            total_issues=plan.summary.total_issues,
            overall_quality_score=plan.summary.overall_quality_score,
            quality_grade=plan.summary.quality_grade,
            estimated_score_after_cleaning=plan.summary.estimated_score_after_cleaning,
            auto_applicable_count=plan.summary.auto_applicable_count,
            readonly=plan.readonly,
        )


class GeneratePlanResponse(BaseModel):
    """Response body for POST /api/v1/cleaning/plan/{dataset_id}.

    Returns the full CleaningPlan alongside a human-readable status message.
    HTTP status: 201 Created.
    """
    status: PlanStatus = Field(
        default=PlanStatus.generated,
        description="Outcome status of the generation request.",
    )
    message: str = Field(
        description="Human-readable summary of the generation result.",
        examples=["Cleaning plan generated successfully for dataset 'sales_data.csv'."],
    )
    dataset_id: str = Field(
        description="Registry dataset ID the plan was generated for.",
    )
    plan: CleaningPlan = Field(
        description="The fully-generated, read-only cleaning plan.",
    )


class PlanListResponse(BaseModel):
    """Response body for GET /api/v1/cleaning/plan/{dataset_id}.

    Returns all stored plans for a dataset (lightweight metadata list),
    plus the most recently generated full plan for convenience.
    """
    dataset_id: str = Field(
        description="Registry dataset ID.",
    )
    total_plans: int = Field(
        ge=0,
        description="Total number of plans stored for this dataset.",
    )
    plans: list[CleaningPlanMeta] = Field(
        default_factory=list,
        description=(
            "Lightweight plan references ordered newest-first. "
            "Use plan_id to retrieve the full plan via the detail endpoint."
        ),
    )
    latest_plan: Optional[CleaningPlan] = Field(
        default=None,
        description="Full content of the most recently generated plan. None if no plans exist.",
    )
