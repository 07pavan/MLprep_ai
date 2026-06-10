"""Application settings loaded from environment variables"""
from pathlib import Path
from pydantic_settings import BaseSettings
from typing import List

# Absolute path to the backend/ directory
BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    # ── LLM API Keys ──────────────────────────────────────────────
    GROQ_API_KEY: str = ""
    GOOGLE_API_KEY: str = ""
    DATABASE_URL: str = ""

    # ── Firebase/Firestore ────────────────────────────────────────
    FIREBASE_PROJECT_ID: str = ""
    GOOGLE_APPLICATION_CREDENTIALS: str = ""

    # ── Multi-Model Router ────────────────────────────────────────
    # "fast" tier — cheap, low-latency (intent classification, insights, summaries)
    # Using Groq llama-3.1-8b-instant (free tier, fast) instead of Google gemini-1.5-flash
    # which has been deprecated. Switch to "google" + "gemini-2.0-flash" if you have
    # a paid Google AI Studio key.
    FAST_MODEL: str = "llama-3.1-8b-instant"
    FAST_PROVIDER: str = "groq"             # "groq" or "google"

    # "smart" tier — high-reasoning (pandas code gen, Vega-Lite specs)
    SMART_MODEL: str = "llama-3.3-70b-versatile"
    SMART_PROVIDER: str = "groq"            # "groq" or "google"

    TEMPERATURE: float = 0.1
    LLM_TIMEOUT: int = 30               # seconds per LLM call

    # ── Storage ───────────────────────────────────────────────────
    STORAGE_DIR: str = str(BACKEND_DIR / "storage")
    MAX_FILE_SIZE_MB: int = 100

    # ── CORS ──────────────────────────────────────────────────────
    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
    ]

    class Config:
        env_file = [str(BACKEND_DIR.parent / ".env"), str(BACKEND_DIR / ".env")]
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
