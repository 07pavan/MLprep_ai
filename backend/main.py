"""FastAPI application entry point"""
from __future__ import annotations
import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config.settings import settings
from routers.upload import router as upload_router
from routers.chat import router as chat_router
from routers.clean import router as clean_router

# ─── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-7s │ %(name)-25s │ %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ─── App factory ──────────────────────────────────────────────────────────────
app = FastAPI(
    title="AI Data Analyst API",
    version="2.0.0",
    description="FastAPI backend with LangGraph orchestration and Vega-Lite visualization",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ─── CORS ─────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Routers ──────────────────────────────────────────────────────────────────
app.include_router(upload_router)
app.include_router(chat_router)
app.include_router(clean_router)


# ─── Health check ─────────────────────────────────────────────────────────────
@app.get("/health", tags=["System"])
async def health():
    return {
        "status": "ok",
        "version": "2.0.0",
        "engine": "LangGraph + Vega-Lite",
    }


# ─── Startup ──────────────────────────────────────────────────────────────────
@app.on_event("startup")
async def on_startup():
    storage = Path(settings.STORAGE_DIR)
    storage.mkdir(parents=True, exist_ok=True)
    logger.info("🚀 AI Data Analyst API v2.0.0 started")
    logger.info("   Storage  : %s", storage.resolve())
    logger.info("   Docs     : http://localhost:8000/docs")
    logger.info("   CORS     : %s", settings.CORS_ORIGINS)
