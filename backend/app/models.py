from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class Language(str, Enum):
    assamese = "as"
    bengali = "bn"
    bodo = "brx"
    dogri = "doi"
    english = "en"
    gujarati = "gu"
    hindi = "hi"
    kannada = "kn"
    kashmiri = "ks"
    konkani = "kok"
    maithili = "mai"
    malayalam = "ml"
    manipuri = "mni"
    marathi = "mr"
    nepali = "ne"
    odia = "or"
    punjabi = "pa"
    sanskrit = "sa"
    santali = "sat"
    sindhi = "sd"
    tamil = "ta"
    telugu = "te"
    urdu = "ur"


class FarmerQuery(BaseModel):
    text: str = Field(..., min_length=1)
    language: Language = Language.hindi
    crop: str | None = None
    market: str | None = None
    state: str | None = None


class MandiPriceRequest(BaseModel):
    crop: str = Field(..., min_length=1)
    market: str = Field("Pune", min_length=1)
    state: str = Field("Maharashtra", min_length=1)


class MandiPriceResponse(BaseModel):
    crop: str
    market: str
    state: str
    min_price: float
    modal_price: float
    max_price: float
    unit: str = "INR/quintal"
    source: str
    confidence: float = Field(ge=0, le=1)
    explanation: str
    observations: list[dict[str, Any]] = Field(default_factory=list)


class AgentResponse(BaseModel):
    answer_text: str
    language: Language
    mandi_price: MandiPriceResponse | None = None
    advisory: list[str] = Field(default_factory=list)
    audio_url: str | None = None


class VoiceWebhookPayload(BaseModel):
    request_id: str
    transcript: str
    language: Language = Language.hindi
    metadata: dict[str, Any] = Field(default_factory=dict)
