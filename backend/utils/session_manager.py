"""File-based session manager — isolates sessions by user ID (uid) with Parquet storage"""
from __future__ import annotations
import os
import uuid
import shutil
import logging
from pathlib import Path

import pandas as pd
from fastapi import HTTPException

logger = logging.getLogger(__name__)


class SessionManager:
    def __init__(self, storage_dir: str = "storage"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        logger.info("SessionManager ready at %s", self.storage_dir.resolve())

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    def create_session(self, uid: str) -> str:
        """Generate a new session ID and create its directory under the user's UID."""
        session_id = str(uuid.uuid4())
        session_path = self._session_path(uid, session_id)
        session_path.mkdir(parents=True, exist_ok=True)
        logger.info("Created session %s for user %s", session_id, uid)
        return session_id

    def session_exists(self, uid: str, session_id: str) -> bool:
        return self._session_path(uid, session_id).exists()

    def cleanup_session(self, uid: str, session_id: str) -> None:
        path = self._session_path(uid, session_id)
        if path.exists():
            shutil.rmtree(path)
            logger.info("Cleaned up session %s for user %s", session_id, uid)

    # ------------------------------------------------------------------
    # DataFrame persistence
    # ------------------------------------------------------------------

    def save_dataframe(self, uid: str, session_id: str, df: pd.DataFrame) -> None:
        """Persist a DataFrame as Parquet (preserves dtypes perfectly)."""
        self._ensure_session(uid, session_id)
        parquet_path = self._data_path(uid, session_id)
        # Try pyarrow first, fall back to fastparquet
        try:
            df.to_parquet(parquet_path, index=False, engine="pyarrow")
        except Exception:
            df.to_parquet(parquet_path, index=False, engine="fastparquet")
        logger.debug("Saved %d×%d df to %s", len(df), len(df.columns), parquet_path)

    def load_dataframe(self, uid: str, session_id: str) -> pd.DataFrame:
        """Load the session DataFrame from Parquet."""
        self._ensure_session(uid, session_id)
        parquet_path = self._data_path(uid, session_id)
        if not parquet_path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"No dataset found for session '{session_id}'. Please upload a file first.",
            )
        # Try pyarrow first, fall back to fastparquet
        try:
            return pd.read_parquet(parquet_path, engine="pyarrow")
        except Exception:
            return pd.read_parquet(parquet_path, engine="fastparquet")

    def get_data_path(self, uid: str, session_id: str) -> str:
        """Return the string path to the session's Parquet file."""
        return str(self._data_path(uid, session_id))

    # ------------------------------------------------------------------
    # Private helpers
    def create_backup_if_not_exists(self, uid: str, session_id: str) -> None:
        """Create a backup of the original data.parquet if data_orig.parquet doesn't exist."""
        data_file = self._data_path(uid, session_id)
        backup_file = self._session_path(uid, session_id) / "data_orig.parquet"
        if data_file.exists() and not backup_file.exists():
            shutil.copy2(data_file, backup_file)
            logger.info("Created backup data_orig.parquet for session %s", session_id)

    def restore_backup(self, uid: str, session_id: str) -> bool:
        """Restore data.parquet from data_orig.parquet. Returns True if restored, False if no backup existed."""
        backup_file = self._session_path(uid, session_id) / "data_orig.parquet"
        data_file = self._data_path(uid, session_id)
        if backup_file.exists():
            shutil.copy2(backup_file, data_file)
            logger.info("Restored data.parquet from backup for session %s", session_id)
            return True
        return False

    # ------------------------------------------------------------------

    def _session_path(self, uid: str, session_id: str) -> Path:
        return self.storage_dir / uid / session_id

    def _data_path(self, uid: str, session_id: str) -> Path:
        return self._session_path(uid, session_id) / "data.parquet"

    def _ensure_session(self, uid: str, session_id: str) -> None:
        if not self.session_exists(uid, session_id):
            raise HTTPException(
                status_code=404,
                detail=f"Session '{session_id}' not found. Please upload a file first.",
            )


# Singleton instance used across routers
from config.settings import settings
session_manager = SessionManager(storage_dir=settings.STORAGE_DIR)
