import pytest
from app.db.session import init_db
from app.services.agent_tools import (
    execute_tool,
    AVAILABLE_TOOLS,
    GEMINI_FUNCTION_DECLARATIONS
)


@pytest.mark.asyncio
async def test_tool_declarations_and_registry():
    """Verify that all tools in GEMINI_FUNCTION_DECLARATIONS have matching handlers."""
    assert len(GEMINI_FUNCTION_DECLARATIONS) == 9
    for decl in GEMINI_FUNCTION_DECLARATIONS:
        name = decl["name"]
        assert name in AVAILABLE_TOOLS, f"Declaration {name} missing handler"


@pytest.mark.asyncio
async def test_executive_tools_execution():
    """Test full execution of all executive tools via execute_tool."""
    await init_db()

    # 1. Test create_task
    task_res = await execute_tool("create_task", {
        "title": "Finalize Q4 Investor Deck",
        "description": "Highlight MRR growth and Voice Agent launch",
        "priority": "urgent",
        "due_date": "Next Monday 9 AM"
    })
    assert task_res["success"] is True
    task_id = task_res["task"]["id"]
    assert task_res["task"]["title"] == "Finalize Q4 Investor Deck"

    # 2. Test list_tasks
    list_tasks_res = await execute_tool("list_tasks", {"limit": 5})
    assert list_tasks_res["success"] is True
    assert list_tasks_res["count"] >= 1

    # 3. Test update_task_status
    update_res = await execute_tool("update_task_status", {
        "task_id": task_id,
        "status": "completed"
    })
    assert update_res["success"] is True
    assert update_res["task"]["status"] == "completed"

    # 4. Test schedule_calendar_event
    event_res = await execute_tool("schedule_calendar_event", {
        "title": "Product Strategy Sync",
        "start_time": "Friday 2:00 PM",
        "location": "Google Meet",
        "attendees": "Design & Engineering leads"
    })
    assert event_res["success"] is True
    event_id = event_res["event"]["id"]
    assert event_res["event"]["title"] == "Product Strategy Sync"

    # 5. Test list_calendar_events
    events_res = await execute_tool("list_calendar_events", {"limit": 5})
    assert events_res["success"] is True
    assert events_res["count"] >= 1

    # 6. Test cancel_calendar_event
    cancel_res = await execute_tool("cancel_calendar_event", {"event_id": event_id})
    assert cancel_res["success"] is True
    assert cancel_res["event"]["status"] == "cancelled"

    # 7. Test save_smart_memory
    memory_res = await execute_tool("save_smart_memory", {
        "key": "preferred_voice",
        "content": "Prefers concise, crisp answers without pleasantries during meetings",
        "category": "preference",
        "importance": "high"
    })
    assert memory_res["success"] is True
    assert memory_res["memory"]["key"] == "preferred_voice"

    # 8. Test recall_smart_memory
    recall_res = await execute_tool("recall_smart_memory", {"query": "concise"})
    assert recall_res["success"] is True
    assert recall_res["count"] >= 1

    # 9. Test unknown tool error handling
    unknown_res = await execute_tool("non_existent_tool", {})
    assert unknown_res["success"] is False
    assert "not recognized" in unknown_res["error"]
