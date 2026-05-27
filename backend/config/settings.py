"""Application settings loaded from environment variables"""
from pathlib import Path
from pydantic_settings import BaseSettings
from typing import List

# Absolute path to the backend/ directory
BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    # LLM API Keys
    GROQ_API_KEY: str = ""
    GOOGLE_API_KEY: str = ""

    # Model configuration
    PRIMARY_MODEL: str = "llama-3.3-70b-versatile"
    BACKUP_MODEL: str = "gemini-1.5-flash"
    TEMPERATURE: float = 0.1

    # Storage — absolute path so it works regardless of CWD
    STORAGE_DIR: str = str(BACKEND_DIR / "storage")
    MAX_FILE_SIZE_MB: int = 100

    # CORS origins allowed
    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
    ]

    class Config:
        # Try root .env first, then backend .env
        env_file = [str(BACKEND_DIR.parent / ".env"), str(BACKEND_DIR / ".env")]
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
