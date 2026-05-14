from __future__ import annotations

import json
import re
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.app.config import Settings, get_settings
from backend.app.models import AgentResponse, FarmerQuery, Language, MandiPriceRequest
from backend.app.services.deepgram_service import DeepgramService
from backend.app.services.gemini_agent import GeminiAgent
from backend.app.services.mandi_price_engine import MandiPriceEngine
from backend.app.services.tts_service import ElevenLabsTTS


app = FastAPI(
    title="AgriVani API",
    description="Real-time multilingual AgriTech voice platform.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="backend/static"), name="static")

pending_transcripts: dict[str, dict] = {}

LANGUAGE_LABELS = {
    "as": "Assamese",
    "bn": "Bengali",
    "brx": "Bodo",
    "doi": "Dogri",
    "en": "English",
    "gu": "Gujarati",
    "hi": "Hindi",
    "kn": "Kannada",
    "kok": "Konkani",
    "ks": "Kashmiri",
    "mai": "Maithili",
    "ml": "Malayalam",
    "mni": "Manipuri",
    "mr": "Marathi",
    "ne": "Nepali",
    "or": "Odia",
    "pa": "Punjabi",
    "sa": "Sanskrit",
    "sat": "Santali",
    "sd": "Sindhi",
    "ta": "Tamil",
    "te": "Telugu",
    "ur": "Urdu",
}

INDIAN_STATES_AND_UTS = [
    "Andhra Pradesh",
    "Arunachal Pradesh",
    "Assam",
    "Bihar",
    "Chhattisgarh",
    "Delhi",
    "Goa",
    "Gujarat",
    "Haryana",
    "Himachal Pradesh",
    "Jammu and Kashmir",
    "Jharkhand",
    "Karnataka",
    "Kerala",
    "Ladakh",
    "Madhya Pradesh",
    "Maharashtra",
    "Manipur",
    "Meghalaya",
    "Mizoram",
    "Nagaland",
    "Odisha",
    "Punjab",
    "Rajasthan",
    "Sikkim",
    "Tamil Nadu",
    "Telangana",
    "Tripura",
    "Uttar Pradesh",
    "Uttarakhand",
    "West Bengal",
    "Andaman and Nicobar Islands",
    "Chandigarh",
    "Dadra and Nagar Haveli and Daman and Diu",
    "Lakshadweep",
    "Puducherry",
]

MAJOR_MANDIS_BY_STATE = {
    "Andhra Pradesh": ["Guntur", "Vijayawada", "Kurnool"],
    "Assam": ["Guwahati", "Jorhat", "Dibrugarh"],
    "Bihar": ["Patna", "Muzaffarpur", "Purnea"],
    "Delhi": ["Delhi", "Azadpur"],
    "Gujarat": ["Ahmedabad", "Rajkot", "Unjha"],
    "Haryana": ["Karnal", "Hisar", "Sirsa"],
    "Karnataka": ["Bengaluru", "Mysuru", "Hubballi"],
    "Kerala": ["Kochi", "Kozhikode", "Thrissur"],
    "Madhya Pradesh": ["Indore", "Bhopal", "Neemuch"],
    "Maharashtra": ["Pune", "Nashik", "Lasalgaon", "Nagpur"],
    "Odisha": ["Bhubaneswar", "Cuttack", "Sambalpur"],
    "Punjab": ["Ludhiana", "Amritsar", "Jalandhar"],
    "Rajasthan": ["Jaipur", "Kota", "Jodhpur"],
    "Tamil Nadu": ["Chennai", "Madurai", "Coimbatore"],
    "Telangana": ["Hyderabad", "Warangal", "Nizamabad"],
    "Uttar Pradesh": ["Lucknow", "Kanpur", "Varanasi"],
    "Uttarakhand": ["Dehradun", "Haldwani"],
    "West Bengal": ["Kolkata", "Siliguri", "Burdwan"],
}

SUPPORTED_CROPS = {
    "onion": ["onion", "प्याज", "कांदा"],
    "tomato": ["tomato", "टमाटर", "टोमॅटो"],
    "soybean": ["soybean", "सोयाबीन"],
    "wheat": ["wheat", "गेहूं", "गहू"],
    "cotton": ["cotton", "कपास", "कापूस"],
    "rice": ["rice", "paddy", "धान", "चावल", "तांदूळ"],
    "maize": ["maize", "corn", "मक्का", "मकई"],
    "potato": ["potato", "आलू", "बटाटा"],
    "mustard": ["mustard", "सरसों", "मोहरी"],
    "tur": ["tur", "arhar", "pigeon pea", "अरहर", "तूर"],
    "chana": ["chana", "gram", "चना", "हरभरा"],
    "groundnut": ["groundnut", "peanut", "मूंगफली", "भुईमूग"],
    "chilli": ["chilli", "chili", "mirchi", "मिर्च", "मिर्ची"],
    "coconut": ["coconut", "नारियल", "नारळ"],
}


def settings_dep() -> Settings:
    return get_settings()


def get_price_engine(settings: Annotated[Settings, Depends(settings_dep)]) -> MandiPriceEngine:
    return MandiPriceEngine(settings.historical_csv_path)


def extract_crop_market(text: str, fallback_crop: str | None, fallback_market: str | None) -> tuple[str, str]:
    lowered = text.lower()
    markets = sorted({market for items in MAJOR_MANDIS_BY_STATE.values() for market in items})

    crop = fallback_crop or "onion"
    for canonical, aliases in SUPPORTED_CROPS.items():
        if any(alias in lowered for alias in aliases):
            crop = canonical
            break

    market = fallback_market or "Pune"
    for candidate in markets:
        if re.search(candidate.lower(), lowered):
            market = candidate
            break
    return crop.title(), market


def infer_state(text: str, fallback_state: str | None, market: str) -> str:
    lowered = text.lower()
    if fallback_state:
        return fallback_state
    for state in INDIAN_STATES_AND_UTS:
        if state.lower() in lowered:
            return state
    for state, markets in MAJOR_MANDIS_BY_STATE.items():
        if market in markets:
            return state
    return "India"


@app.get("/health")
async def health(settings: Annotated[Settings, Depends(settings_dep)]) -> dict:
    return {
        "status": "ok",
        "app": settings.app_name,
        "low_bandwidth_mode": settings.low_bandwidth_mode,
    }


@app.get("/api/languages")
async def languages() -> dict:
    return {
        "languages": [
            {"code": code, "label": label}
            for code, label in LANGUAGE_LABELS.items()
        ],
        "note": (
            "AgriVani accepts all Indian scheduled-language codes. "
            "Provider-specific STT/TTS adapters fall back to the nearest supported Indian language when required."
        ),
    }


@app.get("/api/india/coverage")
async def india_coverage(settings: Annotated[Settings, Depends(settings_dep)]) -> dict:
    return {
        "ai_provider": settings.ai_provider,
        "ollama_base_url": settings.ollama_base_url,
        "ollama_model": settings.ollama_model,
        "states_and_uts": INDIAN_STATES_AND_UTS,
        "major_mandis_by_state": MAJOR_MANDIS_BY_STATE,
        "supported_crops": sorted(crop.title() for crop in SUPPORTED_CROPS),
    }


@app.post("/api/mandi/price")
async def mandi_price(
    request: MandiPriceRequest,
    engine: Annotated[MandiPriceEngine, Depends(get_price_engine)],
):
    return await engine.get_price(request.crop, request.market, request.state)


@app.post("/api/agent/ask", response_model=AgentResponse)
async def ask_agent(
    query: FarmerQuery,
    settings: Annotated[Settings, Depends(settings_dep)],
    engine: Annotated[MandiPriceEngine, Depends(get_price_engine)],
):
    crop, market = extract_crop_market(query.text, query.crop, query.market)
    state = infer_state(query.text, query.state, market)
    price = await engine.get_price(crop, market, state)
    answer_text = await GeminiAgent(settings).answer(query, price)
    audio_url = await ElevenLabsTTS(settings).synthesize(answer_text, query.language.value)
    return AgentResponse(
        answer_text=answer_text,
        language=query.language,
        mandi_price=price,
        advisory=[
            "Check today arrivals before selling.",
            "Prefer local cooperative transport when prices are favorable.",
            "Use the AI prediction only as guidance when live data is unavailable.",
        ],
        audio_url=audio_url,
    )


@app.websocket("/api/voice/ws")
async def voice_ws(websocket: WebSocket):
    await websocket.accept()
    settings = get_settings()
    chunks: list[bytes] = []
    language = Language.hindi.value
    mode = "ask"

    try:
        await websocket.send_json({"type": "ready", "message": "AgriVani voice channel ready"})
        while True:
            message = await websocket.receive()
            if "text" in message:
                payload = json.loads(message["text"])
                if payload.get("type") == "config":
                    language = payload.get("language", language)
                    mode = payload.get("mode", mode)
                    await websocket.send_json({"type": "configured", "language": language})
                elif payload.get("type") == "stop":
                    break
            elif "bytes" in message:
                chunks.append(message["bytes"])
                if len(chunks) % 6 == 0:
                    await websocket.send_json({"type": "chunk_ack", "chunks": len(chunks)})
    except WebSocketDisconnect:
        return

    deepgram = DeepgramService(settings)
    transcript = await deepgram.transcribe_stream(chunks, language)
    await websocket.send_json(
        {
            "type": "transcript",
            "request_id": transcript.request_id,
            "transcript": transcript.transcript,
            "provider": transcript.provider,
        }
    )

    if mode == "transcribe_only":
        await websocket.send_json(
            {
                "type": "voice_text_ready",
                "transcript": transcript.transcript,
                "language": language,
            }
        )
        await websocket.close()
        return

    if transcript.provider == "deepgram_webhook_pending":
        await websocket.send_json(
            {
                "type": "pending",
                "message": "Deepgram webhook accepted. Poll /api/voice/transcript/{request_id}.",
                "request_id": transcript.request_id,
            }
        )
        await websocket.close()
        return

    crop, market = extract_crop_market(transcript.transcript, None, None)
    state = infer_state(transcript.transcript, None, market)
    price = await MandiPriceEngine(settings.historical_csv_path).get_price(crop, market, state)
    query = FarmerQuery(text=transcript.transcript or "मंडी भाव बताइए", language=Language(language), crop=crop, market=market, state=state)
    answer = await GeminiAgent(settings).answer(query, price)
    audio_url = await ElevenLabsTTS(settings).synthesize(answer, language)
    await websocket.send_json(
        {
            "type": "answer",
            "answer_text": answer,
            "audio_url": audio_url,
            "mandi_price": price.model_dump(),
        }
    )
    await websocket.close()


@app.post("/webhooks/deepgram")
async def deepgram_webhook(
    payload: dict,
    request_id: str = Query(...),
    language: str = Query(Language.hindi.value),
    secret: str = Query(...),
    settings: Settings = Depends(settings_dep),
):
    if secret != settings.deepgram_callback_secret:
        raise HTTPException(status_code=401, detail="Invalid Deepgram callback secret")
    transcript = DeepgramService.parse_deepgram_webhook(payload)
    pending_transcripts[request_id] = {
        "request_id": request_id,
        "transcript": transcript,
        "language": language,
        "raw": payload,
    }
    return JSONResponse({"ok": True, "request_id": request_id})


@app.get("/api/voice/transcript/{request_id}")
async def get_voice_transcript(request_id: str):
    if request_id not in pending_transcripts:
        return JSONResponse({"status": "pending", "request_id": request_id}, status_code=202)
    return {"status": "ready", **pending_transcripts[request_id]}
