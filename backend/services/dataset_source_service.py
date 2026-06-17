"""
Dataset source service.
Resolves remote urls (including GitHub blob views), downloads datasets safely,
and parses/flattens them into pandas DataFrames.
Clean up temporary files after loading is complete to prevent storage leaks.
"""
from __future__ import annotations
import os
import re
import json
import logging
from pathlib import Path

import pandas as pd

from services.http_dataset_downloader import HTTPDatasetDownloader

logger = logging.getLogger(__name__)


class DatasetLoadException(Exception):
    """Exception raised when parsing or loading a downloaded dataset into a DataFrame fails."""
    pass


def _load_csv(file_path: Path) -> pd.DataFrame:
    """Load a CSV file into a pandas DataFrame."""
    try:
        # csv files might contain mixed types or encoding issues; low_memory=False resolves mixed types warnings
        return pd.read_csv(file_path, low_memory=False)
    except Exception as e:
        logger.error("Failed to parse CSV file: %s", e)
        raise DatasetLoadException(f"Failed to parse CSV file: {e}")


def _load_excel(file_path: Path) -> pd.DataFrame:
    """Load an Excel spreadsheet (.xlsx/.xls) into a pandas DataFrame.
    
    Selects the first worksheet by default to handle multi-sheet ambiguity.
    """
    try:
        # sheet_name=0 selects the first sheet initially
        return pd.read_excel(file_path, sheet_name=0)
    except Exception as e:
        logger.error("Failed to parse Excel file: %s", e)
        raise DatasetLoadException(f"Failed to parse Excel file: {e}")


def _load_json(file_path: Path) -> pd.DataFrame:
    """Load and flatten a JSON file/payload into a pandas DataFrame.
    
    Flattens nested JSON structures using pandas.json_normalize().
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, list):
            # Normal list of dicts, flatten nested fields
            return pd.json_normalize(data)
        elif isinstance(data, dict):
            # Single JSON object, normalize into a single-row DataFrame
            return pd.json_normalize([data])
        else:
            raise ValueError("Root JSON element must be an array or an object.")
    except Exception as e:
        logger.error("Failed to parse or flatten JSON: %s", e)
        raise DatasetLoadException(f"Failed to parse or flatten JSON: {e}")


def _load_parquet(file_path: Path) -> pd.DataFrame:
    """Load a Parquet columnar file into a pandas DataFrame."""
    try:
        return pd.read_parquet(file_path)
    except Exception as e:
        logger.error("Failed to parse Parquet file: %s", e)
        raise DatasetLoadException(f"Failed to parse Parquet file: {e}")


def _load_github(url: str) -> str:
    """Detect and convert GitHub web viewer URLs into direct raw URLs.
    
    e.g. converts:
      https://github.com/user/repo/blob/main/dir/data.csv
    into:
      https://raw.githubusercontent.com/user/repo/main/dir/data.csv
    """
    github_blob_pattern = r"^https?://(?:www\.)?github\.com/([^/]+)/([^/]+)/blob/([^/]+)/(.+)$"
    match = re.match(github_blob_pattern, url)
    if match:
        owner, repo, branch, filepath = match.groups()
        raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{filepath}"
        logger.info("Rewrote GitHub blob URL to raw URL: '%s' -> '%s'", url, raw_url)
        return raw_url
    return url


async def load_remote_dataset(url: str, storage_dir: str | None = None) -> pd.DataFrame:
    """Download a dataset from a remote URL, detect format, and load into a pandas DataFrame.
    
    SSRF security checks and file size limits are enforced during download.
    Clean up temporary file spooling automatically after loading to memory.
    
    Args:
        url: The absolute target URL (supporting generic HTTP, JSON APIs, and GitHub links).
        storage_dir: Optional location to write the temporary file.
        
    Returns:
        pd.DataFrame: The parsed and populated pandas DataFrame.
        
    Raises:
        InvalidURLException: URL scheme or format is invalid.
        UnsafeURLException: URL hostname resolves to forbidden IP subnets (SSRF).
        DownloadException: Network or timeout errors during download.
        DatasetLoadException: Parsing, flattening, or file format load failures.
    """
    # 1. Preprocess and resolve GitHub URLs to raw content
    resolved_url = _load_github(url)

    # Detect Kaggle dataset URLs (e.g. kaggle.com/datasets/owner/dataset)
    if "kaggle.com/datasets/" in resolved_url.lower():
        from services.kaggle_connector import KaggleConnector
        connector = KaggleConnector()
        return await connector.download_dataset(resolved_url)

    # 2. Download remote file to a safe, validated temporary file
    downloader = HTTPDatasetDownloader(storage_dir=storage_dir)
    result = await downloader.download(resolved_url)
    temp_path = result.path
    detected_format = result.format

    # 3. Load DataFrame based on detected format
    try:
        if detected_format == "csv":
            df = _load_csv(temp_path)
        elif detected_format == "xlsx":
            df = _load_excel(temp_path)
        elif detected_format == "json":
            df = _load_json(temp_path)
        elif detected_format == "parquet":
            df = _load_parquet(temp_path)
        else:
            raise DatasetLoadException(f"Unsupported parsed format: {detected_format}")

        logger.info(
            "Successfully loaded dataset from URL: '%s' into %d×%d DataFrame",
            resolved_url, len(df), len(df.columns)
        )
        return df

    finally:
        # 4. Critical cleanup: ensure the temporary downloaded file is removed to prevent disk leakage
        if temp_path.exists():
            try:
                os.remove(temp_path)
                logger.debug("Cleaned up temporary download file: %s", temp_path)
            except OSError as e:
                logger.warning("Failed to remove temporary file %s: %s", temp_path, e)
