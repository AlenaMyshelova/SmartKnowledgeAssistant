import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from app.data_manager import DataManager
from app.database.database import init_db
from app.middleware.auth_middleware import AuthMiddleware
from app.core.config import settings
from app.api.v1.api import api_router
from app.utils.async_utils import shutdown_executor
from app.dependencies import get_current_user

load_dotenv()

logger = logging.getLogger("uvicorn.error")  # будет писать в логи uvicorn

data_manager = DataManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- startup ---
    logger.info("Starting %s v%s", settings.PROJECT_NAME, settings.VERSION)

    try:
        init_db()
        logger.info("Database initialized")
    except Exception:
        logger.exception("Database initialization failed")

    try:
        data_manager._ensure_faq_index()
        logger.info("Vector search indices ready")
    except Exception:
        logger.exception("Vector search initialization warning")

    oauth_providers = settings.OAUTH_PROVIDERS or {}
    if oauth_providers:
        logger.info("OAuth providers: %s", list(oauth_providers.keys()))
    else:
        logger.warning("No OAuth providers configured")

    yield

    # --- shutdown ---
    logger.info("Shutting down executor...")
    shutdown_executor()
    logger.info("Shutdown complete")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)
app.add_middleware(AuthMiddleware)

app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/")
def root():
    return {
        "message": f"Welcome to {settings.PROJECT_NAME}",
        "version": settings.VERSION,
        "status": "running",
        "docs": "/docs",
        "redoc": "/redoc",
    }


