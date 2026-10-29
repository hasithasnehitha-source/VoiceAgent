import pytest
from app.db.session import init_db
from app.services.rag_service import (
    rag_service,
    compute_cosine_similarity,
    generate_fallback_embedding,
    seed_initial_knowledge_base
)
from app.services.agent_tools import execute_tool
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_cosine_similarity_math():
    """Verify that cosine similarity returns 1.0 for identical vectors and 0.0 for orthogonal."""
    v1 = [1.0, 0.0, 0.0]
    v2 = [1.0, 0.0, 0.0]
    assert pytest.approx(compute_cosine_similarity(v1, v2), 0.001) == 1.0

    v3 = [0.0, 1.0, 0.0]
    assert pytest.approx(compute_cosine_similarity(v1, v3), 0.001) == 0.0


@pytest.mark.asyncio
async def test_rag_ingest_and_semantic_search():
    """Verify document chunking, vector embedding generation, and semantic search."""
    await init_db()
    await seed_initial_knowledge_base()

    # Search for travel policy
    results = await rag_service.search_semantic("flight accommodation travel policy", top_k=2)
    assert len(results) >= 1
    assert any("flight" in r["content"].lower() or "travel" in r["content"].lower() for r in results)

    # Search for crisis protocol
    crisis_res = await rag_service.search_semantic("emergency crisis protocol security", top_k=1)
    assert len(crisis_res) >= 1
    assert "crisis" in crisis_res[0]["content"].lower()


@pytest.mark.asyncio
async def test_rag_tool_execution():
    """Verify that agent execute_tool invokes search_knowledge_base."""
    await init_db()
    await seed_initial_knowledge_base()

    res = await execute_tool("search_knowledge_base", {"query": "board presentation format"})
    assert res["success"] is True
    assert res["count"] >= 1
    assert any("board" in r["content"].lower() for r in res["results"])


def test_rag_rest_endpoints():
    """Verify REST endpoints for vector RAG."""
    # List documents
    res = client.get("/api/rag/documents")
    assert res.status_code == 200
    data = res.json()
    assert "documents" in data
    assert len(data["documents"]) >= 1

    # Search via REST
    search_res = client.post("/api/rag/search", json={"query": "remote work core hours", "top_k": 2})
    assert search_res.status_code == 200
    assert "results" in search_res.json()
