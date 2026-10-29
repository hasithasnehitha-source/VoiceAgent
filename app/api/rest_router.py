from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.db.session import get_db
from app.db import repository
from app.db.models import ConversationLog

router = APIRouter(prefix="/api", tags=["Executive Dashboard REST"])


# ---------------------------------------------------------------------------
# Request Models
# ---------------------------------------------------------------------------

class CreateTaskDTO(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    priority: str = Field(default="medium", pattern="^(low|medium|high|urgent)$")
    due_date: Optional[str] = None


class UpdateTaskStatusDTO(BaseModel):
    status: str = Field(..., pattern="^(pending|in_progress|completed|cancelled)$")


class CreateEventDTO(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    start_time: str = Field(...)
    end_time: Optional[str] = None
    location: Optional[str] = None
    attendees: Optional[str] = None


class CreateMemoryDTO(BaseModel):
    key: str = Field(..., min_length=1, max_length=100)
    content: str = Field(..., min_length=1)
    category: str = Field(default="general", pattern="^(preference|contact|fact|reminder|general)$")
    importance: str = Field(default="normal", pattern="^(low|normal|high)$")


# ---------------------------------------------------------------------------
# Task Endpoints
# ---------------------------------------------------------------------------

@router.get("/tasks")
async def list_tasks(
    status: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """List all action items and tasks."""
    tasks = await repository.get_tasks(db, status=status, priority=priority, limit=limit)
    return {"tasks": [t.to_dict() for t in tasks], "count": len(tasks)}


@router.post("/tasks")
async def create_task(dto: CreateTaskDTO, db: AsyncSession = Depends(get_db)):
    """Create a new task."""
    task = await repository.create_task(
        db,
        title=dto.title,
        description=dto.description,
        priority=dto.priority,
        due_date=dto.due_date
    )
    return {"message": "Task created successfully", "task": task.to_dict()}


@router.patch("/tasks/{task_id}")
async def update_task_status(
    task_id: int,
    dto: UpdateTaskStatusDTO,
    db: AsyncSession = Depends(get_db)
):
    """Update task status (e.g. pending -> completed)."""
    task = await repository.update_task_status(db, task_id=task_id, status=dto.status)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"message": f"Task status updated to {task.status}", "task": task.to_dict()}


@router.delete("/tasks/{task_id}")
async def delete_task(task_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a task."""
    success = await repository.delete_task(db, task_id=task_id)
    if not success:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"message": "Task deleted successfully", "task_id": task_id}


# ---------------------------------------------------------------------------
# Calendar Endpoints
# ---------------------------------------------------------------------------

@router.get("/calendar")
async def list_calendar(
    status: Optional[str] = Query("scheduled"),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """List scheduled calendar events."""
    events = await repository.get_calendar_events(db, status=status, limit=limit)
    return {"events": [e.to_dict() for e in events], "count": len(events)}


@router.post("/calendar")
async def schedule_event(dto: CreateEventDTO, db: AsyncSession = Depends(get_db)):
    """Schedule a new meeting or event."""
    event = await repository.create_calendar_event(
        db,
        title=dto.title,
        start_time=dto.start_time,
        end_time=dto.end_time,
        location=dto.location,
        attendees=dto.attendees
    )
    return {"message": "Event scheduled successfully", "event": event.to_dict()}


@router.delete("/calendar/{event_id}")
async def cancel_event(event_id: int, db: AsyncSession = Depends(get_db)):
    """Cancel a scheduled event."""
    event = await repository.cancel_calendar_event(db, event_id=event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return {"message": "Event cancelled", "event": event.to_dict()}


# ---------------------------------------------------------------------------
# Smart Memory Endpoints
# ---------------------------------------------------------------------------

@router.get("/memories")
async def list_memories(
    query: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """Retrieve stored executive memories and preferences."""
    if query or category:
        memories = await repository.recall_memories(db, query=query, category=category)
    else:
        memories = await repository.list_all_memories(db)
    return {"memories": [m.to_dict() for m in memories], "count": len(memories)}


@router.post("/memories")
async def save_memory(dto: CreateMemoryDTO, db: AsyncSession = Depends(get_db)):
    """Save an executive memory."""
    memory = await repository.save_memory(
        db,
        key=dto.key,
        content=dto.content,
        category=dto.category,
        importance=dto.importance
    )
    return {"message": "Memory saved", "memory": memory.to_dict()}


# ---------------------------------------------------------------------------
# Activity & Telemetry Logs
# ---------------------------------------------------------------------------

@router.get("/logs")
async def list_recent_logs(
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """Retrieve recent conversation turns and latency telemetry."""
    stmt = select(ConversationLog).order_by(desc(ConversationLog.created_at)).limit(limit)
    result = await db.execute(stmt)
    logs = result.scalars().all()
    return {"logs": [log.to_dict() for log in logs], "count": len(logs)}
