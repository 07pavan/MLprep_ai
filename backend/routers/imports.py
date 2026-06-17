"""
Dataset import router.
Exposes endpoint to import remote datasets from external URLs.
"""
from __future__ import annotations
import logging
import asyncio
from functools import partial
from urllib.parse import urlparse
from pathlib import Path

from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel

from utils.auth import verify_firebase_token
from services.dataset_source_service import load_remote_dataset, DatasetLoadException
from services.data_ingestion_service import ingest_dataframe
from utils.url_validator import InvalidURLException, UnsafeURLException
from services.http_dataset_downloader import DownloadException, DownloadSizeLimitExceeded

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/datasets", tags=["Dataset Import"])


class DatasetImportRequest(BaseModel):
    url: str


@router.post("/import", response_model=dict, status_code=status.HTTP_201_CREATED)
async def import_dataset_endpoint(
    req: DatasetImportRequest,
    user: dict = Depends(verify_firebase_token)
):
    """Import a dataset from a remote URL (CSV, Excel, JSON, Parquet).
    
    Verifies tenant credentials, downloads the dataset safely with SSRF and size
    limits checks, converts it to a DataFrame, and triggers the ingestion pipeline.
    """
    url = req.url

    try:
        # 1. Fetch the remote dataset and parse into a DataFrame (runs safety and size checks internally)
        df = await load_remote_dataset(url)
    except (InvalidURLException, UnsafeURLException) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"URL validation failed: {exc}"
        )
    except DownloadSizeLimitExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=str(exc)
        )
    except DownloadException as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to download dataset from URL: {exc}"
        )
    except DatasetLoadException as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Failed to parse and load dataset: {exc}"
        )
    except Exception as exc:
        logger.error("Unexpected error importing dataset from '%s': %s", url, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred during dataset import: {exc}"
        )

    # 2. Extract metadata parameters from URL for registration
    parsed_path = urlparse(url).path
    filename = Path(parsed_path).name or "imported_dataset"
    ext = Path(parsed_path).suffix.lower().replace(".", "")
    if not ext:
        ext = "csv"  # Default fallback format

    # Classify the source type based on URL patterns
    if "github.com" in url or "raw.githubusercontent.com" in url:
        source = "github"
    elif "kaggle.com" in url:
        source = "kaggle"
    else:
        source = "cloud"

    metadata = {
        "filename": filename,
        "source": source,
        "original_file_type": ext,
    }

    # 3. Ingest the DataFrame using the unified Data Ingestion Service
    loop = asyncio.get_event_loop()
    try:
        # Run ingestion in a thread pool to avoid blocking the async event loop
        res = await loop.run_in_executor(
            None,
            partial(ingest_dataframe, user["uid"], df, metadata)
        )
        return res
    except Exception as exc:
        logger.error("Failed to ingest imported dataset: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to ingest dataset: {exc}"
        )
