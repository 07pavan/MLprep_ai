"""
Unit tests for the Kaggle dataset connector (services/kaggle_connector.py).
Tests URL parsing/slug extraction, credential validation, mock API interactions,
zip bomb protection, path traversal blocks, and dataframe parsing.
"""
import os
# Set dummy credentials before importing kaggle or connector to prevent exit(1) on import
os.environ["KAGGLE_USERNAME"] = "dummy_user"
os.environ["KAGGLE_KEY"] = "dummy_key"

import pytest
import zipfile
import tempfile
import pandas as pd
from pathlib import Path
from unittest.mock import patch, MagicMock

from config.settings import settings
from services.kaggle_connector import KaggleConnector
from services.dataset_source_service import load_remote_dataset, DatasetLoadException
from services.http_dataset_downloader import DownloadException, DownloadSizeLimitExceeded


def test_slug_extraction():
    """Verify that Kaggle URLs are parsed correctly into owner/dataset slugs."""
    connector = KaggleConnector()
    
    url = "https://www.kaggle.com/datasets/uciml/iris"
    assert connector._extract_slug(url) == "uciml/iris"
    
    url_with_query = "https://www.kaggle.com/datasets/owner/dataset-name?search=query#fragment"
    assert connector._extract_slug(url_with_query) == "owner/dataset-name"

    url_http = "http://kaggle.com/datasets/owner-name/dataset-123"
    assert connector._extract_slug(url_http) == "owner-name/dataset-123"

    invalid_url = "https://example.com/not/kaggle"
    with pytest.raises(DownloadException) as exc:
        connector._extract_slug(invalid_url)
    assert "Invalid Kaggle dataset URL structure" in str(exc.value)


@pytest.mark.anyio
async def test_download_without_credentials_raises_exception():
    """Verify that download fails if Kaggle API credentials are not configured."""
    connector = KaggleConnector()
    
    with patch.object(settings, "KAGGLE_USERNAME", ""), \
         patch.object(settings, "KAGGLE_KEY", ""), \
         patch.object(settings, "KAGGLE_API_TOKEN", ""):
        with pytest.raises(DownloadException) as exc:
            await connector.download_dataset("https://www.kaggle.com/datasets/uciml/iris")
        assert "Kaggle credentials" in str(exc.value)


@pytest.mark.anyio
async def test_successful_kaggle_download_and_load():
    """Verify a successful download and loading of a CSV from a Kaggle dataset archive."""
    connector = KaggleConnector()
    
    # 1. Create a dummy zip containing a CSV file
    csv_content = b"a,b,c\n1,2,3\n4,5,6\n"
    
    with tempfile.TemporaryDirectory() as temp_dir:
        zip_path = Path(temp_dir) / "iris.zip"
        with zipfile.ZipFile(zip_path, "w") as z:
            z.writestr("iris.csv", csv_content)
            z.writestr("unrelated.txt", b"plain text files should be ignored")

        # Mock settings credentials
        with patch.object(settings, "KAGGLE_USERNAME", "test_user"), \
             patch.object(settings, "KAGGLE_KEY", "test_key"), \
             patch("kaggle.api.kaggle_api_extended.KaggleApi") as mock_api_class:
            
            # Setup mock API behaviour
            mock_api = MagicMock()
            mock_api_class.return_value = mock_api
            
            # Side effect to copy our dummy zip file into the target directory to simulate Kaggle SDK download
            def mock_download_files(slug, path, unzip, quiet):
                dest_zip = Path(path) / "iris.zip"
                dest_zip.write_bytes(zip_path.read_bytes())

            mock_api.dataset_download_files.side_effect = mock_download_files
            
            # Run download
            df = await connector.download_dataset("https://www.kaggle.com/datasets/uciml/iris")
            
            # Assertions
            assert isinstance(df, pd.DataFrame)
            assert len(df) == 2
            assert list(df.columns) == ["a", "b", "c"]
            assert df.iloc[0]["a"] == 1


@pytest.mark.anyio
async def test_zip_bomb_detection():
    """Verify that Kaggle zip files exceeding MAX_FILE_SIZE_MB trigger a DownloadSizeLimitExceeded exception."""
    connector = KaggleConnector()
    connector.max_size_bytes = 10 * 1024 * 1024  # Force limit to 10MB
    
    mock_zip = MagicMock()
    mock_info = MagicMock()
    mock_info.filename = "large.csv"
    mock_info.file_size = 200 * 1024 * 1024
    mock_zip.infolist.return_value = [mock_info]
    mock_zip.__enter__.return_value = mock_zip

    with patch.object(settings, "KAGGLE_USERNAME", "test_user"), \
         patch.object(settings, "KAGGLE_KEY", "test_key"), \
         patch("kaggle.api.kaggle_api_extended.KaggleApi") as mock_api_class, \
         patch("zipfile.ZipFile", return_value=mock_zip):
         
         with tempfile.TemporaryDirectory() as temp_dir:
             mock_api = MagicMock()
             mock_api_class.return_value = mock_api
             
             def mock_download_files(slug, path, unzip, quiet):
                 dest_zip = Path(path) / "bomb.zip"
                 dest_zip.write_bytes(b"")  # satisfy zip file check

             mock_api.dataset_download_files.side_effect = mock_download_files
             
             with pytest.raises(DownloadSizeLimitExceeded) as exc:
                 await connector.download_dataset("https://www.kaggle.com/datasets/uciml/iris")
             assert "exceeds limit" in str(exc.value)


@pytest.mark.anyio
async def test_path_traversal_prevention():
    """Verify that zip entries referencing directory traversal are rejected as malicious."""
    connector = KaggleConnector()
    
    with tempfile.TemporaryDirectory() as temp_dir:
        zip_path = Path(temp_dir) / "traversal.zip"
        with zipfile.ZipFile(zip_path, "w") as z:
            z.writestr("../malicious_file.csv", b"a,b\n1,2")

        with patch.object(settings, "KAGGLE_USERNAME", "test_user"), \
             patch.object(settings, "KAGGLE_KEY", "test_key"), \
             patch("kaggle.api.kaggle_api_extended.KaggleApi") as mock_api_class:
            
            mock_api = MagicMock()
            mock_api_class.return_value = mock_api
            
            def mock_download_files(slug, path, unzip, quiet):
                dest_zip = Path(path) / "traversal.zip"
                dest_zip.write_bytes(zip_path.read_bytes())

            mock_api.dataset_download_files.side_effect = mock_download_files
            
            with pytest.raises(DownloadException) as exc:
                await connector.download_dataset("https://www.kaggle.com/datasets/uciml/iris")
            assert "Malicious path entry detected" in str(exc.value)


@pytest.mark.anyio
async def test_load_remote_dataset_routing_to_kaggle():
    """Verify that load_remote_dataset automatically routes Kaggle URLs to KaggleConnector."""
    url = "https://www.kaggle.com/datasets/uciml/iris"
    mock_df = pd.DataFrame({"routed": [True]})
    
    # Patch the download_dataset method on KaggleConnector
    with patch("services.kaggle_connector.KaggleConnector.download_dataset", return_value=mock_df) as mock_download:
        df = await load_remote_dataset(url)
        
        mock_download.assert_called_once_with(url)
        assert isinstance(df, pd.DataFrame)
        assert bool(df.iloc[0]["routed"]) is True
