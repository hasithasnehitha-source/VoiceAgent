import json
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_websocket_handshake_and_ping():
    """Verify WebSocket handshake and ping-pong heartbeat."""
    with client.websocket_connect("/ws/agent?session_id=ws-test-1") as websocket:
        # 1. First frame on connect is connection_established
        greeting = websocket.receive_json()
        assert greeting["type"] == "connection_established"
        assert greeting["agent"] == "Aria"
        assert greeting["session_id"] == "ws-test-1"

        # 2. Ping-pong test
        websocket.send_json({"type": "ping"})
        pong = websocket.receive_json()
        assert pong["type"] == "pong"
        assert "timestamp" in pong


def test_websocket_message_and_audio_streaming():
    """Verify end-to-end WebSocket voice dialogue and audio chunk streaming."""
    with client.websocket_connect("/ws/agent?session_id=ws-test-2") as websocket:
        # Handshake
        greeting = websocket.receive_json()
        assert greeting["type"] == "connection_established"

        # Send user prompt
        websocket.send_json({
            "type": "text_message",
            "message": "Add an urgent task to review server metrics"
        })

        # Collect event sequence
        received_types = []
        while True:
            msg = websocket.receive_json()
            mtype = msg.get("type")
            received_types.append(mtype)

            if mtype == "status" and msg.get("status") == "idle":
                break

        # Verify key pipeline events were fired
        assert "status" in received_types
        assert "speech_text" in received_types
        assert "audio_stream_start" in received_types
        assert "audio_chunk" in received_types
        assert "audio_stream_end" in received_types
        assert "latency_metrics" in received_types


def test_websocket_barge_in_interrupt():
    """Verify client can send barge-in interruption."""
    with client.websocket_connect("/ws/agent?session_id=ws-test-3") as websocket:
        websocket.receive_json()  # Handshake

        # Send interrupt
        websocket.send_json({"type": "interrupt"})
        res = websocket.receive_json()
        assert res["type"] == "status"
        assert res["status"] == "idle"
        assert "interrupted" in res["message"].lower()
