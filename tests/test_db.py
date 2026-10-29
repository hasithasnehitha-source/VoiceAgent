import pytest
from app.db.session import async_session_factory, init_db
from app.db import repository


@pytest.mark.asyncio
async def test_database_initialization_and_crud():
    """Verify that tables are created and async repository operations work end-to-end."""
    # 1. Initialize tables
    await init_db()

    async with async_session_factory() as session:
        # 2. Test Task operations
        task = await repository.create_task(
            session,
            title="Prepare board deck",
            description="Q3 review and product roadmap",
            priority="high",
            due_date="Friday"
        )
        assert task.id is not None
        assert task.title == "Prepare board deck"
        assert task.status == "pending"

        # Read tasks
        tasks = await repository.get_tasks(session)
        assert any(t.id == task.id for t in tasks)

        # Update task status
        updated = await repository.update_task_status(session, task.id, "completed")
        assert updated is not None
        assert updated.status == "completed"

        # 3. Test Calendar operations
        event = await repository.create_calendar_event(
            session,
            title="Engineering All-Hands",
            start_time="Tomorrow 3:00 PM",
            location="Room 402"
        )
        assert event.id is not None
        assert event.title == "Engineering All-Hands"
        assert event.status == "scheduled"

        events = await repository.get_calendar_events(session)
        assert any(e.id == event.id for e in events)

        # 4. Test Smart Memory operations
        memory = await repository.save_memory(
            session,
            key="preferred_contact",
            content="Alex via Slack or Email",
            category="contact",
            importance="high"
        )
        assert memory.id is not None

        # Search memory
        recalled = await repository.recall_memories(session, query="Slack")
        assert len(recalled) >= 1
        assert "Alex" in recalled[0].content

        # 5. Test stats
        stats = await repository.get_db_stats(session)
        assert stats["tasks"] >= 1
        assert stats["calendar_events"] >= 1
        assert stats["memories"] >= 1
