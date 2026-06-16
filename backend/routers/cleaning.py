"""Phase 2A Cleaning Router — read-only plan generation endpoints.

Phase 2A contract:
  - GET  /api/v2/cleaning/plan          → plan from active session
  - GET  /api/v2/cleaning/plan/dataset  → plan from registered dataset
  - GET  /api/v2/cleaning/summary       → lightweight summary only

Architecture:
  The router owns all DataFrame I/O:
    1. Load DataFrame from session or registry
    2. Run profile_dataset(df)  → profile dict
    3. Run check_quality(df)    → quality dict
    4. Call build_cleaning_plan(profile, quality, ...) → CleaningPlan

  The service receives only dicts — it never sees a DataFrame.

IMPORTANT: No endpoint in this router mutates any dataset.
All write operations belong to Phase 2B (cleaning execution).
"""
from __future__ import annotations

import logging
import os

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from pydantic import BaseModel

from schemas.cleaning_plan import CleaningPlan, CleaningSummary
from tools.cleaning_executor import apply_cleaning_plan
from services.cleaning_planner import build_cleaning_plan
from services.dataset_service import get_dataset_service
from tools.profiler_tool import profile_dataset
from tools.quality_tool import check_quality
from utils.session_manager import session_manager
from utils.auth import verify_firebase_token

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v2/cleaning",
    tags=["Cleaning Planner (Phase 2A)"],
)


# ── Shared helpers ────────────────────────────────────────────────────────────

def _profile_and_quality(df: pd.DataFrame) -> tuple[dict, dict]:
    """Run profiler + quality check and return (profile, quality_report) dicts."""
    try:
        profile = profile_dataset(df)
    except Exception as exc:
        logger.error("Profiler failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Dataset profiling failed: {exc}")

    try:
        quality_report = check_quality(df)
    except Exception as exc:
        logger.error("Quality check failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Quality check failed: {exc}")

    return profile, quality_report


# ── Endpoint 1: Plan from session ─────────────────────────────────────────────

@router.get(
    "/plan",
    response_model=CleaningPlan,
    summary="Generate intelligent cleaning plan for an active upload session",
    description=(
        "Profiles the dataset in the given session, runs quality checks, "
        "and returns a fully structured, read-only cleaning plan. "
        "**No data is modified.** Phase 2A plan-only endpoint."
    ),
)
async def get_plan_for_session(
    sessionId: str = Query(..., description="Upload session ID from /api/upload"),
    user: dict = Depends(verify_firebase_token),
) -> CleaningPlan:
    uid = user["uid"]

    if not session_manager.session_exists(uid, sessionId):
        raise HTTPException(
            status_code=404,
            detail=f"Session '{sessionId}' not found. Upload a file first.",
        )

    # ── I/O layer: load DataFrame ──────────────────────────────────────────────
    try:
        df = session_manager.load_dataframe(uid, sessionId)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to load session df for %s: %s", sessionId, exc)
        raise HTTPException(status_code=500, detail=f"Failed to load session data: {exc}")

    # ── Analysis layer: profile + quality ─────────────────────────────────────
    profile, quality_report = _profile_and_quality(df)

    # ── Service layer: pure functional plan generation ─────────────────────────
    try:
        plan = build_cleaning_plan(
            profile=profile,
            quality_report=quality_report,
            session_id=sessionId,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        logger.error("Plan generation failed for session %s: %s", sessionId, exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Plan generation failed: {exc}")

    return plan


# ── Endpoint 2: Plan from registered dataset ──────────────────────────────────

@router.get(
    "/plan/dataset",
    response_model=CleaningPlan,
    summary="Generate intelligent cleaning plan for a registered dataset",
    description=(
        "Loads the registered dataset by its ID, profiles it, runs quality checks, "
        "and returns a read-only cleaning plan. **No data is modified.** "
        "Phase 2A plan-only endpoint."
    ),
)
async def get_plan_for_dataset(
    datasetId: str = Query(..., description="Dataset registry ID"),
    user: dict = Depends(verify_firebase_token),
    service=Depends(get_dataset_service),
) -> CleaningPlan:
    uid = user["uid"]

    # ── Registry lookup ────────────────────────────────────────────────────────
    try:
        meta = service.get_dataset(datasetId)
    except Exception as exc:
        logger.error("Registry lookup failed for %s: %s", datasetId, exc)
        raise HTTPException(status_code=500, detail=f"Registry query failed: {exc}")

    if not meta:
        raise HTTPException(
            status_code=404,
            detail=f"Dataset '{datasetId}' not found in registry.",
        )

    # ── Ownership check ────────────────────────────────────────────────────────
    if meta.get("user_id") != uid:
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to access this dataset.",
        )

    # ── I/O layer: load from disk ──────────────────────────────────────────────
    parquet_path: str = meta.get("parquet_path", "")
    if not parquet_path or not os.path.exists(parquet_path):
        raise HTTPException(
            status_code=404,
            detail="Dataset file not found on disk. It may have been deleted.",
        )

    try:
        df = pd.read_parquet(parquet_path)
    except Exception as exc:
        logger.error("Failed to read parquet %s: %s", parquet_path, exc)
        raise HTTPException(status_code=500, detail=f"Failed to load dataset file: {exc}")

    # ── Analysis layer ─────────────────────────────────────────────────────────
    profile, quality_report = _profile_and_quality(df)

    # ── Service layer ──────────────────────────────────────────────────────────
    try:
        plan = build_cleaning_plan(
            profile=profile,
            quality_report=quality_report,
            dataset_id=datasetId,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        logger.error("Plan generation failed for dataset %s: %s", datasetId, exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Plan generation failed: {exc}")

    return plan


# ── Endpoint 3: Summary only (lightweight) ────────────────────────────────────

@router.get(
    "/summary",
    response_model=CleaningSummary,
    summary="Get cleaning plan summary (quality scores and issue counts only)",
    description=(
        "Returns only the CleaningSummary — no full action list. "
        "Ideal for dashboard health widgets. **Read-only.**"
    ),
)
async def get_cleaning_summary(
    sessionId: str = Query(..., description="Upload session ID from /api/upload"),
    user: dict = Depends(verify_firebase_token),
) -> CleaningSummary:
    uid = user["uid"]

    if not session_manager.session_exists(uid, sessionId):
        raise HTTPException(status_code=404, detail=f"Session '{sessionId}' not found.")

    try:
        df = session_manager.load_dataframe(uid, sessionId)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to load session data: {exc}")

    profile, quality_report = _profile_and_quality(df)

    try:
        plan = build_cleaning_plan(
            profile=profile,
            quality_report=quality_report,
            session_id=sessionId,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        logger.error("Summary generation failed for %s: %s", sessionId, exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Summary generation failed: {exc}")

    return plan.summary


import re
import uuid
from datetime import datetime, timezone
from typing import Optional

class CleaningExecuteRequest(BaseModel):
    sessionId: Optional[str] = None
    datasetId: Optional[str] = None
    plan: dict
    action_ids: list[str] | None = None

@router.post(
    "/execute",
    summary="Execute intelligent cleaning plan for an active upload session or registered dataset",
    description=(
        "Applies selected cleaning plan actions on the dataset (either from active session or "
        "registered metadata), re-runs profiling and quality checks, and returns execution metrics. "
        "For sessions, creates a backup. For registered datasets, generates a new versioned file "
        "and metadata record."
    ),
)
async def execute_plan(
    req: CleaningExecuteRequest,
    user: dict = Depends(verify_firebase_token),
    service = Depends(get_dataset_service),
):
    uid = user["uid"]

    # ── Branch 1: Registry-based dataset execution ────────────────────────────
    if req.datasetId:
        try:
            meta = service.get_dataset(req.datasetId)
        except Exception as exc:
            logger.error("Registry lookup failed for %s: %s", req.datasetId, exc)
            raise HTTPException(status_code=500, detail=f"Database query failed: {exc}")

        if not meta:
            raise HTTPException(status_code=404, detail="Dataset not found in registry.")

        if meta.get("user_id") != uid:
            raise HTTPException(status_code=403, detail="You do not have permission to access this dataset.")

        parquet_path = meta.get("parquet_path", "")
        if not parquet_path or not os.path.exists(parquet_path):
            raise HTTPException(status_code=404, detail="Dataset file not found on disk.")

        try:
            df = pd.read_parquet(parquet_path)
        except Exception as exc:
            logger.error("Failed to read parquet %s: %s", parquet_path, exc)
            raise HTTPException(status_code=500, detail=f"Failed to load dataset file: {exc}")

        orig_profile, orig_quality = _profile_and_quality(df)
        try:
            orig_plan = build_cleaning_plan(
                profile=orig_profile,
                quality_report=orig_quality,
                dataset_id=req.datasetId,
            )
            orig_score = orig_plan.summary.overall_quality_score
        except Exception as exc:
            logger.warning("Failed to calculate baseline score, defaulting to 0: %s", exc)
            orig_score = 0

        rows_before = len(df)
        cols_before = len(df.columns)

        try:
            cleaned_df, stats = apply_cleaning_plan(df, req.plan, action_ids=req.action_ids)
        except Exception as exc:
            logger.error("Failed to execute cleaning plan: %s", exc)
            raise HTTPException(status_code=500, detail=f"Failed to execute cleaning plan: {exc}")

        # Establish new version and path
        orig_name = meta.get("dataset_name", "dataset.parquet")
        base_name = orig_name.rsplit(".", 1)[0] if "." in orig_name else orig_name
        base_name = re.sub(r"_v\d+$", "", base_name)
        base_name = re.sub(r"^cleaned_", "", base_name)
        new_version = (meta.get("dataset_version") or 1) + 1
        new_filename = f"cleaned_{base_name}_v{new_version}.parquet"
        
        parent_dir = os.path.dirname(parquet_path)
        new_path = os.path.join(parent_dir, new_filename)

        try:
            cleaned_df.to_parquet(new_path, index=False)
        except Exception as exc:
            logger.error("Failed to save cleaned parquet file at %s: %s", new_path, exc)
            raise HTTPException(status_code=500, detail=f"Failed to save cleaned dataset: {exc}")

        new_profile, new_quality = _profile_and_quality(cleaned_df)
        try:
            new_plan = build_cleaning_plan(
                profile=new_profile,
                quality_report=new_quality,
                dataset_id=req.datasetId,
            )
            new_score = new_plan.summary.overall_quality_score
        except Exception as exc:
            logger.warning("Failed to calculate post-clean score, defaulting to baseline: %s", exc)
            new_score = orig_score

        new_dataset_id = str(uuid.uuid4())
        upload_timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        row_count = len(cleaned_df)
        column_count = len(cleaned_df.columns)
        try:
            memory_usage = round(cleaned_df.memory_usage(deep=False).sum() / (1024 * 1024), 2)
        except Exception:
            memory_usage = 0.0

        new_meta = {
            "dataset_id": new_dataset_id,
            "user_id": uid,
            "dataset_name": new_filename,
            "original_file_type": "parquet",
            "source": meta.get("source", "upload"),
            "upload_timestamp": upload_timestamp,
            "row_count": row_count,
            "column_count": column_count,
            "memory_usage": memory_usage,
            "parquet_path": new_path,
            "ml_readiness_score": new_score,
            "dataset_version": new_version,
            "status": "active",
            "parent_dataset_id": req.datasetId
        }

        try:
            service.create_dataset(new_meta)
        except Exception as exc:
            logger.error("Failed to register cleaned dataset: %s", exc)
            raise HTTPException(status_code=500, detail=f"Failed to update dataset registry: {exc}")

        return {
            "success": True,
            "datasetId": new_dataset_id,
            "dataset_version": new_version,
            "original_score": orig_score,
            "new_score": new_score,
            "applied_actions": stats.get("actions_executed", []),
            "metrics": {
                "rowsBefore": rows_before,
                "rowsAfter": row_count,
                "colsBefore": cols_before,
                "colsAfter": column_count,
            },
            "stats": stats,
        }

    # ── Branch 2: Session-based execution ─────────────────────────────────────
    elif req.sessionId:
        if not session_manager.session_exists(uid, req.sessionId):
            raise HTTPException(
                status_code=404,
                detail=f"Session '{req.sessionId}' not found.",
            )

        session_manager.create_backup_if_not_exists(uid, req.sessionId)

        try:
            df = session_manager.load_dataframe(uid, req.sessionId)
        except Exception as exc:
            logger.error("Failed to load session df for %s: %s", req.sessionId, exc)
            raise HTTPException(status_code=500, detail=f"Failed to load session data: {exc}")

        orig_profile, orig_quality = _profile_and_quality(df)
        try:
            orig_plan = build_cleaning_plan(
                profile=orig_profile,
                quality_report=orig_quality,
                session_id=req.sessionId,
            )
            orig_score = orig_plan.summary.overall_quality_score
        except Exception as exc:
            logger.warning("Failed to calculate baseline score, defaulting to 0: %s", exc)
            orig_score = 0

        rows_before = len(df)
        cols_before = len(df.columns)

        try:
            cleaned_df, stats = apply_cleaning_plan(df, req.plan, action_ids=req.action_ids)
        except Exception as exc:
            logger.error("Failed to execute cleaning plan: %s", exc)
            raise HTTPException(status_code=500, detail=f"Failed to execute cleaning plan: {exc}")

        try:
            session_manager.save_dataframe(uid, req.sessionId, cleaned_df)
        except Exception as exc:
            logger.error("Failed to save cleaned df: %s", exc)
            raise HTTPException(status_code=500, detail=f"Failed to save cleaned data: {exc}")

        new_profile, new_quality = _profile_and_quality(cleaned_df)
        try:
            new_plan = build_cleaning_plan(
                profile=new_profile,
                quality_report=new_quality,
                session_id=req.sessionId,
            )
            new_score = new_plan.summary.overall_quality_score
        except Exception as exc:
            logger.warning("Failed to calculate post-clean score, defaulting to baseline: %s", exc)
            new_score = orig_score

        rows_after = len(cleaned_df)
        cols_after = len(cleaned_df.columns)

        return {
            "success": True,
            "sessionId": req.sessionId,
            "original_score": orig_score,
            "new_score": new_score,
            "applied_actions": stats.get("actions_executed", []),
            "metrics": {
                "rowsBefore": rows_before,
                "rowsAfter": rows_after,
                "colsBefore": cols_before,
                "colsAfter": cols_after,
            },
            "stats": stats,
        }

    else:
        raise HTTPException(status_code=400, detail="Either sessionId or datasetId must be provided.")


class CleaningResetRequest(BaseModel):
    sessionId: str

@router.post(
    "/reset",
    summary="Reset cleaning session back to original state",
    description="Restores the original parquet file (data_orig.parquet) back as the active session data.",
)
async def reset_session(
    req: CleaningResetRequest,
    user: dict = Depends(verify_firebase_token),
):
    uid = user["uid"]
    
    if not session_manager.session_exists(uid, req.sessionId):
        raise HTTPException(
            status_code=404,
            detail=f"Session '{req.sessionId}' not found.",
        )
        
    restored = session_manager.restore_backup(uid, req.sessionId)
    if not restored:
        raise HTTPException(
            status_code=400,
            detail="No original backup found. The session is already in its original state.",
        )
        
    return {
        "success": True,
        "sessionId": req.sessionId,
        "message": "Session restored to original state successfully."
    }

