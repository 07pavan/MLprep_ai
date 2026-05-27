"""File-based session manager — each session gets its own directory with Parquet storage"""
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

    def create_session(self) -> str:
        """Generate a new session ID and create its directory."""
        session_id = str(uuid.uuid4())
        session_path = self._session_path(session_id)
        session_path.mkdir(parents=True, exist_ok=True)
        logger.info("Created session %s", session_id)
        return session_id

    def session_exists(self, session_id: str) -> bool:
        return self._session_path(session_id).exists()

    def cleanup_session(self, session_id: str) -> None:
        path = self._session_path(session_id)
        if path.exists():
            shutil.rmtree(path)
            logger.info("Cleaned up session %s", session_id)

    # ------------------------------------------------------------------
    # DataFrame persistence
    # ------------------------------------------------------------------

    def save_dataframe(self, session_id: str, df: pd.DataFrame) -> None:
        """Persist a DataFrame as Parquet (preserves dtypes perfectly)."""
        self._ensure_session(session_id)
        parquet_path = self._data_path(session_id)
        df.to_parquet(parquet_path, index=False)
        logger.debug("Saved %d×%d df to %s", len(df), len(df.columns), parquet_path)

    def load_dataframe(self, session_id: str) -> pd.DataFrame:
        """Load the session DataFrame from Parquet."""
        self._ensure_session(session_id)
        parquet_path = self._data_path(session_id)
        if not parquet_path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"No dataset found for session '{session_id}'. Please upload a file first.",
            )
        return pd.read_parquet(parquet_path)

    def get_data_path(self, session_id: str) -> str:
        """Return the string path to the session's Parquet file."""
        return str(self._data_path(session_id))

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _session_path(self, session_id: str) -> Path:
        return self.storage_dir / session_id

    def _data_path(self, session_id: str) -> Path:
        return self._session_path(session_id) / "data.parquet"

    def _ensure_session(self, session_id: str) -> None:
        if not self.session_exists(session_id):
            raise HTTPException(
                status_code=404,
                detail=f"Session '{session_id}' not found. Please upload a file first.",
            )


# Singleton instance used across routers
session_manager = SessionManager()
