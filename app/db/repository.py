from typing import List, Optional, Dict, Any
from sqlalchemy import select, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Task, CalendarEvent, SmartMemory, ConversationLog


# ---------------------------------------------------------------------------
# Task Repository Functions
# ---------------------------------------------------------------------------

async def create_task(
    db: AsyncSession,
    title: str,
    description: Optional[str] = None,
    priority: str = "medium",
    due_date: Optional[str] = None
) -> Task:
    """Create a new action item or task."""
    task = Task(
        title=title.strip(),
        description=description.strip() if description else None,
        priority=priority.lower(),
        due_date=due_date.strip() if due_date else None,
        status="pending"
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task


async def get_tasks(
    db: AsyncSession,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    limit: int = 50
) -> List[Task]:
    """Retrieve list of tasks with optional filtering."""
    query = select(Task)
    if status:
        query = query.where(Task.status == status.lower())
    if priority:
        query = query.where(Task.priority == priority.lower())
    query = query.order_by(Task.created_at.desc()).limit(limit)

    result = await db.execute(query)
    return list(result.scalars().all())


async def get_task_by_id(db: AsyncSession, task_id: int) -> Optional[Task]:
    """Retrieve single task by ID."""
    result = await db.execute(select(Task).where(Task.id == task_id))
    return result.scalar_one_or_none()


async def update_task_status(
    db: AsyncSession,
    task_id: int,
    status: str
) -> Optional[Task]:
    """Update status of a task (e.g. pending -> completed)."""
    task = await get_task_by_id(db, task_id)
    if not task:
        return None
    task.status = status.lower()
    await db.commit()
    await db.refresh(task)
    return task


async def delete_task(db: AsyncSession, task_id: int) -> bool:
    """Delete a task by ID."""
    task = await get_task_by_id(db, task_id)
    if not task:
        return False
    await db.delete(task)
    await db.commit()
    return True


# ---------------------------------------------------------------------------
# Calendar Repository Functions
# ---------------------------------------------------------------------------

async def create_calendar_event(
    db: AsyncSession,
    title: str,
    start_time: str,
    end_time: Optional[str] = None,
    location: Optional[str] = None,
    attendees: Optional[str] = None
) -> CalendarEvent:
    """Schedule a new calendar event or meeting."""
    event = CalendarEvent(
        title=title.strip(),
        start_time=start_time.strip(),
        end_time=end_time.strip() if end_time else None,
        location=location.strip() if location else None,
        attendees=attendees.strip() if attendees else None,
        status="scheduled"
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)
    return event


async def get_calendar_events(
    db: AsyncSession,
    status: Optional[str] = "scheduled",
    limit: int = 50
) -> List[CalendarEvent]:
    """Retrieve calendar events ordered by creation."""
    query = select(CalendarEvent)
    if status:
        query = query.where(CalendarEvent.status == status.lower())
    query = query.order_by(CalendarEvent.created_at.desc()).limit(limit)

    result = await db.execute(query)
    return list(result.scalars().all())


async def cancel_calendar_event(
    db: AsyncSession,
    event_id: int
) -> Optional[CalendarEvent]:
    """Cancel a calendar event."""
    result = await db.execute(select(CalendarEvent).where(CalendarEvent.id == event_id))
    event = result.scalar_one_or_none()
    if not event:
        return None
    event.status = "cancelled"
    await db.commit()
    await db.refresh(event)
    return event


# ---------------------------------------------------------------------------
# Smart Memory Repository Functions
# ---------------------------------------------------------------------------

async def save_memory(
    db: AsyncSession,
    key: str,
    content: str,
    category: str = "general",
    importance: str = "normal"
) -> SmartMemory:
    """Save or update a smart memory entry."""
    # Check if memory key in category already exists
    query = select(SmartMemory).where(
        SmartMemory.key == key.strip().lower(),
        SmartMemory.category == category.strip().lower()
    )
    result = await db.execute(query)
    existing = result.scalar_one_or_none()

    if existing:
        existing.content = content.strip()
        existing.importance = importance.lower()
        await db.commit()
        await db.refresh(existing)
        return existing

    memory = SmartMemory(
        key=key.strip().lower(),
        content=content.strip(),
        category=category.strip().lower(),
        importance=importance.lower()
    )
    db.add(memory)
    await db.commit()
    await db.refresh(memory)
    return memory


async def recall_memories(
    db: AsyncSession,
    query: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = 10
) -> List[SmartMemory]:
    """Search and recall relevant memories."""
    stmt = select(SmartMemory)
    if category:
        stmt = stmt.where(SmartMemory.category == category.strip().lower())
    if query:
        search_filter = f"%{query.strip().lower()}%"
        stmt = stmt.where(
            (SmartMemory.key.ilike(search_filter)) |
            (SmartMemory.content.ilike(search_filter))
        )
    stmt = stmt.order_by(SmartMemory.created_at.desc()).limit(limit)

    result = await db.execute(stmt)
    return list(result.scalars().all())


async def list_all_memories(db: AsyncSession, limit: int = 50) -> List[SmartMemory]:
    """List all stored memories."""
    result = await db.execute(select(SmartMemory).order_by(SmartMemory.created_at.desc()).limit(limit))
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Telemetry & Status Functions
# ---------------------------------------------------------------------------

async def log_conversation(
    db: AsyncSession,
    session_id: str,
    role: str,
    content: str,
    tool_name: Optional[str] = None,
    latency_ms: Optional[float] = None
) -> ConversationLog:
    """Log dialogue or tool execution."""
    entry = ConversationLog(
        session_id=session_id,
        role=role,
        content=content,
        tool_name=tool_name,
        latency_ms=latency_ms
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return entry


async def get_db_stats(db: AsyncSession) -> Dict[str, Any]:
    """Get count summaries across all domain tables."""
    task_count = await db.scalar(select(func.count(Task.id)))
    calendar_count = await db.scalar(select(func.count(CalendarEvent.id)))
    memory_count = await db.scalar(select(func.count(SmartMemory.id)))
    log_count = await db.scalar(select(func.count(ConversationLog.id)))

    return {
        "tasks": task_count or 0,
        "calendar_events": calendar_count or 0,
        "memories": memory_count or 0,
        "conversation_logs": log_count or 0
    }
