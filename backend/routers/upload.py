"""Upload router — handles multi-format file upload and profiling"""
from __future__ import annotations
import io
import logging
import asyncio
from functools import partial

import pandas as pd
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends

from utils.validators import validate_file, validate_dataframe
from utils.session_manager import session_manager
from utils.auth import verify_firebase_token

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["Upload"])


def _load_dataframe(name: str, contents: bytes) -> pd.DataFrame:
    """Load file bytes into a DataFrame (runs in thread pool to avoid blocking)."""
    buf = io.BytesIO(contents)
    if name.endswith(".csv"):
        return pd.read_csv(buf, low_memory=False)
    elif name.endswith((".xlsx", ".xls")):
        return pd.read_excel(buf)
    elif name.endswith(".json"):
        return pd.read_json(buf)
    elif name.endswith(".parquet"):
        return pd.read_parquet(buf)
    else:
        raise ValueError("Unsupported format")


def _profile_columns(df: pd.DataFrame) -> list[dict]:
    """Build per-column metadata — capped to avoid slow nunique on huge datasets."""
    MAX_ROWS_FOR_UNIQUE = 100_000
    sample = df if len(df) <= MAX_ROWS_FOR_UNIQUE else df.sample(MAX_ROWS_FOR_UNIQUE, random_state=0)
    cols = []
    for col in df.columns:
        null_count = int(df[col].isnull().sum())
        try:
            unique_count = int(sample[col].nunique())
        except Exception:
            unique_count = -1
        cols.append({
            "name": col,
            "dtype": str(df[col].dtype),
            "nullCount": null_count,
            "uniqueCount": unique_count,
        })
    return cols


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    user: dict = Depends(verify_firebase_token)
):
    """Upload a data file (CSV, Excel, JSON, Parquet) and create a session."""

    # 1. Validate filename
    is_valid, msg = validate_file(file.filename)
    if not is_valid:
        raise HTTPException(status_code=400, detail=msg)

    # 2. Read file bytes
    contents = await file.read()
    size_mb = len(contents) / (1024 * 1024)
    if size_mb > 100:
        raise HTTPException(status_code=400, detail=f"File too large ({size_mb:.1f} MB). Max 100 MB.")

    # 3. Load into DataFrame in a thread pool (non-blocking)
    name = (file.filename or "").lower()
    loop = asyncio.get_event_loop()
    try:
        df = await loop.run_in_executor(None, partial(_load_dataframe, name, contents))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to parse file: {exc}")

    # 4. Validate DataFrame
    ok, df_msg = validate_dataframe(df)
    if not ok:
        raise HTTPException(status_code=400, detail=df_msg)

    # 5. Create session and persist (in thread pool)
    session_id = session_manager.create_session(user["uid"])
    await loop.run_in_executor(None, partial(session_manager.save_dataframe, user["uid"], session_id, df))

    # 6. Profile columns (capped for speed) — also in thread pool
    columns_info = await loop.run_in_executor(None, partial(_profile_columns, df))

    # 7. Memory estimate — use fast non-deep estimate to avoid blocking
    mem_mb = round(df.memory_usage(deep=False).sum() / (1024 * 1024), 2)

    # 8. Score ML Readiness and register dataset in Dataset Registry
    import uuid
    from datetime import datetime
    from tools.ml_readiness_tool import score_ml_readiness
    from services.dataset_service import get_dataset_service

    try:
        ml_score = score_ml_readiness(df)["score"]
    except Exception as exc:
        logger.error("Failed to score uploaded dataset: %s", exc, exc_info=True)
        ml_score = 0

    dataset_id = str(uuid.uuid4())
    upload_timestamp = datetime.utcnow().isoformat() + "Z"
    parquet_path = session_manager.get_data_path(user["uid"], session_id)

    dataset_record = {
        "dataset_id": dataset_id,
        "user_id": user["uid"],
        "dataset_name": file.filename,
        "source": "upload",
        "original_file_type": name.rsplit(".", 1)[-1] if "." in name else "unknown",
        "upload_timestamp": upload_timestamp,
        "row_count": len(df),
        "column_count": len(df.columns),
        "memory_usage": mem_mb,
        "parquet_path": parquet_path,
        "ml_readiness_score": ml_score,
        "dataset_version": 1,
        "status": "active"
    }

    try:
        db_service = get_dataset_service()
        db_service.create_dataset(dataset_record)
        logger.info("Registered uploaded dataset %s in metadata registry", dataset_id)
    except Exception as exc:
        logger.error("Failed to store dataset metadata: %s", exc, exc_info=True)
        # We don't fail the upload entirely if registry fails, but we log the error

    logger.info(
        "Uploaded '%s' → session %s (%d×%d, %.2f MB in)",
        file.filename, session_id, len(df), len(df.columns), size_mb,
    )

    return {
        "sessionId": session_id,
        "datasetId": dataset_id,
        "filename": file.filename,
        "format": name.rsplit(".", 1)[-1] if "." in name else "unknown",
        "shape": {"rows": len(df), "cols": len(df.columns)},
        "columns": columns_info,
        "memoryMb": mem_mb,
    }
