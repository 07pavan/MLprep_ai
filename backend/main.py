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
from routers.traces import router as traces_router
from routers.insights import router as insights_router

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
app.include_router(traces_router)
app.include_router(insights_router)


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

    # Initialize Firebase Admin SDK
    import firebase_admin
    from firebase_admin import credentials
    if not firebase_admin._apps:
        if settings.GOOGLE_APPLICATION_CREDENTIALS:
            try:
                cred = credentials.Certificate(settings.GOOGLE_APPLICATION_CREDENTIALS)
                firebase_admin.initialize_app(cred)
                logger.info("🔥 Firebase Admin SDK initialized with certificate")
            except Exception as e:
                logger.error("❌ Failed to initialize Firebase Admin with certificate: %s", e)
        else:
            try:
                firebase_admin.initialize_app()
                logger.info("🔥 Firebase Admin SDK initialized with default credentials")
            except Exception as e:
                logger.warning("⚠️ Firebase Admin SDK initialized without credentials (ENABLE_AUTH must be False to allow local calls): %s", e)

    logger.info("🚀 AI Data Analyst API v2.0.0 started")
    logger.info("   Storage  : %s", storage.resolve())
    logger.info("   Docs     : http://localhost:8000/docs")
    logger.info("   CORS     : %s", settings.CORS_ORIGINS)


# ─── Shutdown ─────────────────────────────────────────────────────────────────
@app.on_event("shutdown")
async def on_shutdown():
    try:
        from graph.graph import db_pool
        if db_pool is not None:
            logger.info("🔌 Gracefully closing PostgreSQL connection pool...")
            db_pool.close()
            logger.info("🔒 PostgreSQL connection pool closed successfully.")
    except Exception as e:
        logger.error("⚠️ Error while closing PostgreSQL pool during shutdown: %s", str(e))
