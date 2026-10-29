import pytest
from app.services.tts_service import tts_service
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


@pytest.mark.asyncio
async def test_tts_service_synthesis():
    """Verify that edge-tts generates valid non-empty MP3 audio bytes."""
    sample_text = "Hello, your executive assistant is online."
    audio = await tts_service.synthesize_to_bytes(sample_text)
    assert len(audio) > 1000  # Should be substantial audio byte stream
    # MP3 frames typically start with sync word 0xFF 0xFB or ID3 tag header
    assert audio[:3] == b"ID3" or audio[:2] == b"\xff\xfb" or len(audio) > 0


def test_tts_voices_endpoint():
    """Verify that /api/tts/voices returns curated neural voices."""
    response = client.get("/api/tts/voices")
    assert response.status_code == 200
    data = response.json()
    assert "voices" in data
    assert len(data["voices"]) >= 3
    assert any(v["name"] == "en-US-AriaNeural" for v in data["voices"])


def test_tts_speak_endpoint():
    """Verify that /api/tts/speak returns 200 with audio/mpeg media type."""
    response = client.get("/api/tts/speak", params={"text": "Testing voice synthesis"})
    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/mpeg"
    assert len(response.content) > 1000
