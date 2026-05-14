from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    app_name: str = "AgriVani"
    backend_host: str = "127.0.0.1"
    backend_port: int = 8000
    frontend_port: int = 8501

    gemini_api_key: str = ""
    gemini_model: str = "gemini-3-flash"
    ai_provider: str = "auto"
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "llama3.1:8b"
    ollama_timeout_seconds: float = 6.0
    use_mock_ai: bool = False

    deepgram_api_key: str = ""
    deepgram_callback_secret: str = "local-dev-secret"
    public_base_url: str = ""

    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = "21m00Tcm4TlvDq8ikWAM"

    low_bandwidth_mode: bool = True
    historical_csv_path: Path = BASE_DIR / "data" / "historical_mandi_prices.csv"

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
