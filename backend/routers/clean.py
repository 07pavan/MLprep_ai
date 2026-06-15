"""Cleaning router — data quality reports and cleaning operations"""
from __future__ import annotations
import logging

from fastapi import APIRouter, HTTPException, Query, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import io

from agents.cleaner import DataCleanerAgent
from utils.session_manager import session_manager
from utils.auth import verify_firebase_token
from tools.quality_tool import check_quality
from tools.cleaning_planner import generate_cleaning_plan
from tools.cleaning_executor import apply_cleaning_plan
from tools.ml_readiness_tool import score_ml_readiness
from services.dataset_service import get_dataset_service
from typing import Optional, Any
import os
import uuid
import re
from datetime import datetime
import pandas as pd

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["Cleaning"])

cleaner = DataCleanerAgent()


class CleanRequest(BaseModel):
    sessionId: str
    options: dict


@router.get("/clean/report")
async def get_cleaning_report(
    sessionId: str = Query(...),
    user: dict = Depends(verify_firebase_token)
):
    """Return a data quality report for the session's dataset."""
    df = session_manager.load_dataframe(user["uid"], sessionId)
    report = cleaner.get_cleaning_report(df)
    suggestions = cleaner.suggest_cleaning_steps(df)
    return {
        "report": report,
        "suggestedDefaults": suggestions,
    }


@router.post("/clean")
async def apply_cleaning(
    req: CleanRequest,
    user: dict = Depends(verify_firebase_token)
):
    """Apply cleaning operations and persist the cleaned dataset."""
    df = session_manager.load_dataframe(user["uid"], req.sessionId)
    rows_before = len(df)
    cols_before = len(df.columns)

    cleaned_df, change_log = cleaner.clean(df, req.options)

    # Persist cleaned version
    session_manager.save_dataframe(user["uid"], req.sessionId, cleaned_df)

    return {
        "success": True,
        "changeLog": change_log,
        "metrics": {
            "rowsBefore": rows_before,
            "rowsAfter": len(cleaned_df),
            "colsBefore": cols_before,
            "colsAfter": len(cleaned_df.columns),
        },
    }


@router.get("/clean/download")
async def download_cleaned(
    sessionId: str = Query(...),
    user: dict = Depends(verify_firebase_token)
):
    """Download the current session dataset as CSV."""
    df = session_manager.load_dataframe(user["uid"], sessionId)
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    buf.seek(0)

    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=cleaned_data.csv"},
    )


@router.get("/cleaning-plan")
async def get_cleaning_plan(
    sessionId: str = Query(...),
    user: dict = Depends(verify_firebase_token)
):
    """Generate a data cleaning plan based on dataset quality inspection."""
    try:
        df = session_manager.load_dataframe(user["uid"], sessionId)
        quality_report = check_quality(df)
        plan = generate_cleaning_plan(df, quality_report)
        return plan
    except Exception as exc:
        logger.error("Failed to generate cleaning plan for session %s: %s", sessionId, exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to generate cleaning plan: {exc}")


class ApplyCleaningRequest(BaseModel):
    datasetId: Optional[str] = None
    dataset_id: Optional[str] = None
    sessionId: Optional[str] = None
    plan: dict


@router.post("/apply-cleaning")
async def apply_cleaning_endpoint(
    req: ApplyCleaningRequest,
    user: dict = Depends(verify_firebase_token),
    service = Depends(get_dataset_service)
):
    """Apply data cleaning plan, create a new version of the dataset, and register it."""
    db_id = req.datasetId or req.dataset_id

    if db_id:
        try:
            dataset_meta = service.get_dataset(db_id)
        except Exception as exc:
            logger.error("Failed to query dataset metadata for %s: %s", db_id, exc, exc_info=True)
            raise HTTPException(status_code=500, detail=f"Database query failed: {exc}")

        if not dataset_meta:
            raise HTTPException(status_code=404, detail=f"Dataset with ID '{db_id}' not found in registry")

        if dataset_meta["user_id"] != user["uid"]:
            raise HTTPException(status_code=403, detail="Not authorized to access this dataset")

        original_parquet_path = dataset_meta["parquet_path"]
        if not os.path.exists(original_parquet_path):
            raise HTTPException(status_code=404, detail="Dataset file not found on disk")

        try:
            df = pd.read_parquet(original_parquet_path)
        except Exception as exc:
            logger.error("Failed to load dataset parquet file %s: %s", original_parquet_path, exc, exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to load dataset: {exc}")

        orig_filename = dataset_meta.get("dataset_name") or "dataset.parquet"
        orig_source = dataset_meta.get("source") or "upload"
        orig_version = dataset_meta.get("dataset_version") or 1
        parent_dir = os.path.dirname(original_parquet_path)

    elif req.sessionId:
        try:
            df = session_manager.load_dataframe(user["uid"], req.sessionId)
        except HTTPException as exc:
            raise exc
        except Exception as exc:
            logger.error("Failed to load session dataframe for session %s: %s", req.sessionId, exc, exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to load dataset: {exc}")

        orig_filename = "dataset.parquet"
        orig_source = "upload"
        orig_version = 1
        session_data_path = session_manager.get_data_path(user["uid"], req.sessionId)
        parent_dir = os.path.dirname(session_data_path)

    else:
        raise HTTPException(status_code=400, detail="Either datasetId (or dataset_id) or sessionId must be provided")

    # Calculate baseline score
    try:
        old_score = score_ml_readiness(df)["score"]
    except Exception as exc:
        logger.error("Failed to score baseline ML readiness: %s", exc, exc_info=True)
        old_score = 0

    # Apply cleaning steps
    try:
        cleaned_df, stats = apply_cleaning_plan(df, req.plan)
    except Exception as exc:
        logger.error("Failed to execute cleaning plan: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to execute cleaning plan: {exc}")

    # Calculate post-cleaning score
    try:
        new_score = score_ml_readiness(cleaned_df)["score"]
    except Exception as exc:
        logger.error("Failed to score post-cleaned ML readiness: %s", exc, exc_info=True)
        new_score = old_score

    # Compile improvements report
    improvements = []
    if stats.get("duplicates_removed", 0) > 0:
        improvements.append(f"Removed {stats['duplicates_removed']} duplicates")
    if stats.get("missing_values_filled", 0) > 0:
        improvements.append(f"Filled {stats['missing_values_filled']} missing values")
    if stats.get("outliers_removed", 0) > 0:
        improvements.append(f"Removed {stats['outliers_removed']} outliers")
    for col in stats.get("columns_dropped", []):
        improvements.append(f"Dropped column '{col}'")
    for change_msg in stats.get("types_converted", []):
        improvements.append(change_msg)

    # Establish new version and path
    new_version = orig_version + 1
    base_name = orig_filename.rsplit(".", 1)[0] if "." in orig_filename else orig_filename
    base_name = re.sub(r"_v\d+$", "", base_name)
    base_name = re.sub(r"^cleaned_", "", base_name)
    new_filename = f"cleaned_{base_name}_v{new_version}.parquet"
    new_parquet_path = os.path.join(parent_dir, new_filename)

    # Save cleaned dataframe
    try:
        cleaned_df.to_parquet(new_parquet_path, index=False)
    except Exception as exc:
        logger.error("Failed to save cleaned parquet file at %s: %s", new_parquet_path, exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to write cleaned file: {exc}")

    # Register in Dataset Registry
    new_dataset_id = str(uuid.uuid4())
    upload_timestamp = datetime.utcnow().isoformat() + "Z"
    row_count = len(cleaned_df)
    column_count = len(cleaned_df.columns)
    try:
        memory_usage = round(cleaned_df.memory_usage(deep=False).sum() / (1024 * 1024), 2)
    except Exception:
        memory_usage = 0.0

    new_dataset_data = {
        "dataset_id": new_dataset_id,
        "user_id": user["uid"],
        "dataset_name": new_filename,
        "original_file_type": "parquet",
        "source": orig_source,
        "upload_timestamp": upload_timestamp,
        "row_count": row_count,
        "column_count": column_count,
        "memory_usage": memory_usage,
        "parquet_path": new_parquet_path,
        "ml_readiness_score": new_score,
        "dataset_version": new_version,
        "status": "active"
    }

    try:
        service.create_dataset(new_dataset_data)
    except Exception as exc:
        logger.error("Failed to register cleaned dataset version in database registry: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to update dataset registry: {exc}")

    return {
        "dataset_version": new_version,
        "old_score": old_score,
        "new_score": new_score,
        "improvements": improvements
    }

