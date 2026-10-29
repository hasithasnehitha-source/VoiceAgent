import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.gemini_agent import agent
from app.db.session import init_db

client = TestClient(app)


@pytest.mark.asyncio
async def test_agent_process_schedule_request():
    """Verify that agent processes scheduling requests and invokes calendar tools."""
    await init_db()
    res = await agent.process_user_message(
        user_message="Schedule a meeting with Alex tomorrow at 10 AM",
        session_id="test-session-1"
    )
    assert "reply" in res
    assert len(res["reply"]) > 5
    assert res["session_id"] == "test-session-1"
    assert len(res["tools_executed"]) >= 1
    assert any(t["tool"] == "schedule_calendar_event" for t in res["tools_executed"])


@pytest.mark.asyncio
async def test_agent_process_task_request():
    """Verify that agent processes action item requests and invokes task tools."""
    await init_db()
    res = await agent.process_user_message(
        user_message="Add an urgent task to review server logs",
        session_id="test-session-2"
    )
    assert "reply" in res
    assert len(res["tools_executed"]) >= 1
    assert any(t["tool"] == "create_task" for t in res["tools_executed"])


def test_agent_status_endpoint():
    """Verify that /api/agent/status returns agent model and configuration."""
    response = client.get("/api/agent/status")
    assert response.status_code == 200
    data = response.json()
    assert data["agent_name"] == "Aria"
    assert "mode" in data
    assert data["tools_count"] == 9


def test_agent_chat_endpoint():
    """Verify that /api/agent/chat endpoint returns assistant response and metadata."""
    payload = {
        "message": "Remember that my favourite airline is Delta",
        "session_id": "test-session-api"
    }
    response = client.post("/api/agent/chat", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "reply" in data
    assert "tools_executed" in data
    assert "latency_ms" in data
