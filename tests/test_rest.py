import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_rest_tasks_crud():
    """Verify CRUD endpoints for tasks."""
    # 1. Create task
    res = client.post("/api/tasks", json={
        "title": "Review Step 6 WebSocket",
        "priority": "high",
        "due_date": "Tonight"
    })
    assert res.status_code == 200
    task_id = res.json()["task"]["id"]

    # 2. List tasks
    list_res = client.get("/api/tasks")
    assert list_res.status_code == 200
    assert any(t["id"] == task_id for t in list_res.json()["tasks"])

    # 3. Update task status
    patch_res = client.patch(f"/api/tasks/{task_id}", json={"status": "completed"})
    assert patch_res.status_code == 200
    assert patch_res.json()["task"]["status"] == "completed"

    # 4. Delete task
    del_res = client.delete(f"/api/tasks/{task_id}")
    assert del_res.status_code == 200


def test_rest_calendar_crud():
    """Verify Calendar REST endpoints."""
    res = client.post("/api/calendar", json={
        "title": "Strategy Sync Meeting",
        "start_time": "Tomorrow 4 PM",
        "location": "Zoom"
    })
    assert res.status_code == 200
    event_id = res.json()["event"]["id"]

    # List events
    list_res = client.get("/api/calendar")
    assert list_res.status_code == 200
    assert any(e["id"] == event_id for e in list_res.json()["events"])

    # Cancel event
    del_res = client.delete(f"/api/calendar/{event_id}")
    assert del_res.status_code == 200
    assert del_res.json()["event"]["status"] == "cancelled"


def test_rest_memories_and_logs():
    """Verify smart memories and activity logs endpoints."""
    # Save memory
    mem_res = client.post("/api/memories", json={
        "key": "rest_test_key",
        "content": "Test content for memory",
        "category": "fact"
    })
    assert mem_res.status_code == 200

    # List memories
    get_mem = client.get("/api/memories?query=rest_test_key")
    assert get_mem.status_code == 200
    assert len(get_mem.json()["memories"]) >= 1

    # Check logs
    logs_res = client.get("/api/logs")
    assert logs_res.status_code == 200
    assert "logs" in logs_res.json()
