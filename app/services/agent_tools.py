from app.db.session import async_session_factory
from app.db import repository
from typing import Dict, Any, Optional, List
import logging

logger = logging.getLogger("voice_agent.tools")


# ---------------------------------------------------------------------------
# Executive Tool Implementations
# ---------------------------------------------------------------------------

async def tool_create_task(
    title: str,
    description: Optional[str] = None,
    priority: str = "medium",
    due_date: Optional[str] = None
) -> Dict[str, Any]:
    """Create a new action item or to-do task for the executive."""
    async with async_session_factory() as db:
        task = await repository.create_task(
            db,
            title=title,
            description=description,
            priority=priority,
            due_date=due_date
        )
        return {
            "success": True,
            "message": f"Task '{task.title}' created successfully with {task.priority} priority.",
            "task": task.to_dict()
        }


async def tool_list_tasks(
    status: Optional[str] = None,
    priority: Optional[str] = None,
    limit: int = 10
) -> Dict[str, Any]:
    """Retrieve existing tasks, optionally filtered by status or priority."""
    async with async_session_factory() as db:
        tasks = await repository.get_tasks(
            db,
            status=status,
            priority=priority,
            limit=limit
        )
        return {
            "success": True,
            "count": len(tasks),
            "tasks": [t.to_dict() for t in tasks]
        }


async def tool_update_task_status(
    task_id: int,
    status: str
) -> Dict[str, Any]:
    """Update the status of a task (e.g., 'completed', 'in_progress', 'cancelled')."""
    async with async_session_factory() as db:
        task = await repository.update_task_status(db, task_id=task_id, status=status)
        if not task:
            return {
                "success": False,
                "message": f"Task with ID {task_id} not found."
            }
        return {
            "success": True,
            "message": f"Task '{task.title}' status updated to '{task.status}'.",
            "task": task.to_dict()
        }


async def tool_schedule_calendar_event(
    title: str,
    start_time: str,
    end_time: Optional[str] = None,
    location: Optional[str] = None,
    attendees: Optional[str] = None
) -> Dict[str, Any]:
    """Schedule a new meeting or calendar event."""
    async with async_session_factory() as db:
        event = await repository.create_calendar_event(
            db,
            title=title,
            start_time=start_time,
            end_time=end_time,
            location=location,
            attendees=attendees
        )
        return {
            "success": True,
            "message": f"Event '{event.title}' scheduled for {event.start_time}.",
            "event": event.to_dict()
        }


async def tool_list_calendar_events(
    status: Optional[str] = "scheduled",
    limit: int = 10
) -> Dict[str, Any]:
    """Retrieve upcoming calendar events."""
    async with async_session_factory() as db:
        events = await repository.get_calendar_events(db, status=status, limit=limit)
        return {
            "success": True,
            "count": len(events),
            "events": [e.to_dict() for e in events]
        }


async def tool_cancel_calendar_event(
    event_id: int
) -> Dict[str, Any]:
    """Cancel a scheduled calendar event."""
    async with async_session_factory() as db:
        event = await repository.cancel_calendar_event(db, event_id=event_id)
        if not event:
            return {
                "success": False,
                "message": f"Calendar event with ID {event_id} not found."
            }
        return {
            "success": True,
            "message": f"Event '{event.title}' has been cancelled.",
            "event": event.to_dict()
        }


async def tool_save_smart_memory(
    key: str,
    content: str,
    category: str = "general",
    importance: str = "normal"
) -> Dict[str, Any]:
    """Save an important executive memory, preference, contact, or note."""
    async with async_session_factory() as db:
        memory = await repository.save_memory(
            db,
            key=key,
            content=content,
            category=category,
            importance=importance
        )
        return {
            "success": True,
            "message": f"Stored memory under key '{memory.key}'.",
            "memory": memory.to_dict()
        }


async def tool_recall_smart_memory(
    query: Optional[str] = None,
    category: Optional[str] = None
) -> Dict[str, Any]:
    """Recall stored memories or preferences matching a query or category."""
    async with async_session_factory() as db:
        memories = await repository.recall_memories(db, query=query, category=category)
        return {
            "success": True,
            "count": len(memories),
            "memories": [m.to_dict() for m in memories]
        }


async def tool_search_knowledge_base(
    query: str,
    top_k: int = 2
) -> Dict[str, Any]:
    """Perform semantic vector RAG search across executive handbooks, company policies, and documents."""
    from app.services.rag_service import rag_service
    results = await rag_service.search_semantic(query=query, top_k=top_k)
    return {
        "success": True,
        "count": len(results),
        "query": query,
        "results": results
    }



# ---------------------------------------------------------------------------
# Tool Dispatcher Registry
# ---------------------------------------------------------------------------

AVAILABLE_TOOLS = {
    "create_task": tool_create_task,
    "list_tasks": tool_list_tasks,
    "update_task_status": tool_update_task_status,
    "schedule_calendar_event": tool_schedule_calendar_event,
    "list_calendar_events": tool_list_calendar_events,
    "cancel_calendar_event": tool_cancel_calendar_event,
    "save_smart_memory": tool_save_smart_memory,
    "recall_smart_memory": tool_recall_smart_memory,
    "search_knowledge_base": tool_search_knowledge_base,
}


async def execute_tool(tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a tool by name with arguments and return JSON-serializable results."""
    handler = AVAILABLE_TOOLS.get(tool_name)
    if not handler:
        logger.warning(f"Unknown tool requested: {tool_name}")
        return {
            "success": False,
            "error": f"Tool '{tool_name}' is not recognized."
        }

    try:
        logger.info(f"Executing tool '{tool_name}' with args: {args}")
        result = await handler(**args)
        return result
    except Exception as exc:
        logger.error(f"Error executing tool '{tool_name}': {exc}", exc_info=True)
        return {
            "success": False,
            "error": str(exc)
        }


# ---------------------------------------------------------------------------
# Gemini Tool Function Declarations
# ---------------------------------------------------------------------------

GEMINI_FUNCTION_DECLARATIONS = [
    {
        "name": "create_task",
        "description": "Create a new task or action item on the executive to-do list.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "title": {"type": "STRING", "description": "Short title of the task."},
                "description": {"type": "STRING", "description": "Optional details or notes for the task."},
                "priority": {"type": "STRING", "description": "Priority: low, medium, high, or urgent.", "enum": ["low", "medium", "high", "urgent"]},
                "due_date": {"type": "STRING", "description": "Due date or time expression, e.g. 'Tomorrow 5 PM'."}
            },
            "required": ["title"]
        }
    },
    {
        "name": "list_tasks",
        "description": "List current tasks and to-dos, optionally filtered by status or priority.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "status": {"type": "STRING", "description": "Filter by status: pending, in_progress, completed, cancelled.", "enum": ["pending", "in_progress", "completed", "cancelled"]},
                "priority": {"type": "STRING", "description": "Filter by priority: low, medium, high, urgent.", "enum": ["low", "medium", "high", "urgent"]},
                "limit": {"type": "INTEGER", "description": "Maximum number of tasks to return (default 10)."}
            }
        }
    },
    {
        "name": "update_task_status",
        "description": "Mark a task as completed, in-progress, or cancelled by its ID.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "task_id": {"type": "INTEGER", "description": "Numeric ID of the task to update."},
                "status": {"type": "STRING", "description": "New status: completed, in_progress, pending, or cancelled.", "enum": ["completed", "in_progress", "pending", "cancelled"]}
            },
            "required": ["task_id", "status"]
        }
    },
    {
        "name": "schedule_calendar_event",
        "description": "Schedule a new meeting, appointment, or calendar event.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "title": {"type": "STRING", "description": "Title or subject of the meeting."},
                "start_time": {"type": "STRING", "description": "When the meeting starts, e.g. 'Tomorrow at 10:00 AM' or '2026-10-30 14:00'."},
                "end_time": {"type": "STRING", "description": "When the meeting ends."},
                "location": {"type": "STRING", "description": "Location or meeting link (Zoom, Google Meet, Room 101)."},
                "attendees": {"type": "STRING", "description": "Names or emails of people attending."}
            },
            "required": ["title", "start_time"]
        }
    },
    {
        "name": "list_calendar_events",
        "description": "List scheduled calendar events and upcoming meetings.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "status": {"type": "STRING", "description": "Event status, default 'scheduled'.", "enum": ["scheduled", "completed", "cancelled"]},
                "limit": {"type": "INTEGER", "description": "Maximum number of events to return."}
            }
        }
    },
    {
        "name": "cancel_calendar_event",
        "description": "Cancel a scheduled calendar event by its numeric ID.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "event_id": {"type": "INTEGER", "description": "Numeric ID of the event to cancel."}
            },
            "required": ["event_id"]
        }
    },
    {
        "name": "save_smart_memory",
        "description": "Save a personal preference, contact info, fact, or important note about the user.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "key": {"type": "STRING", "description": "Unique topic or keyword (e.g. 'preferred_airline', 'wife_birthday', 'dietary_restrictions')."},
                "content": {"type": "STRING", "description": "The exact fact, preference, or note to remember."},
                "category": {"type": "STRING", "description": "Category: preference, contact, fact, reminder, general.", "enum": ["preference", "contact", "fact", "reminder", "general"]},
                "importance": {"type": "STRING", "description": "Importance level: low, normal, high.", "enum": ["low", "normal", "high"]}
            },
            "required": ["key", "content"]
        }
    },
    {
        "name": "recall_smart_memory",
        "description": "Recall saved preferences, notes, or facts by searching keywords or categories.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {"type": "STRING", "description": "Search term or keyword to find relevant memories."},
                "category": {"type": "STRING", "description": "Category to filter by."}
            }
        }
    },
    {
        "name": "search_knowledge_base",
        "description": "Perform semantic vector RAG search across executive handbooks, corporate policies, and uploaded company documents.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {"type": "STRING", "description": "Topic, question, or keyword to retrieve from company knowledge base."},
                "top_k": {"type": "INTEGER", "description": "Number of snippets to retrieve (default 2)."}
            },
            "required": ["query"]
        }
    }
]
