"""Phase 2A — v1 REST Cleaning Plan Endpoints.

Base URL: /api/v1/cleaning/plan

Endpoints:
    POST   /api/v1/cleaning/plan/{dataset_id}
        Generate a new cleaning plan from a registered dataset.
        Stores the plan in PlanStore for later retrieval.
        Returns HTTP 201 with GeneratePlanResponse.

    GET    /api/v1/cleaning/plan/{dataset_id}
        Retrieve all stored plans for a dataset.
        Optional ?plan_id=<uuid> query param to fetch one specific plan.
        Returns HTTP 200 with PlanListResponse.

    DELETE /api/v1/cleaning/plan/{dataset_id}
        Purge all stored plans for a dataset.
        Returns HTTP 200 with deletion count.

Design decisions:
    - Path param {dataset_id} is the primary resource identifier (REST convention).
    - POST always generates a fresh plan (idempotent-safe — does not overwrite old plans).
    - GET returns lightweight CleaningPlanMeta list + the latest full plan in one response,
      eliminating the need for a separate "get latest" call from the frontend.
    - All endpoints are auth-protected and ownership-checked.
    - No data is mutated — Phase 2A is read-only.

OpenAPI documentation:
    - All models have Field descriptions and examples for Swagger/Redoc.
    - Response models use distinct Pydantic classes (GeneratePlanResponse, PlanListResponse).
    - Error responses document 401, 403, 404, 422, 500 explicitly.
"""
from __future__ import annotations

import logging
import os

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from fastapi.responses import JSONResponse

from schemas.cleaning_plan import (
    CleaningPlan,
    CleaningPlanMeta,
    GeneratePlanResponse,
    PlanListResponse,
    PlanStatus,
)
from services.cleaning_planner import build_cleaning_plan
from services.dataset_service import get_dataset_service
from services.plan_store import PlanStore, get_plan_store
from tools.profiler_tool import profile_dataset
from tools.quality_tool import check_quality
from utils.auth import verify_firebase_token

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/cleaning/plan",
    tags=["Cleaning Planner v1 — Plan Management"],
)


# ── Shared helpers ────────────────────────────────────────────────────────────

def _load_dataset_meta(dataset_id: str, uid: str, service) -> dict:
    """Fetch registry metadata and enforce ownership. Raises HTTPException on failure."""
    try:
        meta = service.get_dataset(dataset_id)
    except Exception as exc:
        logger.error("Registry lookup failed for dataset %s: %s", dataset_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Registry query failed: {exc}",
        )

    if not meta:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset '{dataset_id}' not found in registry.",
        )

    if meta.get("user_id") != uid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this dataset.",
        )
    return meta


def _load_dataframe(meta: dict) -> pd.DataFrame:
    """Load the Parquet file described by registry metadata. Raises HTTPException on failure."""
    parquet_path: str = meta.get("parquet_path", "")
    if not parquet_path or not os.path.exists(parquet_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dataset file not found on disk. It may have been deleted or moved.",
        )
    try:
        return pd.read_parquet(parquet_path)
    except Exception as exc:
        logger.error("Failed to read parquet %s: %s", parquet_path, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to read dataset file: {exc}",
        )


# ── POST /api/v1/cleaning/plan/{dataset_id} ───────────────────────────────────

@router.post(
    "/{dataset_id}",
    response_model=GeneratePlanResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate a new intelligent cleaning plan for a registered dataset",
    description="""
**Phase 2A — Read-Only Plan Generation**

Analyses the dataset identified by `dataset_id` and returns a structured
intelligent cleaning plan. The plan is stored server-side and can be
retrieved later via `GET /api/v1/cleaning/plan/{dataset_id}`.

**What this endpoint does:**
1. Loads the dataset from the registry and reads its Parquet file.
2. Runs the dataset profiler (`profile_dataset`) to extract structural metadata.
3. Runs the quality scanner (`check_quality`) to detect data issues.
4. Passes both result dicts to the rule engine to produce `CleaningAction` objects.
5. Calculates the overall quality score and estimates the post-cleaning improvement.
6. Stores the plan and returns HTTP 201 with the full `CleaningPlan`.

**Important:** This endpoint **never modifies the dataset**. It is purely advisory.
Cleaning execution is reserved for Phase 2B.
    """,
    responses={
        201: {"description": "Plan generated and stored successfully."},
        401: {"description": "Missing or invalid authentication token."},
        403: {"description": "Authenticated user does not own this dataset."},
        404: {"description": "Dataset not found in registry or file not on disk."},
        422: {"description": "Dataset is empty or cannot be profiled."},
        500: {"description": "Internal error during profiling, quality check, or plan assembly."},
    },
)
async def generate_plan(
    dataset_id: str = Path(
        ...,
        description="Registry dataset ID to generate a cleaning plan for.",
        examples=["550e8400-e29b-41d4-a716-446655440000"],
    ),
    user: dict = Depends(verify_firebase_token),
    service=Depends(get_dataset_service),
    store: PlanStore = Depends(get_plan_store),
) -> GeneratePlanResponse:
    """Generate and store a new CleaningPlan for a registered dataset."""
    uid = user["uid"]

    # ── 1. Load dataset metadata + ownership check ────────────────────────────
    meta = _load_dataset_meta(dataset_id, uid, service)
    dataset_name: str = meta.get("dataset_name", dataset_id)

    # ── 2. Load DataFrame from disk ────────────────────────────────────────────
    df = _load_dataframe(meta)

    # ── 3. Profile + quality check ────────────────────────────────────────────
    try:
        profile = profile_dataset(df)
    except Exception as exc:
        logger.error("Profiling failed for dataset %s: %s", dataset_id, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Dataset profiling failed: {exc}",
        )

    try:
        quality_report = check_quality(df)
    except Exception as exc:
        logger.error("Quality check failed for dataset %s: %s", dataset_id, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Quality check failed: {exc}",
        )

    # ── 4–6. Build plan (service layer: pure function, no I/O) ────────────────
    try:
        plan: CleaningPlan = build_cleaning_plan(
            profile=profile,
            quality_report=quality_report,
            dataset_id=dataset_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    except Exception as exc:
        logger.error("Plan assembly failed for dataset %s: %s", dataset_id, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Plan generation failed: {exc}",
        )

    # ── 7. Persist plan ───────────────────────────────────────────────────────
    store.save(uid, dataset_id, plan)

    logger.info(
        "Plan %s generated for user=%s dataset=%s (%d actions, score=%d)",
        plan.plan_id, uid, dataset_id,
        plan.summary.total_issues,
        plan.summary.overall_quality_score,
    )

    return GeneratePlanResponse(
        status=PlanStatus.generated,
        message=(
            f"Cleaning plan generated successfully for dataset '{dataset_name}'. "
            f"Found {plan.summary.total_issues} issue(s) "
            f"(score: {plan.summary.overall_quality_score} → "
            f"{plan.summary.estimated_score_after_cleaning} estimated)."
        ),
        dataset_id=dataset_id,
        plan=plan,
    )


# ── GET /api/v1/cleaning/plan/{dataset_id} ────────────────────────────────────

@router.get(
    "/{dataset_id}",
    response_model=PlanListResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve previously generated cleaning plans for a dataset",
    description="""
**Phase 2A — Stored Plan Retrieval**

Returns all cleaning plans previously generated for the given `dataset_id`,
ordered newest-first.

**Response structure:**
- `plans`: lightweight `CleaningPlanMeta` list (no full action list) for efficient rendering.
- `latest_plan`: the full `CleaningPlan` for the most recently generated plan.
- `total_plans`: total number of stored plans for this dataset.

**Optional query params:**
- `?plan_id=<uuid>`: return the `latest_plan` field populated with a specific plan instead of the newest.

If no plans have been generated yet, returns HTTP 200 with `total_plans=0`
and `latest_plan=null`. Use `POST` to generate a plan first.

**Note:** Plans are stored in-process (server memory). They persist for the
lifetime of the server process and are cleared on restart.
    """,
    responses={
        200: {"description": "Plan list returned. `latest_plan` is null if no plans exist."},
        401: {"description": "Missing or invalid authentication token."},
        403: {"description": "Authenticated user does not own this dataset."},
        404: {"description": "Dataset not found in registry."},
        500: {"description": "Internal server error."},
    },
)
async def retrieve_plans(
    dataset_id: str = Path(
        ...,
        description="Registry dataset ID to retrieve cleaning plans for.",
        examples=["550e8400-e29b-41d4-a716-446655440000"],
    ),
    plan_id: str | None = Query(
        default=None,
        description=(
            "Optional. If provided, the `latest_plan` field in the response will "
            "contain this specific plan instead of the most recently generated one."
        ),
        examples=["3fa85f64-5717-4562-b3fc-2c963f66afa6"],
    ),
    user: dict = Depends(verify_firebase_token),
    service=Depends(get_dataset_service),
    store: PlanStore = Depends(get_plan_store),
) -> PlanListResponse:
    """Retrieve all stored CleaningPlans for a dataset."""
    uid = user["uid"]

    # ── Ownership check — dataset must exist and belong to this user ──────────
    _load_dataset_meta(dataset_id, uid, service)

    # ── Fetch all stored plans ────────────────────────────────────────────────
    all_plans = store.list_for_dataset(uid, dataset_id)

    # ── Build lightweight meta list ───────────────────────────────────────────
    metas: list[CleaningPlanMeta] = [
        CleaningPlanMeta.from_plan(p) for p in all_plans
    ]

    # ── Resolve the "selected" full plan ─────────────────────────────────────
    if plan_id:
        selected = store.get_by_plan_id(uid, dataset_id, plan_id)
        if selected is None and all_plans:
            # plan_id not found — fall back to latest with a warning header
            logger.warning(
                "plan_id '%s' not found for dataset %s — returning latest",
                plan_id, dataset_id,
            )
            selected = all_plans[0] if all_plans else None
    else:
        selected = all_plans[0] if all_plans else None

    return PlanListResponse(
        dataset_id=dataset_id,
        total_plans=len(all_plans),
        plans=metas,
        latest_plan=selected,
    )


# ── DELETE /api/v1/cleaning/plan/{dataset_id} ─────────────────────────────────

@router.delete(
    "/{dataset_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete all stored cleaning plans for a dataset",
    description="""
Purges all server-side stored cleaning plans for the given `dataset_id`.
The dataset itself is **not** affected. Use `POST` to regenerate a plan.
    """,
    responses={
        200: {"description": "Plans deleted successfully."},
        401: {"description": "Missing or invalid authentication token."},
        403: {"description": "Authenticated user does not own this dataset."},
        404: {"description": "Dataset not found in registry."},
    },
)
async def delete_plans(
    dataset_id: str = Path(
        ...,
        description="Registry dataset ID whose plans should be deleted.",
    ),
    user: dict = Depends(verify_firebase_token),
    service=Depends(get_dataset_service),
    store: PlanStore = Depends(get_plan_store),
) -> dict:
    uid = user["uid"]
    _load_dataset_meta(dataset_id, uid, service)
    deleted = store.delete_for_dataset(uid, dataset_id)
    return {
        "status": "deleted",
        "dataset_id": dataset_id,
        "plans_deleted": deleted,
        "message": f"Deleted {deleted} plan(s) for dataset '{dataset_id}'.",
    }
