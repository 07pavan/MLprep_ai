"""Upload router — handles multi-format file upload and profiling"""
from __future__ import annotations
import io
import logging
import asyncio
from functools import partial

import pandas as pd
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends

from utils.validators import validate_file, validate_dataframe
from utils.auth import verify_firebase_token
from services.data_ingestion_service import ingest_dataframe

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

    # 5. Ingest via unified ingestion service in a thread pool (non-blocking)
    metadata = {
        "filename": file.filename,
        "source": "upload",
        "original_file_type": name.rsplit(".", 1)[-1] if "." in name else "unknown",
    }

    res = await loop.run_in_executor(
        None,
        partial(ingest_dataframe, user["uid"], df, metadata)
    )

    logger.info(
        "Uploaded '%s' → session %s (%d×%d, %.2f MB in)",
        file.filename, res["sessionId"], len(df), len(df.columns), size_mb,
    )

    return res
