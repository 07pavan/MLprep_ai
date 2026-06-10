"""Cleaning router — data quality reports and cleaning operations"""
from __future__ import annotations
import logging

from fastapi import APIRouter, HTTPException, Query, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import io

from agents.cleaner import DataCleanerAgent
from utils.session_manager import session_manager
from utils.auth import verify_firebase_token

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["Cleaning"])

cleaner = DataCleanerAgent()


class CleanRequest(BaseModel):
    sessionId: str
    options: dict


@router.get("/clean/report")
async def get_cleaning_report(
    sessionId: str = Query(...),
    user: dict = Depends(verify_firebase_token)
):
    """Return a data quality report for the session's dataset."""
    df = session_manager.load_dataframe(user["uid"], sessionId)
    report = cleaner.get_cleaning_report(df)
    suggestions = cleaner.suggest_cleaning_steps(df)
    return {
        "report": report,
        "suggestedDefaults": suggestions,
    }


@router.post("/clean")
async def apply_cleaning(
    req: CleanRequest,
    user: dict = Depends(verify_firebase_token)
):
    """Apply cleaning operations and persist the cleaned dataset."""
    df = session_manager.load_dataframe(user["uid"], req.sessionId)
    rows_before = len(df)
    cols_before = len(df.columns)

    cleaned_df, change_log = cleaner.clean(df, req.options)

    # Persist cleaned version
    session_manager.save_dataframe(user["uid"], req.sessionId, cleaned_df)

    return {
        "success": True,
        "changeLog": change_log,
        "metrics": {
            "rowsBefore": rows_before,
            "rowsAfter": len(cleaned_df),
            "colsBefore": cols_before,
            "colsAfter": len(cleaned_df.columns),
        },
    }


@router.get("/clean/download")
async def download_cleaned(
    sessionId: str = Query(...),
    user: dict = Depends(verify_firebase_token)
):
    """Download the current session dataset as CSV."""
    df = session_manager.load_dataframe(user["uid"], sessionId)
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    buf.seek(0)

    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=cleaned_data.csv"},
    )
