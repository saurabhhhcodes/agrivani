from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass

import httpx
import websockets

from backend.app.config import Settings


DEEPGRAM_LISTEN_WS = "wss://api.deepgram.com/v1/listen"
DEEPGRAM_PRERECORDED_URL = "https://api.deepgram.com/v1/listen"
DEEPGRAM_SUPPORTED_LANGUAGES = {
    "bn",
    "en",
    "gu",
    "hi",
    "kn",
    "ml",
    "mr",
    "pa",
    "ta",
    "te",
    "ur",
}


@dataclass
class TranscriptResult:
    request_id: str
    transcript: str
    language: str
    provider: str


class DeepgramService:
    def __init__(self, settings: Settings):
        self.settings = settings

    async def transcribe_stream(self, chunks: list[bytes], language: str) -> TranscriptResult:
        request_id = str(uuid.uuid4())
        if not self._has_real_key(self.settings.deepgram_api_key):
            return TranscriptResult(
                request_id=request_id,
                transcript="मेरा प्याज का आज मंडी भाव बताइए",
                language=language,
                provider="mock_deepgram",
            )

        audio = b"".join(chunks)
        if self.settings.public_base_url:
            try:
                return await self._transcribe_with_webhook(audio, language, request_id)
            except Exception:
                pass
        return await self._transcribe_live_ws(chunks, language, request_id)

    async def _transcribe_with_webhook(
        self, audio: bytes, language: str, request_id: str
    ) -> TranscriptResult:
        deepgram_language = self._deepgram_language(language)
        callback = (
            f"{self.settings.public_base_url.rstrip('/')}/webhooks/deepgram"
            f"?secret={self.settings.deepgram_callback_secret}&request_id={request_id}&language={language}"
        )
        params = {
            "model": "nova-3",
            "smart_format": "true",
            "language": deepgram_language,
            "callback": callback,
        }
        headers = {
            "Authorization": f"Token {self.settings.deepgram_api_key}",
            "Content-Type": "audio/webm",
        }
        async with httpx.AsyncClient(timeout=12.0) as client:
            response = await client.post(
                DEEPGRAM_PRERECORDED_URL,
                params=params,
                content=audio,
                headers=headers,
            )
            response.raise_for_status()
        return TranscriptResult(
            request_id=request_id,
            transcript="",
            language=language,
            provider="deepgram_webhook_pending",
        )

    async def _transcribe_live_ws(
        self, chunks: list[bytes], language: str, request_id: str
    ) -> TranscriptResult:
        deepgram_language = self._deepgram_language(language)
        params = f"model=nova-3&smart_format=true&interim_results=false&language={deepgram_language}"
        headers = {"Authorization": f"Token {self.settings.deepgram_api_key}"}
        transcript_parts: list[str] = []

        async with websockets.connect(f"{DEEPGRAM_LISTEN_WS}?{params}", additional_headers=headers) as ws:
            async def receiver() -> None:
                async for message in ws:
                    payload = json.loads(message)
                    channel = payload.get("channel", {})
                    alternatives = channel.get("alternatives", [])
                    if alternatives:
                        text = alternatives[0].get("transcript", "")
                        if text and payload.get("is_final", False):
                            transcript_parts.append(text)

            receive_task = asyncio.create_task(receiver())
            for chunk in chunks:
                await ws.send(chunk)
            await ws.send(json.dumps({"type": "CloseStream"}))
            try:
                await asyncio.wait_for(receive_task, timeout=5)
            except asyncio.TimeoutError:
                receive_task.cancel()

        return TranscriptResult(
            request_id=request_id,
            transcript=" ".join(transcript_parts).strip(),
            language=language,
            provider="deepgram_live_ws",
        )

    @staticmethod
    def parse_deepgram_webhook(payload: dict) -> str:
        channels = payload.get("results", {}).get("channels", [])
        pieces: list[str] = []
        for channel in channels:
            alternatives = channel.get("alternatives", [])
            if alternatives and alternatives[0].get("transcript"):
                pieces.append(alternatives[0]["transcript"])
        return " ".join(pieces).strip()

    @staticmethod
    def _has_real_key(value: str) -> bool:
        return bool(value and not value.startswith("replace_with"))

    @staticmethod
    def _deepgram_language(language: str) -> str:
        return language if language in DEEPGRAM_SUPPORTED_LANGUAGES else "hi"
