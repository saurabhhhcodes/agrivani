from __future__ import annotations

import base64
import hashlib
import asyncio
from pathlib import Path

import httpx
from gtts import gTTS

from backend.app.config import BASE_DIR, Settings


ELEVENLABS_TTS_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"

GTTS_LANGUAGE_MAP = {
    "as": "bn",
    "bn": "bn",
    "brx": "hi",
    "doi": "hi",
    "en": "en",
    "gu": "gu",
    "hi": "hi",
    "kn": "kn",
    "kok": "hi",
    "ks": "ur",
    "mai": "hi",
    "ml": "ml",
    "mni": "bn",
    "mr": "mr",
    "ne": "ne",
    "or": "or",
    "pa": "pa",
    "sa": "hi",
    "sat": "hi",
    "sd": "ur",
    "ta": "ta",
    "te": "te",
    "ur": "ur",
}


class ElevenLabsTTS:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.audio_dir = BASE_DIR / "backend" / "static" / "audio"
        self.audio_dir.mkdir(parents=True, exist_ok=True)

    async def synthesize(self, text: str, language: str) -> str | None:
        digest = hashlib.sha256(f"tts-v2:{language}:{text}".encode("utf-8")).hexdigest()[:18]
        audio_path = self.audio_dir / f"{digest}.mp3"
        if audio_path.exists():
            return f"/static/audio/{audio_path.name}"

        if not self._has_real_key(self.settings.elevenlabs_api_key):
            await self._write_gtts_mp3(text, language, audio_path)
            return f"/static/audio/{audio_path.name}"

        url = ELEVENLABS_TTS_URL.format(voice_id=self.settings.elevenlabs_voice_id)
        headers = {
            "xi-api-key": self.settings.elevenlabs_api_key,
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
        }
        payload = {
            "text": text[:1400],
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {"stability": 0.52, "similarity_boost": 0.74},
        }
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                audio_path.write_bytes(response.content)
        except Exception:
            await self._write_gtts_mp3(text, language, audio_path)
        return f"/static/audio/{audio_path.name}"

    async def _write_gtts_mp3(self, text: str, language: str, path: Path) -> None:
        gtts_language = GTTS_LANGUAGE_MAP.get(language, "hi")
        try:
            await asyncio.to_thread(
                gTTS(text=text[:1400], lang=gtts_language, slow=False).save,
                str(path),
            )
        except Exception:
            self._write_placeholder_mp3(path)

    @staticmethod
    def _write_placeholder_mp3(path: Path) -> None:
        silent_mp3_base64 = (
            "SUQzBAAAAAAAI1RTU0UAAAAPAAADTGF2ZjU5LjI3LjEwMAAAAAAAAAAAAAAA//tQxAADBpAAAANIAAAA"
            "AABAAABpAAAACAAADSAAAAEAAAGkAAAAIAAANIAAAAP/7UMQAg8AAANIAAAAABAAAAAQAAAARAAAAB"
            "EAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        )
        path.write_bytes(base64.b64decode(silent_mp3_base64 + "==="))

    @staticmethod
    def _has_real_key(value: str) -> bool:
        return bool(value and not value.startswith("replace_with"))
