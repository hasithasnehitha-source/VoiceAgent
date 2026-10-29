from contextlib import asynccontextmanager
from datetime import datetime, timezone
import logging
from fastapi import FastAPI, Depends, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import init_db, get_db, engine
from app.db import repository
from app.services.agent_tools import (
    AVAILABLE_TOOLS,
    GEMINI_FUNCTION_DECLARATIONS,
    execute_tool
)
from app.services.tts_service import tts_service
from pydantic import BaseModel, Field
from typing import Dict, Any

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


class ToolExecutionRequest(BaseModel):
    tool_name: str = Field(..., description="Name of the tool to execute")
    args: Dict[str, Any] = Field(default_factory=dict, description="Arguments dictionary for the tool")


@app.get("/api/tools", tags=["Tools"])
async def list_tools():
    """List all registered agent tools and their Gemini function calling schemas."""
    return JSONResponse(
        content={
            "count": len(GEMINI_FUNCTION_DECLARATIONS),
            "tool_names": list(AVAILABLE_TOOLS.keys()),
            "declarations": GEMINI_FUNCTION_DECLARATIONS
        }
    )


@app.post("/api/tools/execute", tags=["Tools"])
async def run_tool(request: ToolExecutionRequest):
    """Execute an agent tool with arguments and return the result."""
    result = await execute_tool(request.tool_name, request.args)
    return JSONResponse(content=result)


@app.get("/api/tts/voices", tags=["Speech (TTS)"])
async def list_voices():
    """List curated high-fidelity neural voices available for the voice agent."""
    return JSONResponse(
        content={
            "default_voice": settings.DEFAULT_VOICE,
            "voices": tts_service.get_curated_voices()
        }
    )


@app.get("/api/tts/speak", tags=["Speech (TTS)"])
async def synthesize_speech(
    text: str = Query(..., description="Text to synthesize into neural speech"),
    voice: str = Query(None, description="Neural voice name (e.g. en-US-AriaNeural, en-US-GuyNeural)")
):
    """Synthesize text into MP3 audio and stream directly to the browser or audio player."""
    if not text.strip():
        raise HTTPException(status_code=400, detail="Text parameter cannot be empty.")

    audio_bytes = await tts_service.synthesize_to_bytes(text=text, voice=voice)
    if not audio_bytes:
        raise HTTPException(status_code=500, detail="Failed to synthesize speech audio.")

    return Response(
        content=audio_bytes,
        media_type="audio/mpeg",
        headers={
            "Content-Disposition": "inline; filename=speech.mp3",
            "Cache-Control": "no-cache"
        }
    )



