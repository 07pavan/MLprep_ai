"""
Unit tests for the HTTP dataset downloader service (services/http_dataset_downloader.py).
Tests streaming chunks, file-type detection, size constraints, and error propagation.
"""
import pytest
import os
import httpx
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock

from services.http_dataset_downloader import (
    download_dataset,
    DownloadException,
    DownloadSizeLimitExceeded,
    MAX_DATASET_SIZE_BYTES
)
from utils.url_validator import UnsafeURLException, InvalidURLException


def _setup_mock_client(mock_response) -> MagicMock:
    """Helper to configure httpx.AsyncClient async context manager mocks."""
    mock_client = MagicMock()
    
    # Mock stream context: async with client.stream(...) as response
    mock_stream_ctx = MagicMock()
    mock_stream_ctx.__aenter__ = AsyncMock(return_value=mock_response)
    mock_stream_ctx.__aexit__ = AsyncMock(return_value=None)
    mock_client.stream.return_value = mock_stream_ctx
    
    # Mock client context: async with httpx.AsyncClient(...) as client
    mock_client_ctx = MagicMock()
    mock_client_ctx.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client_ctx.__aexit__ = AsyncMock(return_value=None)
    
    return mock_client_ctx


@pytest.mark.anyio
async def test_successful_streaming_download():
    """Verify that a normal file downloads and writes to a temporary file successfully."""
    url = "https://example.com/data/salaries.csv"
    chunk_data = b"id,name,salary\n1,Alice,120000\n2,Bob,95000\n"

    # Mock response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.headers = {"Content-Length": str(len(chunk_data)), "Content-Type": "text/csv"}
    
    # Mock iter_bytes to stream the chunk
    async def mock_iter_bytes(*args, **kwargs):
        yield chunk_data

    mock_response.iter_bytes = mock_iter_bytes
    mock_client_ctx = _setup_mock_client(mock_response)

    # Patch URL safety check (to bypass DNS resolution) and httpx AsyncClient
    with patch("services.http_dataset_downloader.validate_url_safety") as mock_validate, \
         patch("httpx.AsyncClient", return_value=mock_client_ctx):
         
         temp_path, fmt, size = await download_dataset(url)
         
         try:
             # Verify URL validation was called
             mock_validate.assert_called_once_with(url)
             
             # Verify returns
             assert temp_path.exists()
             assert fmt == "csv"
             assert size == len(chunk_data)
             
             # Verify temp file content
             content = temp_path.read_bytes()
             assert content == chunk_data
         finally:
             if temp_path.exists():
                 os.remove(temp_path)


@pytest.mark.anyio
async def test_content_length_exceeded_raises_immediately():
    """Verify that Content-Length header exceeding limit rejects download immediately."""
    url = "https://example.com/big_file.parquet"
    exceeded_size = MAX_DATASET_SIZE_BYTES + 1024

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.headers = {"Content-Length": str(exceeded_size)}
    mock_client_ctx = _setup_mock_client(mock_response)

    with patch("services.http_dataset_downloader.validate_url_safety"), \
         patch("httpx.AsyncClient", return_value=mock_client_ctx):
         
         with pytest.raises(DownloadSizeLimitExceeded) as exc:
             await download_dataset(url)
         
         assert "exceeds limit" in str(exc.value)


@pytest.mark.anyio
async def test_stream_limit_exceeded_mid_stream_and_cleanup():
    """Verify that a stream exceeding size limit raises error and cleans up temp file."""
    url = "https://example.com/infinite_stream.json"
    
    mock_response = MagicMock()
    mock_response.status_code = 200
    # No Content-Length header
    mock_response.headers = {"Content-Type": "application/json"}
    
    # Mock chunks exceeding MAX_DATASET_SIZE_BYTES
    async def mock_iter_bytes(*args, **kwargs):
        # First chunk is within limit
        yield b"["
        # Second chunk exceeds limit
        yield b"0" * (MAX_DATASET_SIZE_BYTES + 100)

    mock_response.iter_bytes = mock_iter_bytes
    mock_client_ctx = _setup_mock_client(mock_response)

    with patch("services.http_dataset_downloader.validate_url_safety"), \
         patch("httpx.AsyncClient", return_value=mock_client_ctx), \
         patch("tempfile.NamedTemporaryFile") as mock_temp:
         
         # Return a real NamedTemporaryFile but mock the path to inspect deletion
         from tempfile import NamedTemporaryFile
         real_temp = NamedTemporaryFile(delete=False)
         mock_temp.return_value = real_temp
         temp_path = Path(real_temp.name)
         
         try:
             with pytest.raises(DownloadSizeLimitExceeded) as exc:
                 await download_dataset(url)
             
             assert "exceeded maximum allowed limit" in str(exc.value)
             # Verify the file was cleaned up/deleted
             assert not temp_path.exists()
         finally:
             if temp_path.exists():
                 os.remove(temp_path)


@pytest.mark.anyio
async def test_non_200_status_raises_error():
    """Verify that a non-200 HTTP response raises a DownloadException."""
    url = "https://example.com/missing.xlsx"

    mock_response = MagicMock()
    mock_response.status_code = 444  # Custom server error
    mock_client_ctx = _setup_mock_client(mock_response)

    with patch("services.http_dataset_downloader.validate_url_safety"), \
         patch("httpx.AsyncClient", return_value=mock_client_ctx):
         
         with pytest.raises(DownloadException) as exc:
             await download_dataset(url)
         assert "non-200" in str(exc.value)


@pytest.mark.anyio
async def test_ssrf_safety_error_propagation():
    """Verify that SSRF validator errors are propagated directly."""
    url = "http://localhost/private.csv"

    with patch("services.http_dataset_downloader.validate_url_safety", side_effect=UnsafeURLException("SSRF")):
        with pytest.raises(UnsafeURLException):
            await download_dataset(url)
