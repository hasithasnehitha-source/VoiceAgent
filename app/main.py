from contextlib import asynccontextmanager
from datetime import datetime, timezone
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("voice_agent")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle management."""
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION} [{settings.ENVIRONMENT}]")
    yield
    logger.info(f"Shutting down {settings.APP_NAME}")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Enterprise-grade Executive Personal AI Voice Agent with real-time speech and tool execution.",
    lifespan=lifespan
)

# Enable CORS for local development and WebSocket clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", tags=["Root"])
async def root():
    """Root endpoint welcoming users and providing basic API metadata."""
    return JSONResponse(
        content={
            "message": f"Welcome to {settings.APP_NAME}",
            "version": settings.APP_VERSION,
            "status": "online",
            "docs_url": "/docs",
            "health_url": "/api/health"
        }
    )


@app.get("/api/health", tags=["System"])
async def health_check():
    """System health check endpoint verifying API service availability."""
    return JSONResponse(
        content={
            "status": "healthy",
            "app_name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "environment": settings.ENVIRONMENT,
            "debug": settings.DEBUG,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    )
