"""
Data ingestion service.
Provides a unified pipeline to ingest pandas DataFrames into MLPrep AI.
Handles session creation, Parquet persistence, column profiling, ML readiness scoring,
and dataset registry metadata insertion.
"""
from __future__ import annotations
import uuid
import logging
from datetime import datetime
from typing import Dict, Any

import pandas as pd

from utils.session_manager import session_manager
from tools.ml_readiness_tool import score_ml_readiness
from services.dataset_service import get_dataset_service

logger = logging.getLogger(__name__)


def _profile_columns(df: pd.DataFrame) -> list[dict[str, Any]]:
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


def ingest_dataframe(
    user_id: str,
    dataframe: pd.DataFrame,
    metadata: Dict[str, Any]
) -> Dict[str, Any]:
    """Ingest a pandas DataFrame into the system.
    
    Args:
        user_id: ID of the owning tenant.
        dataframe: The populated pandas DataFrame to ingest.
        metadata: Ingestion parameters including:
            - "filename": Name of the source file.
            - "source": Enum value from DatasetSource (e.g. "upload", "github", etc.).
            - "original_file_type": The parsed suffix format (e.g. "csv", "xlsx", etc.).
            
    Returns:
        Dict[str, Any]: The standard API payload dictionary expected by the frontend.
    """
    # 1. Create active session workspace
    session_id = session_manager.create_session(user_id)

    # 2. Persist DataFrame as Parquet for performance and dtype preservation
    session_manager.save_dataframe(user_id, session_id, dataframe)

    # 3. Profile columns (capped for speed)
    columns_info = _profile_columns(dataframe)

    # 4. Memory estimate (fast non-deep to avoid event loop blocking)
    mem_mb = round(dataframe.memory_usage(deep=False).sum() / (1024 * 1024), 2)

    # 5. Score ML Readiness
    try:
        ml_score = score_ml_readiness(dataframe)["score"]
    except Exception as exc:
        logger.error("Failed to score ingested dataset: %s", exc, exc_info=True)
        ml_score = 0

    # 6. Construct metadata registry record
    dataset_id = str(uuid.uuid4())
    upload_timestamp = datetime.utcnow().isoformat() + "Z"
    parquet_path = session_manager.get_data_path(user_id, session_id)

    dataset_record = {
        "dataset_id": dataset_id,
        "user_id": user_id,
        "dataset_name": metadata.get("filename", "untitled_dataset"),
        "source": metadata.get("source", "upload"),
        "original_file_type": metadata.get("original_file_type", "unknown"),
        "upload_timestamp": upload_timestamp,
        "row_count": len(dataframe),
        "column_count": len(dataframe.columns),
        "memory_usage": mem_mb,
        "parquet_path": parquet_path,
        "ml_readiness_score": ml_score,
        "dataset_version": 1,
        "status": "active",
        "parent_dataset_id": metadata.get("parent_dataset_id")
    }

    # 7. Register metadata inside the db registry (PostgreSQL/Firestore)
    try:
        db_service = get_dataset_service()
        db_service.create_dataset(dataset_record)
        logger.info(
            "Registered ingested dataset '%s' (ID: %s, tenant: %s) in metadata registry",
            dataset_record["dataset_name"], dataset_id, user_id
        )
    except Exception as exc:
        # Non-blocking failure: log metadata storage issue but allow execution to proceed
        logger.error("Failed to store dataset metadata in registry: %s", exc, exc_info=True)

    # 8. Return response contract matching upload router payload
    warning = None
    if len(dataframe) > 100000:
        warning = (
            "Large dataset detected. Columns will be profiled using a sample subset of 100k rows. "
            "Downstream AI insights and storytelling calculations may experience increased latency."
        )

    return {
        "sessionId": session_id,
        "datasetId": dataset_id,
        "filename": dataset_record["dataset_name"],
        "format": dataset_record["original_file_type"],
        "shape": {"rows": len(dataframe), "cols": len(dataframe.columns)},
        "columns": columns_info,
        "memoryMb": mem_mb,
        "warning": warning,
    }
