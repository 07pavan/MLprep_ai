from __future__ import annotations
import uuid
import logging
import os
from datetime import datetime
from typing import List

from fastapi import APIRouter, HTTPException, Depends, status
import pandas as pd

from utils.auth import verify_firebase_token
from schemas.dataset import DatasetCreate, DatasetResponse, DatasetUpdate
from services.dataset_service import get_dataset_service
from utils.session_manager import session_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/datasets", tags=["Dataset Registry"])

@router.post("", response_model=DatasetResponse, status_code=status.HTTP_201_CREATED)
async def create_dataset_endpoint(
    payload: DatasetCreate,
    user: dict = Depends(verify_firebase_token),
    service = Depends(get_dataset_service)
):
    """Register a new dataset entry in the metadata registry."""
    dataset_id = str(uuid.uuid4())
    upload_timestamp = datetime.utcnow().isoformat() + "Z"
    
    dataset_data = payload.dict()
    dataset_data.update({
        "dataset_id": dataset_id,
        "user_id": user["uid"],
        "upload_timestamp": upload_timestamp
    })
    
    try:
        service.create_dataset(dataset_data)
        return dataset_data
    except Exception as exc:
        logger.error("Failed to register dataset: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Database insertion failed: {exc}")


@router.get("", response_model=List[DatasetResponse])
async def list_datasets_endpoint(
    user: dict = Depends(verify_firebase_token),
    service = Depends(get_dataset_service)
):
    """Retrieve all dataset registry records owned by the authenticated user."""
    try:
        return service.list_datasets(user["uid"])
    except Exception as exc:
        logger.error("Failed to list datasets: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Database query failed: {exc}")


@router.get("/{dataset_id}", response_model=DatasetResponse)
async def get_dataset_endpoint(
    dataset_id: str,
    user: dict = Depends(verify_firebase_token),
    service = Depends(get_dataset_service)
):
    """Retrieve metadata for a specific dataset ID (ownership validated)."""
    try:
        dataset = service.get_dataset(dataset_id)
    except Exception as exc:
        logger.error("Failed to get dataset %s: %s", dataset_id, exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Database query failed: {exc}")
        
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
        
    if dataset["user_id"] != user["uid"]:
        raise HTTPException(status_code=403, detail="Not authorized to access this dataset")
        
    return dataset


@router.patch("/{dataset_id}", response_model=DatasetResponse)
async def update_dataset_endpoint(
    dataset_id: str,
    payload: DatasetUpdate,
    user: dict = Depends(verify_firebase_token),
    service = Depends(get_dataset_service)
):
    """Update dataset metadata (ownership validated)."""
    try:
        dataset = service.get_dataset(dataset_id)
    except Exception as exc:
        logger.error("Failed to get dataset %s on update: %s", dataset_id, exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Database query failed: {exc}")
        
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
        
    if dataset["user_id"] != user["uid"]:
        raise HTTPException(status_code=403, detail="Not authorized to update this dataset")
        
    update_data = payload.dict(exclude_unset=True)
    if not update_data:
        return dataset
        
    try:
        service.update_dataset(dataset_id, update_data)
        dataset.update(update_data)
        return dataset
    except Exception as exc:
        logger.error("Failed to update dataset %s: %s", dataset_id, exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Database update failed: {exc}")


@router.delete("/{dataset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dataset_endpoint(
    dataset_id: str,
    user: dict = Depends(verify_firebase_token),
    service = Depends(get_dataset_service)
):
    """Delete a dataset registry metadata record (ownership validated)."""
    try:
        dataset = service.get_dataset(dataset_id)
    except Exception as exc:
        logger.error("Failed to check dataset %s on delete: %s", dataset_id, exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Database check failed: {exc}")
        
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
        
    if dataset["user_id"] != user["uid"]:
        raise HTTPException(status_code=403, detail="Not authorized to delete this dataset")
        
    try:
        service.delete_dataset(dataset_id)
    except Exception as exc:
        logger.error("Failed to delete dataset %s: %s", dataset_id, exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Database delete failed: {exc}")
        
    return


@router.post("/{dataset_id}/activate")
async def activate_dataset_endpoint(
    dataset_id: str,
    user: dict = Depends(verify_firebase_token),
    service = Depends(get_dataset_service)
):
    """Load a registered dataset into the current active session."""
    try:
        dataset = service.get_dataset(dataset_id)
    except Exception as exc:
        logger.error("Failed to query dataset metadata for %s: %s", dataset_id, exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Database query failed: {exc}")
        
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
        
    if dataset["user_id"] != user["uid"]:
        raise HTTPException(status_code=403, detail="Not authorized to access this dataset")
        
    parquet_path = dataset["parquet_path"]
    if not os.path.exists(parquet_path):
        raise HTTPException(status_code=404, detail="Dataset file not found on disk")
        
    try:
        df = pd.read_parquet(parquet_path)
    except Exception as exc:
        logger.error("Failed to read parquet file %s: %s", parquet_path, exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to load dataset: {exc}")
        
    # Create new session
    session_id = session_manager.create_session(user["uid"])
    session_manager.save_dataframe(user["uid"], session_id, df)
    
    # Build columns info (reusing _profile_columns logic from services/data_ingestion_service.py)
    from services.data_ingestion_service import _profile_columns
    columns_info = _profile_columns(df)
    
    dataset_meta = {
        "filename": dataset["dataset_name"],
        "format": dataset["original_file_type"],
        "shape": {"rows": dataset["row_count"], "cols": dataset["column_count"]},
        "columns": columns_info,
        "memoryMb": dataset["memory_usage"],
    }
    
    return {
        "sessionId": session_id,
        "datasetId": dataset_id,
        "datasetMeta": dataset_meta
    }
