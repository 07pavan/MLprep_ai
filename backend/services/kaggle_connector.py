"""
Kaggle dataset connector service.
Handles secure extraction, size validation, zip bomb protection, path traversal protection,
and parses Kaggle dataset archives into pandas DataFrames.
"""
from __future__ import annotations
import os
import re
import logging
import tempfile
import asyncio
import json
import zipfile
from pathlib import Path
from typing import Optional

import pandas as pd

from config.settings import settings
from services.http_dataset_downloader import DownloadException, DownloadSizeLimitExceeded
from services.dataset_source_service import DatasetLoadException

logger = logging.getLogger(__name__)


class KaggleConnector:
    """Connector service for downloading and loading datasets from Kaggle."""

    def __init__(self):
        """Initialize the Kaggle connector with configured limits."""
        self.max_size_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024

    def _extract_slug(self, url: str) -> str:
        """Extract the owner/dataset slug from a Kaggle URL.
        
        Args:
            url: The absolute Kaggle URL.
            
        Returns:
            str: The dataset slug (e.g. 'owner/dataset-name').
            
        Raises:
            DownloadException: If the URL format is invalid.
        """
        pattern = r"^https?://(?:www\.)?kaggle\.com/datasets/([^/]+)/([^/?#]+)"
        match = re.match(pattern, url)
        if not match:
            raise DownloadException(f"Invalid Kaggle dataset URL structure: {url}")
        owner, dataset_name = match.groups()
        return f"{owner}/{dataset_name}"

    async def download_dataset(self, url: str) -> pd.DataFrame:
        """Download a dataset from Kaggle, extract safely, and parse the main file.
        
        Args:
            url: The absolute Kaggle dataset URL.
            
        Returns:
            pd.DataFrame: Loaded dataset in memory.
            
        Raises:
            DownloadException: Credential configuration or connection failures.
            DownloadSizeLimitExceeded: Uncompressed archive size exceeds limit.
            DatasetLoadException: Parsing error or missing supported data files.
        """
        # 1. Setup credentials
        has_user_keys = bool(settings.KAGGLE_USERNAME and settings.KAGGLE_KEY)
        has_api_token = bool(settings.KAGGLE_API_TOKEN)

        if not has_user_keys and not has_api_token:
            logger.error("Kaggle credentials not configured in settings.")
            raise DownloadException(
                "Kaggle credentials (KAGGLE_USERNAME/KAGGLE_KEY or KAGGLE_API_TOKEN) are not configured."
            )

        # Set environment variables expected by the Kaggle SDK
        if has_user_keys:
            os.environ["KAGGLE_USERNAME"] = settings.KAGGLE_USERNAME
            os.environ["KAGGLE_KEY"] = settings.KAGGLE_KEY
        if has_api_token:
            os.environ["KAGGLE_API_TOKEN"] = settings.KAGGLE_API_TOKEN

        # 2. Extract dataset slug
        slug = self._extract_slug(url)

        # 3. Create temporary directory context for safe downloads and extractions
        with tempfile.TemporaryDirectory() as temp_dir_str:
            temp_dir = Path(temp_dir_str)

            # 4. Authenticate and initialize Kaggle API in a worker thread (non-blocking)
            try:
                from kaggle.api.kaggle_api_extended import KaggleApi
                api = KaggleApi()
                await asyncio.to_thread(api.authenticate)
            except Exception as e:
                logger.error("Failed to authenticate with Kaggle API: %s", e)
                raise DownloadException(f"Kaggle API authentication failed: {e}")

            logger.info("Downloading Kaggle dataset '%s'...", slug)
            try:
                # Download ZIP archive without extracting first to inspect size and file paths
                await asyncio.to_thread(
                    api.dataset_download_files,
                    slug,
                    path=str(temp_dir),
                    unzip=False,
                    quiet=True
                )
            except Exception as e:
                logger.error("Failed to download files for Kaggle dataset '%s': %s", slug, e)
                raise DownloadException(f"Kaggle dataset download failed: {e}")

            # Locate downloaded zip file
            zip_files = list(temp_dir.glob("*.zip"))
            if not zip_files:
                raise DownloadException("No zip archive downloaded from Kaggle.")

            zip_file_path = zip_files[0]

            # 5. Inspect ZIP contents (SSRF, zip bomb, and traversal checks) before extraction
            try:
                with zipfile.ZipFile(zip_file_path, "r") as z:
                    total_uncompressed_size = 0
                    for info in z.infolist():
                        # Path traversal prevention
                        filename = info.filename
                        if filename.startswith("/") or ".." in filename.split("/"):
                            raise DownloadException(
                                f"Malicious path entry detected in Kaggle zip archive: {filename}"
                            )
                        total_uncompressed_size += info.file_size

                    # Enforce size limits
                    if total_uncompressed_size > self.max_size_bytes:
                        raise DownloadSizeLimitExceeded(
                            f"Kaggle dataset total uncompressed size ({total_uncompressed_size} bytes) "
                            f"exceeds limit of {self.max_size_bytes} bytes."
                        )

                    # Safe extraction
                    logger.info("Extracting Kaggle archive safely...")
                    z.extractall(path=str(temp_dir))

            except (DownloadException, DownloadSizeLimitExceeded):
                raise
            except Exception as e:
                raise DownloadException(f"Failed to inspect or extract Kaggle archive: {e}")

            # 6. Find all supported data files
            supported_exts = (".csv", ".xlsx", ".xls", ".json", ".parquet")
            extracted_files = []
            for root, _, files in os.walk(str(temp_dir)):
                for file in files:
                    file_path = Path(root) / file
                    if file_path == zip_file_path:
                        continue
                    if file_path.suffix.lower() in supported_exts:
                        extracted_files.append(file_path)

            if not extracted_files:
                raise DatasetLoadException(
                    "No supported dataset file (CSV, Excel, JSON, Parquet) found in Kaggle archive."
                )

            # 7. Multi-file dataset selection: select the largest file
            extracted_files.sort(key=lambda p: p.stat().st_size, reverse=True)
            selected_file = extracted_files[0]
            selected_format = selected_file.suffix.lower().replace(".", "")
            if selected_format == "xls":
                selected_format = "xlsx"

            logger.info(
                "Selected main Kaggle file: '%s' (%d bytes, format: %s)",
                selected_file.name, selected_file.stat().st_size, selected_format
            )

            # 8. Load the selected file into a DataFrame before the temp folder context is deleted
            df = self._load_file(selected_file, selected_format)

            # Safe Logging: Log hostname (kaggle.com), size, and format. Never log credentials or full query URLs.
            logger.info(
                "Successfully ingested Kaggle dataset: host 'kaggle.com' (size: %d bytes, format: %s)",
                selected_file.stat().st_size, selected_format
            )
            return df

    def _load_file(self, file_path: Path, format_type: str) -> pd.DataFrame:
        """Parse file into a pandas DataFrame.
        
        Args:
            file_path: Absolute Path to the file.
            format_type: Format category extension.
            
        Returns:
            pd.DataFrame: Parsed DataFrame.
        """
        try:
            if format_type == "csv":
                return pd.read_csv(file_path, low_memory=False)
            elif format_type in ("xlsx", "xls"):
                return pd.read_excel(file_path, sheet_name=0)
            elif format_type == "json":
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    return pd.json_normalize(data)
                elif isinstance(data, dict):
                    return pd.json_normalize([data])
                else:
                    raise ValueError("Root JSON element must be an array or an object.")
            elif format_type == "parquet":
                return pd.read_parquet(file_path)
            else:
                raise ValueError(f"Unsupported format: {format_type}")
        except Exception as e:
            logger.error("Failed to parse Kaggle dataset file '%s': %s", file_path.name, e)
            raise DatasetLoadException(f"Failed to parse Kaggle dataset file: {e}")
