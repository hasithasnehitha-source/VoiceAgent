from contextlib import asynccontextmanager
from datetime import datetime, timezone
import logging
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import init_db, get_db, engine
from app.db import repository

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
    await init_db()
    yield
    logger.info(f"Shutting down {settings.APP_NAME}")
    await engine.dispose()


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
            "health_url": "/api/health",
            "db_status_url": "/api/db/status"
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


@app.get("/api/db/status", tags=["Database"])
async def database_status(db: AsyncSession = Depends(get_db)):
    """Database status endpoint verifying connectivity, dialect, and record counts."""
    stats = await repository.get_db_stats(db)
    dialect_name = engine.dialect.name
    return JSONResponse(
        content={
            "status": "connected",
            "dialect": dialect_name,
            "url_scheme": settings.DATABASE_URL.split("://")[0],
            "stats": stats,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    )


@app.post("/api/db/seed-sample", tags=["Database"])
async def seed_sample_data(db: AsyncSession = Depends(get_db)):
    """Seed sample executive data (tasks, calendar event, memory) for manual browser verification."""
    task = await repository.create_task(
        db,
        title="Review Q4 Executive Budget Strategy",
        description="Analyze cloud infrastructure costs and AI token burn rate.",
        priority="high",
        due_date="Tomorrow at 5:00 PM"
    )
    event = await repository.create_calendar_event(
        db,
        title="Board of Directors Quarterly Sync",
        start_time="Tomorrow 10:00 AM",
        end_time="Tomorrow 11:30 AM",
        location="Executive Boardroom / Zoom",
        attendees="CEO, CTO, Head of Product"
    )
    memory = await repository.save_memory(
        db,
        key="meeting_preference",
        content="Prefer mornings before 12 PM for strategic architecture reviews.",
        category="preference",
        importance="high"
    )
    stats = await repository.get_db_stats(db)
    return JSONResponse(
        content={
            "message": "Sample executive records created successfully!",
            "created_items": {
                "task": task.to_dict(),
                "event": event.to_dict(),
                "memory": memory.to_dict()
            },
            "stats": stats
        }
    )

