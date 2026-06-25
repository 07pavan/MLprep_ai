import pytest
import os
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch
from config.settings import settings

def test_run_midnight_cleanup_preserves_firebase_key():
    # Setup temporary storage directory
    temp_storage = Path("temp_test_storage")
    temp_storage.mkdir(exist_ok=True)
    
    # Create some dummy files and directories
    (temp_storage / "user1").mkdir(exist_ok=True)
    (temp_storage / "user1" / "session1").mkdir(parents=True, exist_ok=True)
    (temp_storage / "user1" / "session1" / "data.parquet").write_text("dummy content")
    (temp_storage / "firebase-key.json").write_text("secret key content")
    (temp_storage / "some_random_file.txt").write_text("random")
    
    # Mock settings.STORAGE_DIR
    with patch.object(settings, "STORAGE_DIR", str(temp_storage)):
        # Mock get_dataset_service
        mock_service = MagicMock()
        mock_service.delete_all_datasets = MagicMock()
        
        with patch("services.dataset_service.get_dataset_service", return_value=mock_service):
            from main import run_midnight_cleanup
            
            run_midnight_cleanup()
            
            # Verify DB delete_all_datasets was called
            mock_service.delete_all_datasets.assert_called_once()
            
            # Verify firebase-key.json is preserved
            assert (temp_storage / "firebase-key.json").exists()
            assert (temp_storage / "firebase-key.json").read_text() == "secret key content"
            
            # Verify other files and directories are deleted
            assert not (temp_storage / "user1").exists()
            assert not (temp_storage / "some_random_file.txt").exists()
            
    # Cleanup temp_storage
    shutil.rmtree(temp_storage, ignore_errors=True)
