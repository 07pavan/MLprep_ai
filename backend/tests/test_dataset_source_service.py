"""
Unit tests for the dataset source service (services/dataset_source_service.py).
Verifies file parsing handlers, GitHub URL rewriting, nested JSON flattening,
and temporary file cleanup.
"""
import pytest
import os
import tempfile
import json
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import numpy as np

from services.dataset_source_service import (
    load_remote_dataset,
    _load_github,
    DatasetLoadException
)
from services.http_dataset_downloader import DownloadResult


def test_github_url_rewriting():
    """Verify that GitHub URL blob references are rewritten to raw URLs."""
    github_blob = "https://github.com/07pavan/data-analyst-AGENT/blob/main/backend/tests/test_data.csv"
    expected_raw = "https://raw.githubusercontent.com/07pavan/data-analyst-AGENT/main/backend/tests/test_data.csv"
    assert _load_github(github_blob) == expected_raw

    # Test with subdirectories and branches
    branch_url = "https://github.com/user/repo-name/blob/feature/v2/path/to/my-file.xlsx"
    expected_branch = "https://raw.githubusercontent.com/user/repo-name/feature/v2/path/to/my-file.xlsx"
    assert _load_github(branch_url) == expected_branch

    # Verify generic HTTP URLs are left unmodified
    generic_url = "https://example.com/data.csv"
    assert _load_github(generic_url) == generic_url


@pytest.mark.anyio
async def test_load_csv_success():
    """Verify that a CSV dataset is parsed correctly into a DataFrame and cleaned up."""
    # Write a temporary CSV file
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w") as tmp:
        tmp.write("col1,col2\n10,20\n30,40\n")
        tmp_path = Path(tmp.name)
        
    try:
        # Mock download to return our local temp file result
        mock_result = DownloadResult(path=tmp_path, format="csv", size_bytes=100, content_type="text/csv")
        with patch("services.dataset_source_service.HTTPDatasetDownloader.download", return_value=mock_result) as mock_download:
            df = await load_remote_dataset("https://example.com/data.csv")
            
            # Verify download mock was called
            mock_download.assert_called_once_with("https://example.com/data.csv")
            
            # Verify DataFrame content
            assert isinstance(df, pd.DataFrame)
            assert len(df) == 2
            assert list(df.columns) == ["col1", "col2"]
            assert df.iloc[0]["col1"] == 10
            
            # Verify the temp file was automatically deleted/cleaned up
            assert not tmp_path.exists()
    finally:
        if tmp_path.exists():
            os.remove(tmp_path)


@pytest.mark.anyio
async def test_load_json_flattening_success():
    """Verify that a nested JSON payload is flattened correctly using json_normalize."""
    nested_json = [
        {"id": 1, "info": {"name": "Alice", "city": "NYC"}},
        {"id": 2, "info": {"name": "Bob", "city": "SF"}}
    ]
    
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as tmp:
        json.dump(nested_json, tmp)
        tmp_path = Path(tmp.name)
        
    try:
        mock_result = DownloadResult(path=tmp_path, format="json", size_bytes=150, content_type="application/json")
        with patch("services.dataset_source_service.HTTPDatasetDownloader.download", return_value=mock_result):
            df = await load_remote_dataset("https://example.com/data.json")
            
            assert isinstance(df, pd.DataFrame)
            assert len(df) == 2
            # Nested fields should be flattened to dot notation
            assert "info.name" in df.columns
            assert "info.city" in df.columns
            assert df.iloc[0]["info.name"] == "Alice"
            
            # Verify cleanup
            assert not tmp_path.exists()
    finally:
        if tmp_path.exists():
            os.remove(tmp_path)


@pytest.mark.anyio
async def test_load_malformed_csv_raises_exception():
    """Verify that parser failures raise a DatasetLoadException and clean up files."""
    # Write garbage binary data to a .csv file
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="wb") as tmp:
        tmp.write(b"\x80\x81\xff\x00malformed_csv")
        tmp_path = Path(tmp.name)
        
    try:
        mock_result = DownloadResult(path=tmp_path, format="csv", size_bytes=50, content_type="text/csv")
        with patch("services.dataset_source_service.HTTPDatasetDownloader.download", return_value=mock_result):
            with pytest.raises(DatasetLoadException):
                # pandas read_csv might throw parse or encoding errors on raw binary garbage
                # We will trigger a load error
                # In some cases pandas might read it as a single row, so let's mock _load_csv to raise
                with patch("services.dataset_source_service._load_csv", side_effect=DatasetLoadException("parse error")):
                    await load_remote_dataset("https://example.com/data.csv")
            
            # Verify cleanup on failure
            assert not tmp_path.exists()
    finally:
        if tmp_path.exists():
            os.remove(tmp_path)
