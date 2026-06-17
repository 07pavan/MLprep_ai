from __future__ import annotations
from enum import Enum
from typing import Optional
from pydantic import BaseModel

class DatasetSource(str, Enum):
    upload = "upload"
    kaggle = "kaggle"
    github = "github"
    cloud = "cloud"

class DatasetBase(BaseModel):
    dataset_name: str
    source: DatasetSource
    original_file_type: str
    row_count: int
    column_count: int
    memory_usage: float
    parquet_path: str
    ml_readiness_score: Optional[int] = None
    dataset_version: int = 1
    status: str = "active"
    parent_dataset_id: Optional[str] = None
    source_url: Optional[str] = None
    import_options: Optional[dict] = None

class DatasetCreate(DatasetBase):
    pass

class DatasetUpdate(BaseModel):
    dataset_name: Optional[str] = None
    status: Optional[str] = None
    ml_readiness_score: Optional[int] = None
    dataset_version: Optional[int] = None
    parent_dataset_id: Optional[str] = None
    source_url: Optional[str] = None
    import_options: Optional[dict] = None

class DatasetResponse(DatasetBase):
    dataset_id: str
    user_id: str
    upload_timestamp: str
