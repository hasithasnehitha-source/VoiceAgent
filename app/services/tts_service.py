import io
import logging
from typing import AsyncGenerator, Optional, List, Dict
import edge_tts

from app.core.config import settings

logger = logging.getLogger("voice_agent.tts")

# Popular curated high-fidelity neural voices
POPULAR_VOICES = [
    {"name": "en-US-AriaNeural", "gender": "Female", "locale": "en-US", "description": "Professional executive assistant (default)"},
    {"name": "en-US-GuyNeural", "gender": "Male", "locale": "en-US", "description": "Crisp, authoritative male voice"},
    {"name": "en-US-JennyNeural", "gender": "Female", "locale": "en-US", "description": "Warm, conversational voice"},
    {"name": "en-GB-SoniaNeural", "gender": "Female", "locale": "en-GB", "description": "British formal executive"},
    {"name": "en-AU-NatashaNeural", "gender": "Female", "locale": "en-AU", "description": "Australian natural accent"},
]


class TTSService:
    """High-fidelity text-to-speech service powered by Microsoft Edge Neural Voices."""

    def __init__(self, default_voice: Optional[str] = None):
        self.default_voice = default_voice or settings.DEFAULT_VOICE
        self.rate = settings.VOICE_RATE
        self.pitch = settings.VOICE_PITCH

    async def synthesize_to_bytes(
        self,
        text: str,
        voice: Optional[str] = None,
        rate: Optional[str] = None,
        pitch: Optional[str] = None
    ) -> bytes:
        """Synthesize text into full MP3 audio bytes."""
        clean_text = text.strip()
        if not clean_text:
            return b""

        selected_voice = voice or self.default_voice
        selected_rate = rate or self.rate
        selected_pitch = pitch or self.pitch

        logger.info(f"Synthesizing speech with voice '{selected_voice}': {clean_text[:60]}...")
        communicate = edge_tts.Communicate(
            text=clean_text,
            voice=selected_voice,
            rate=selected_rate,
            pitch=selected_pitch
        )

        audio_buffer = io.BytesIO()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_buffer.write(chunk["data"])

        return audio_buffer.getvalue()

    async def stream_audio_chunks(
        self,
        text: str,
        voice: Optional[str] = None,
        rate: Optional[str] = None,
        pitch: Optional[str] = None
    ) -> AsyncGenerator[bytes, None]:
        """Stream synthesized audio chunks as they are generated for low-latency playback."""
        clean_text = text.strip()
        if not clean_text:
            return

        selected_voice = voice or self.default_voice
        selected_rate = rate or self.rate
        selected_pitch = pitch or self.pitch

        communicate = edge_tts.Communicate(
            text=clean_text,
            voice=selected_voice,
            rate=selected_rate,
            pitch=selected_pitch
        )

        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                yield chunk["data"]

    @staticmethod
    def get_curated_voices() -> List[Dict[str, str]]:
        """Return list of recommended executive voices."""
        return POPULAR_VOICES


tts_service = TTSService()
