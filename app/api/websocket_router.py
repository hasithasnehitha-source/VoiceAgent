import asyncio
import base64
import json
import logging
import time
import uuid
from typing import Dict, Any, Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.gemini_agent import agent
from app.services.tts_service import tts_service

logger = logging.getLogger("voice_agent.websocket")

router = APIRouter(tags=["WebSocket Real-Time Voice"])


class ConnectionManager:
    """Manages active WebSocket connections."""

    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        self.active_connections[session_id] = websocket
        logger.info(f"WebSocket client connected: session {session_id}")

    def disconnect(self, session_id: str):
        if session_id in self.active_connections:
            del self.active_connections[session_id]
            logger.info(f"WebSocket client disconnected: session {session_id}")

    async def send_json(self, session_id: str, data: Dict[str, Any]):
        ws = self.active_connections.get(session_id)
        if ws:
            await ws.send_text(json.dumps(data))


manager = ConnectionManager()


@router.websocket("/ws/agent")
async def websocket_agent_endpoint(websocket: WebSocket, session_id: Optional[str] = None):
    """Full-duplex real-time voice streaming WebSocket endpoint."""
    sid = session_id or str(uuid.uuid4())
    await manager.connect(websocket, sid)

    # Send initial greeting & handshake
    await manager.send_json(sid, {
        "type": "connection_established",
        "session_id": sid,
        "agent": "Aria",
        "status": "idle",
        "message": "Executive Agent connected. Ready for voice interaction."
    })

    try:
        while True:
            raw_text = await websocket.receive_text()
            try:
                payload = json.loads(raw_text)
            except json.JSONDecodeError:
                await manager.send_json(sid, {"type": "error", "message": "Invalid JSON format."})
                continue

            msg_type = payload.get("type", "text_message")

            # 1. Heartbeat Ping / Pong
            if msg_type == "ping":
                await manager.send_json(sid, {"type": "pong", "timestamp": time.time()})
                continue

            # 2. Interruption signal (Barge-in)
            if msg_type == "interrupt":
                logger.info(f"Barge-in interrupt received for session {sid}")
                await manager.send_json(sid, {
                    "type": "status",
                    "status": "idle",
                    "message": "Playback interrupted by user."
                })
                continue

            # 3. Voice text or transcription message
            if msg_type in ("text_message", "voice_transcript"):
                user_text = payload.get("message") or payload.get("text", "")
                if not user_text.strip():
                    continue

                total_start_time = time.time()

                # Notify client: agent is thinking
                await manager.send_json(sid, {
                    "type": "status",
                    "status": "thinking",
                    "message": "Processing executive request..."
                })

                # Agent Reasoning & Tool Execution
                llm_start = time.time()
                agent_res = await agent.process_user_message(user_text, session_id=sid)
                llm_duration_ms = round((time.time() - llm_start) * 1000, 2)
                reply_text = agent_res.get("reply", "")
                tools_executed = agent_res.get("tools_executed", [])

                # Notify client if tools were executed & broadcast state sync
                if tools_executed:
                    await manager.send_json(sid, {
                        "type": "tool_executed",
                        "tools": tools_executed
                    })
                    await manager.send_json(sid, {
                        "type": "state_sync",
                        "updated": True
                    })

                # Send spoken transcript
                await manager.send_json(sid, {
                    "type": "speech_text",
                    "text": reply_text,
                    "mode": agent_res.get("mode", "simulation")
                })

                # Speech Synthesis & Audio Chunk Streaming
                await manager.send_json(sid, {
                    "type": "status",
                    "status": "speaking",
                    "message": "Synthesizing and streaming voice response..."
                })

                tts_start = time.time()
                await manager.send_json(sid, {"type": "audio_stream_start"})

                audio_chunk_count = 0
                async for chunk in tts_service.stream_audio_chunks(reply_text):
                    b64_audio = base64.b64encode(chunk).decode("utf-8")
                    await manager.send_json(sid, {
                        "type": "audio_chunk",
                        "data": b64_audio
                    })
                    audio_chunk_count += 1

                tts_duration_ms = round((time.time() - tts_start) * 1000, 2)
                await manager.send_json(sid, {"type": "audio_stream_end"})

                total_duration_ms = round((time.time() - total_start_time) * 1000, 2)

                # Send comprehensive latency metrics
                await manager.send_json(sid, {
                    "type": "latency_metrics",
                    "llm_latency_ms": llm_duration_ms,
                    "tts_latency_ms": tts_duration_ms,
                    "total_latency_ms": total_duration_ms,
                    "audio_chunks": audio_chunk_count
                })

                # Reset status to idle
                await manager.send_json(sid, {
                    "type": "status",
                    "status": "idle",
                    "message": "Awaiting next command."
                })

    except WebSocketDisconnect:
        manager.disconnect(sid)
    except Exception as exc:
        logger.error(f"WebSocket error in session {sid}: {exc}", exc_info=True)
        manager.disconnect(sid)
