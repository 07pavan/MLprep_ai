"""
Generic HTTP dataset downloader service.
Downloads datasets from a remote URL safely using streaming chunks.
Enforces size limit, timeouts, and SSRF validation.
"""
from __future__ import annotations
import os
import logging
import tempfile
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse
from typing import Optional, Tuple

import httpx

from config.settings import settings
from utils.url_validator import validate_url_safety, InvalidURLException, UnsafeURLException

logger = logging.getLogger(__name__)

# Enforce maximum dataset size limit from settings (or fallback to 100 MB)
MAX_DATASET_SIZE_BYTES = settings.MAX_FILE_SIZE_MB * 1024 * 1024


class DownloadException(Exception):
    """Base download failure."""
    pass


class DownloadSizeLimitExceeded(DownloadException):
    """Raised when dataset exceeds configured size limit."""
    pass


@dataclass
class DownloadResult:
    """Dataclass holding downloaded dataset file properties and metadata."""
    path: Path
    format: str
    size_bytes: int
    content_type: Optional[str]


class HTTPDatasetDownloader:
    """Service class responsible for downloading datasets over HTTP/HTTPS safely."""

    def __init__(self, storage_dir: Optional[str] = None):
        """Initialize downloader with storage options and size limits.
        
        Args:
            storage_dir: Custom target directory for writing temporary files.
        """
        self.storage_dir = storage_dir or settings.STORAGE_DIR
        self.max_size_bytes = MAX_DATASET_SIZE_BYTES
        self.connect_timeout = 10.0
        self.read_timeout = 60.0
        self.max_connections = 10
        self.chunk_size = 64 * 1024  # 64 KB chunks

    def _detect_format(self, url: str, content_type: Optional[str]) -> str:
        """Detect dataset format from URL suffix or Content-Type header.
        
        Supports: csv, xlsx, json, parquet.
        Raises DownloadException if format is unknown.
        """
        parsed_path = urlparse(url).path
        ext = Path(parsed_path).suffix.lower()

        # 1. Detect from extension
        if ext in (".csv", ".txt"):
            return "csv"
        elif ext in (".xlsx", ".xls"):
            return "xlsx"
        elif ext in (".json",):
            return "json"
        elif ext in (".parquet",):
            return "parquet"

        # 2. Detect from Content-Type
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

        # If format cannot be identified, raise DownloadException
        raise DownloadException(
            f"Unsupported or unknown file format. Content-Type: {content_type}, Extension: {ext}"
        )

    async def download(self, url: str) -> DownloadResult:
        """Download remote dataset using a safe streaming GET request.
        
        Args:
            url: Absolute remote dataset target URL.
            
        Returns:
            DownloadResult: Downloaded file path and metadata attributes.
            
        Raises:
            InvalidURLException / UnsafeURLException: SSRF safety violations.
            DownloadSizeLimitExceeded: File exceeds maximum allowed size.
            DownloadException: Client/network errors, filesystem errors, or non-200 responses.
        """
        # 1. Validate URL safety (SSRF protection) before making any HTTP request
        safe_url = validate_url_safety(url)
        if not isinstance(safe_url, str):
            safe_url = url
        hostname = urlparse(safe_url).hostname or "unknown-host"

        # 2. Setup client limits and timeouts
        limits = httpx.Limits(max_keepalive_connections=5, max_connections=self.max_connections)
        timeout = httpx.Timeout(connect=self.connect_timeout, read=self.read_timeout, write=10.0, pool=10.0)

        try:
            async with httpx.AsyncClient(limits=limits, timeout=timeout, follow_redirects=True) as client:
                async with client.stream("GET", safe_url) as response:
                    if response.status_code != 200:
                        raise DownloadException(
                            f"Server returned non-200 status code: {response.status_code}"
                        )

                    # 3. Check Content-Length header upfront
                    content_length_str = response.headers.get("Content-Length")
                    if content_length_str:
                        try:
                            content_length = int(content_length_str)
                            if content_length > self.max_size_bytes:
                                raise DownloadSizeLimitExceeded(
                                    f"Content-Length ({content_length} bytes) exceeds limit of {self.max_size_bytes} bytes."
                                )
                        except ValueError:
                            # If Content-Length header value is malformed, ignore and fall back to stream counting
                            pass

                    # 4. Detect format (raises DownloadException if unknown)
                    content_type = response.headers.get("Content-Type")
                    detected_format = self._detect_format(safe_url, content_type)

                    # 5. Create temporary file
                    suffix = f".{detected_format}"
                    try:
                        temp_file = tempfile.NamedTemporaryFile(dir=self.storage_dir, delete=False, suffix=suffix)
                        temp_path = Path(temp_file.name)
                    except OSError as e:
                        logger.error("Failed to create temporary file: %s", e)
                        raise DownloadException(f"Filesystem error: could not create temporary file. {e}")

                    # 6. Stream chunks and dynamically count bytes
                    bytes_downloaded = 0
                    try:
                        with temp_file as f:
                            async for chunk in response.iter_bytes(chunk_size=self.chunk_size):
                                bytes_downloaded += len(chunk)
                                if bytes_downloaded > self.max_size_bytes:
                                    raise DownloadSizeLimitExceeded(
                                        f"Streaming data exceeded maximum allowed limit of {self.max_size_bytes} bytes."
                                    )
                                f.write(chunk)
                    except Exception:
                        # Ensure cleanup of partially written file on stream failure
                        if temp_path.exists():
                            try:
                                os.remove(temp_path)
                            except OSError:
                                pass
                        raise

                    # 7. Safe Logging: hostname, size, format only. Never log full URLs or query parameters.
                    logger.info(
                        "Successfully downloaded dataset from host '%s' (size: %d bytes, format: %s)",
                        hostname, bytes_downloaded, detected_format
                    )

                    return DownloadResult(
                        path=temp_path,
                        format=detected_format,
                        size_bytes=bytes_downloaded,
                        content_type=content_type
                    )

        except httpx.TimeoutException as e:
            logger.error("Download timeout contacting host '%s': %s", hostname, e)
            raise DownloadException(f"Connection or read timeout contacting host: {e}")
        except httpx.NetworkError as e:
            logger.error("Network connection error contacting host '%s': %s", hostname, e)
            raise DownloadException(f"Network error contacting host: {e}")
        except (InvalidURLException, UnsafeURLException):
            # Propagate security and validation errors directly
            raise
        except Exception as e:
            if isinstance(e, DownloadException):
                raise
            logger.error("Unexpected error downloading from host '%s': %s", hostname, e, exc_info=True)
            raise DownloadException(f"An unexpected download error occurred: {e}")
