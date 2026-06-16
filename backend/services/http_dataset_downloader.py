"""
Generic HTTP dataset downloader service.
Downloads datasets from a remote URL safely using streaming chunks.
Enforces size limit, timeouts, and SSRF validation.
"""
from __future__ import annotations
import os
import logging
import tempfile
from pathlib import Path
from urllib.parse import urlparse
from typing import Tuple

import httpx

from utils.url_validator import validate_url_safety, InvalidURLException, UnsafeURLException

logger = logging.getLogger(__name__)

# ─── Configuration Constants ──────────────────────────────────────────────────
# Enforce maximum dataset size limit of 100 MB (104,857,600 bytes)
MAX_DATASET_SIZE_BYTES = 100 * 1024 * 1024
# Timouts for connection and reading
CONNECT_TIMEOUT_SEC = 10.0
READ_TIMEOUT_SEC = 60.0
# Chunk size for streaming to file
CHUNK_SIZE = 64 * 1024  # 64 KB


class DownloadException(Exception):
    """Base exception for dataset download operations."""
    pass


class DownloadSizeLimitExceeded(DownloadException):
    """Exception raised when dataset file size exceeds maximum limits."""
    pass


def _detect_format(url: str, content_type: str | None) -> str:
    """Detect dataset format from URL path or Content-Type header.
    
    Supports: csv, xlsx, json, parquet. Defaults to csv if unknown.
    """
    # 1. Detect from URL extension
    parsed_path = urlparse(url).path
    ext = Path(parsed_path).suffix.lower()

    if ext in (".csv", ".txt"):
        return "csv"
    elif ext in (".xlsx", ".xls"):
        return "xlsx"
    elif ext in (".json",):
        return "json"
    elif ext in (".parquet",):
        return "parquet"

    # 2. Detect from Content-Type header
    if content_type:
        content_type = content_type.lower()
        if "csv" in content_type or "text/plain" in content_type:
            return "csv"
        elif "spreadsheet" in content_type or "ms-excel" in content_type or "openxmlformats" in content_type:
            return "xlsx"
        elif "json" in content_type:
            return "json"
        elif "parquet" in content_type or "octet-stream" in content_type:
            return "parquet"

    # Default fallback
    return "csv"


async def download_dataset(url: str, storage_dir: str | None = None) -> Tuple[Path, str, int]:
    """Download a dataset from a URL safely using streaming chunks.
    
    Writes chunks directly to a temporary file on disk to prevent memory spikes.
    
    Args:
        url: The absolute target URL to download.
        storage_dir: Optional target directory for the temporary file.
        
    Returns:
        Tuple[Path, str, int]: (temp_file_path, detected_format, file_size_in_bytes)
        
    Raises:
        InvalidURLException: If URL scheme or syntax is invalid.
        UnsafeURLException: If URL hostname resolves to forbidden IP subnets.
        DownloadSizeLimitExceeded: If Content-Length or stream size exceeds limit.
        DownloadException: For network issues, non-200 responses, or read timeouts.
    """
    # 1. Run SSRF Safety checks (raises Invalid/Unsafe exception)
    validate_url_safety(url)

    # 2. Setup client limits and timeouts
    limits = httpx.Limits(max_keepalive_connections=5, max_connections=10)
    timeout = httpx.Timeout(connect=CONNECT_TIMEOUT_SEC, read=READ_TIMEOUT_SEC, write=10.0, pool=10.0)

    try:
        async with httpx.AsyncClient(limits=limits, timeout=timeout, follow_redirects=True) as client:
            async with client.stream("GET", url) as response:
                if response.status_code != 200:
                    raise DownloadException(
                        f"Server returned non-200 status code: {response.status_code}"
                    )

                # 3. Check Content-Length header upfront
                content_length_str = response.headers.get("Content-Length")
                if content_length_str:
                    try:
                        content_length = int(content_length_str)
                        if content_length > MAX_DATASET_SIZE_BYTES:
                            raise DownloadSizeLimitExceeded(
                                f"Content-Length ({content_length} bytes) exceeds limit of {MAX_DATASET_SIZE_BYTES} bytes."
                            )
                    except ValueError:
                        # If Content-Length is malformed, ignore it and count stream bytes instead
                        pass

                # 4. Detect format
                detected_format = _detect_format(url, response.headers.get("Content-Type"))

                # 5. Create a temporary file to save the streaming chunks
                suffix = f".{detected_format}"
                temp_file = tempfile.NamedTemporaryFile(dir=storage_dir, delete=False, suffix=suffix)
                temp_path = Path(temp_file.name)

                bytes_downloaded = 0
                try:
                    with temp_file as f:
                        async for chunk in response.iter_bytes(chunk_size=CHUNK_SIZE):
                            bytes_downloaded += len(chunk)
                            if bytes_downloaded > MAX_DATASET_SIZE_BYTES:
                                raise DownloadSizeLimitExceeded(
                                    f"Streaming data exceeded maximum allowed limit of {MAX_DATASET_SIZE_BYTES} bytes."
                                )
                            f.write(chunk)
                except Exception:
                    # Clean up the file if an error occurs during download
                    if temp_path.exists():
                        try:
                            os.remove(temp_path)
                        except OSError:
                            pass
                    raise

                logger.info(
                    "Successfully downloaded dataset: '%s' (%d bytes, format: %s) -> %s",
                    url, bytes_downloaded, detected_format, temp_path
                )
                return temp_path, detected_format, bytes_downloaded

    except httpx.HTTPError as e:
        logger.error("Network error during dataset download: %s", e)
        raise DownloadException(f"Failed to fetch dataset from remote host: {e}")
    except (InvalidURLException, UnsafeURLException):
        # Propagate security exceptions directly
        raise
    except Exception as e:
        if isinstance(e, DownloadException):
            raise
        logger.error("Unexpected error downloading dataset: %s", e, exc_info=True)
        raise DownloadException(f"An unexpected download error occurred: {e}")
