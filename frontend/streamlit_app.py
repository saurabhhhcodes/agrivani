from __future__ import annotations

import csv
import hashlib
import os
from pathlib import Path

import requests
import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv
from gtts import gTTS


load_dotenv()

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_PATH = BASE_DIR / "data" / "historical_mandi_prices.csv"
AUDIO_DIR = BASE_DIR / "backend" / "static" / "audio"
AUDIO_DIR.mkdir(parents=True, exist_ok=True)

for secret_name in [
    "GEMINI_API_KEY",
    "GEMINI_MODEL",
    "AI_PROVIDER",
    "OLLAMA_BASE_URL",
    "OLLAMA_MODEL",
    "OLLAMA_TIMEOUT_SECONDS",
    "ELEVENLABS_API_KEY",
    "ELEVENLABS_VOICE_ID",
]:
    try:
        if secret_name in st.secrets and not os.getenv(secret_name):
            os.environ[secret_name] = str(st.secrets[secret_name])
    except Exception:
        pass

BACKEND_HOST = os.getenv("BACKEND_HOST", "127.0.0.1")
BACKEND_PORT = os.getenv("BACKEND_PORT", "8000")
API_BASE = f"http://{BACKEND_HOST}:{BACKEND_PORT}"
WS_BASE = f"ws://{BACKEND_HOST}:{BACKEND_PORT}"

LANGUAGES = {
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

STATES_AND_UTS = [
    "India",
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
]

CROPS = [
    "Onion",
    "Tomato",
    "Soybean",
    "Wheat",
    "Cotton",
    "Rice",
    "Maize",
    "Potato",
    "Mustard",
    "Tur",
    "Chana",
    "Groundnut",
    "Chilli",
    "Coconut",
]

MARKETS = [
    "Pune",
    "Lucknow",
    "Azadpur",
    "Bengaluru",
    "Bhopal",
    "Chennai",
    "Guntur",
    "Guwahati",
    "Hyderabad",
    "Indore",
    "Jaipur",
    "Kochi",
    "Kolkata",
    "Lasalgaon",
    "Ludhiana",
    "Nagpur",
    "Nashik",
    "Patna",
    "Rajkot",
    "Varanasi",
]

BROWSER_SPEECH_LANGS = {
    "as": "as-IN",
    "bn": "bn-IN",
    "brx": "hi-IN",
    "doi": "hi-IN",
    "en": "en-IN",
    "gu": "gu-IN",
    "hi": "hi-IN",
    "kn": "kn-IN",
    "kok": "hi-IN",
    "ks": "ur-IN",
    "mai": "hi-IN",
    "ml": "ml-IN",
    "mni": "bn-IN",
    "mr": "mr-IN",
    "ne": "ne-IN",
    "or": "or-IN",
    "pa": "pa-IN",
    "sa": "hi-IN",
    "sat": "hi-IN",
    "sd": "ur-IN",
    "ta": "ta-IN",
    "te": "te-IN",
    "ur": "ur-IN",
}


def backend_health() -> bool:
    try:
        response = requests.get(f"{API_BASE}/health", timeout=1.5)
        return response.status_code == 200
    except Exception:
        return False


BACKEND_AVAILABLE = backend_health()


def local_price(crop: str, market: str, state: str) -> dict:
    rows = []
    with DATA_PATH.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            for key in ["min_price", "modal_price", "max_price"]:
                row[key] = float(row[key])
            rows.append(row)

    def matches(row, exact_market: bool) -> bool:
        crop_ok = row["crop"].lower() == crop.lower()
        state_ok = state == "India" or row["state"].lower() == state.lower()
        market_ok = row["market"].lower() == market.lower() if exact_market else True
        return crop_ok and state_ok and market_ok

    sample = [row for row in rows if matches(row, True)]
    confidence = 0.79
    if len(sample) < 3:
        sample = [row for row in rows if matches(row, False)]
        confidence = 0.64
    if len(sample) < 3:
        sample = [row for row in rows if row["crop"].lower() == crop.lower()]
        confidence = 0.52
    if len(sample) < 3:
        sample = rows
        confidence = 0.4

    sample = sorted(sample, key=lambda row: row["date"])[-8:]
    weights = list(range(1, len(sample) + 1))
    total_weight = sum(weights)

    def weighted(column: str) -> float:
        return round(sum(row[column] * weight for row, weight in zip(sample, weights)) / total_weight, 2)

    return {
        "crop": crop,
        "market": market,
        "state": state,
        "min_price": weighted("min_price"),
        "modal_price": weighted("modal_price"),
        "max_price": weighted("max_price"),
        "unit": "INR/quintal",
        "source": "historical_csv_ai_prediction",
        "confidence": confidence,
        "explanation": (
            "Agmarknet live backend is not available in Streamlit Cloud mode. "
            "This price is an AI-assisted prediction from recent historical CSV trends."
        ),
        "observations": [
            {
                "date": row["date"],
                "crop": row["crop"],
                "market": row["market"],
                "state": row["state"],
                "min_price": row["min_price"],
                "modal_price": row["modal_price"],
                "max_price": row["max_price"],
            }
            for row in sample
        ],
    }


def mock_answer(query: str, language: str, price: dict) -> str:
    if language == "en":
        return (
            f"Quick advisory: The expected modal price for {price['crop']} in "
            f"{price['market']} is INR {price['modal_price']}/quintal. Check local arrivals, "
            "compare transport cost, and avoid distress selling when prices are volatile."
        )
    if language == "mr":
        return (
            f"जलद सल्ला: {price['market']} मध्ये {price['crop']} चा अंदाजे भाव "
            f"{price['modal_price']} रुपये/क्विंटल आहे. स्थानिक आवक तपासा आणि विक्री टप्प्याटप्प्याने करा."
        )
    return (
        f"त्वरित सलाह: {price['market']} में {price['crop']} का अनुमानित मॉडल भाव "
        f"{price['modal_price']} रुपये/क्विंटल है. स्थानीय आवक देखें, जल्दबाज़ी में बिक्री न करें, "
        "और भाव बदलने पर किस्तों में बेचें."
    )


def ollama_answer(query: str, language: str, price: dict) -> str | None:
    provider = os.getenv("AI_PROVIDER", "mock").lower()
    base_url = os.getenv("OLLAMA_BASE_URL", "").strip()
    if provider != "ollama" or not base_url:
        return None
    prompt = (
        "You are AgriVani, a practical agricultural advisor for Indian farmers. "
        f"Answer in language code {language}. Question: {query}. "
        f"Mandi context: {price}"
    )
    try:
        response = requests.post(
            f"{base_url.rstrip('/')}/api/chat",
            json={
                "model": os.getenv("OLLAMA_MODEL", "llama3.1:8b"),
                "stream": False,
                "messages": [
                    {"role": "system", "content": "Keep answers short, actionable, and farmer-friendly."},
                    {"role": "user", "content": prompt},
                ],
            },
            timeout=float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "2")),
        )
        response.raise_for_status()
        return response.json().get("message", {}).get("content", "").strip() or None
    except Exception:
        return None


def make_audio(text: str, language: str) -> str | None:
    gtts_language = {
        "bn": "bn",
        "en": "en",
        "gu": "gu",
        "hi": "hi",
        "kn": "kn",
        "ml": "ml",
        "mr": "mr",
        "ne": "ne",
        "or": "or",
        "pa": "pa",
        "ta": "ta",
        "te": "te",
        "ur": "ur",
    }.get(language, "hi")
    digest = hashlib.sha256(f"streamlit-cloud:{language}:{text}".encode("utf-8")).hexdigest()[:18]
    audio_path = AUDIO_DIR / f"{digest}.mp3"
    if not audio_path.exists():
        try:
            gTTS(text=text[:1400], lang=gtts_language, slow=False).save(str(audio_path))
        except Exception:
            return None
    return str(audio_path)


def local_agent(query: str, language: str, crop: str, market: str, state: str) -> dict:
    price = local_price(crop, market, state)
    answer_text = ollama_answer(query, language, price) or mock_answer(query, language, price)
    audio_path = make_audio(answer_text, language)
    return {
        "answer_text": answer_text,
        "language": language,
        "mandi_price": price,
        "advisory": [
            "Check today arrivals before selling.",
            "Compare nearest mandi and transport cost.",
            "Use predicted prices as guidance when live data is unavailable.",
        ],
        "audio_url": None,
        "audio_path": audio_path,
    }


def post_agent(query: str, language: str, crop: str, market: str, state: str) -> dict:
    if BACKEND_AVAILABLE:
        try:
            response = requests.post(
                f"{API_BASE}/api/agent/ask",
                json={
                    "text": query,
                    "language": language,
                    "crop": crop,
                    "market": market,
                    "state": state,
                },
                timeout=45,
            )
            response.raise_for_status()
            payload = response.json()
            payload["mode"] = "fastapi"
            return payload
        except Exception:
            pass
    payload = local_agent(query, language, crop, market, state)
    payload["mode"] = "streamlit-cloud"
    return payload


def post_price(crop: str, market: str, state: str) -> dict:
    if BACKEND_AVAILABLE:
        try:
            response = requests.post(
                f"{API_BASE}/api/mandi/price",
                json={"crop": crop, "market": market, "state": state},
                timeout=20,
            )
            response.raise_for_status()
            payload = response.json()
            payload["mode"] = "fastapi"
            return payload
        except Exception:
            pass
    payload = local_price(crop, market, state)
    payload["mode"] = "streamlit-cloud"
    return payload

params = st.query_params
voice_text = params.get("voice_text", "")
voice_lang = params.get("voice_lang", "hi")
if voice_lang not in LANGUAGES:
    voice_lang = "hi"

st.set_page_config(page_title="AgriVani", page_icon="🌾", layout="wide")

st.markdown(
    """
    <style>
      :root {
        --leaf: #1f7a4d;
        --soil: #5a4634;
        --sun: #f4b942;
        --mist: #eef7f0;
        --ink: #1d2521;
      }
      .block-container { padding-top: 1.25rem; max-width: 1180px; }
      .agri-header {
        display: flex; align-items: center; justify-content: space-between;
        padding: 18px 0 14px; border-bottom: 1px solid #d8e8dd;
      }
      .agri-title { font-size: 38px; font-weight: 800; color: var(--ink); line-height: 1.05; }
      .agri-subtitle { color: #466055; font-size: 16px; margin-top: 6px; max-width: 680px; }
      .metric-row { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin: 16px 0; }
      .metric {
        border: 1px solid #d8e8dd; border-radius: 8px; padding: 14px 16px;
        background: #fbfdfb;
      }
      .metric b { display: block; font-size: 24px; color: var(--leaf); }
      .metric span { color: #50635a; font-size: 13px; }
      .voice-shell {
        position: fixed; right: 28px; bottom: 26px; z-index: 99999;
      }
      .voice-panel {
        width: 340px; border: 1px solid #cfe5d4; background: white; border-radius: 8px;
        box-shadow: 0 16px 44px rgba(31, 70, 49, .18); padding: 12px;
        font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      }
      .voice-btn {
        width: 100%; border: 0; border-radius: 8px; background: #1f7a4d; color: white;
        padding: 13px 14px; font-weight: 750; cursor: pointer; font-size: 15px;
      }
      .voice-btn.recording { background: #b42318; }
      .voice-status { color: #42574d; font-size: 13px; min-height: 42px; margin-top: 9px; line-height: 1.35; }
      .voice-select { width: 100%; padding: 8px; margin-bottom: 8px; border: 1px solid #cfe5d4; border-radius: 6px; }
      .voice-result { max-height: 190px; overflow-y: auto; color: #1d2521; font-size: 13px; line-height: 1.45; }
      @media (max-width: 720px) {
        .agri-title { font-size: 30px; }
        .metric-row { grid-template-columns: 1fr; }
        .voice-shell { right: 12px; left: 12px; bottom: 12px; }
        .voice-panel { width: auto; }
      }
    </style>
    """,
    unsafe_allow_html=True,
)

provider_label = "FastAPI backend" if BACKEND_AVAILABLE else "Streamlit Cloud single-app"

st.markdown(
    f"""
    <div class="agri-header">
      <div>
        <div class="agri-title">AgriVani</div>
        <div class="agri-subtitle">
          Real-time multilingual agri advisory for Indian farmers,
          optimized for low-bandwidth rural networks.
        </div>
      </div>
    </div>
    <div class="metric-row">
      <div class="metric"><b>40%</b><span>Target reduction in advisory and market-discovery cost</span></div>
      <div class="metric"><b>&lt; 60 KB</b><span>Chunked voice packets for unstable mobile data</span></div>
      <div class="metric"><b>Pan-India</b><span>States, UTs, major mandis, and local Ollama support</span></div>
    </div>
    <div style="color:#50635a; font-size:13px; margin: -4px 0 14px;">
      Runtime: {provider_label}
    </div>
    """,
    unsafe_allow_html=True,
)

left, right = st.columns([0.55, 0.45], gap="large")

with left:
    st.subheader("Ask AgriVani")
    language_codes = list(LANGUAGES.keys())
    language = st.selectbox(
        "Language",
        language_codes,
        index=language_codes.index(voice_lang),
        format_func=lambda x: LANGUAGES[x],
    )
    inline_language_options = "\n".join(
        f'<option value="{code}"{" selected" if code == language else ""}>{label}</option>'
        for code, label in LANGUAGES.items()
    )
    inline_voice_component = f"""
    <style>
      .voice-panel {{
        border: 1px solid #cfe5d4; background: #fbfdfb; border-radius: 8px;
        padding: 12px; margin: 4px 0 12px;
        font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      }}
      .voice-row {{ display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }}
      .voice-select {{ width: 100%; padding: 9px; border: 1px solid #cfe5d4; border-radius: 6px; }}
      .voice-btn {{
        border: 0; border-radius: 8px; background: #1f7a4d; color: white;
        padding: 10px 12px; font-weight: 750; cursor: pointer; font-size: 14px;
      }}
      .voice-btn.recording {{ background: #b42318; }}
      .voice-status {{ color: #42574d; font-size: 13px; min-height: 36px; margin-top: 8px; line-height: 1.35; }}
      .voice-result {{ color: #1d2521; font-size: 13px; line-height: 1.45; }}
      @media (max-width: 640px) {{ .voice-row {{ grid-template-columns: 1fr; }} }}
    </style>
    <div class="voice-panel">
      <div class="voice-row">
        <select id="agri-lang-inline" class="voice-select">{inline_language_options}</select>
        <button id="agri-voice-inline" class="voice-btn">Voice to Text</button>
      </div>
      <div id="agri-status-inline" class="voice-status">Speak the farmer question, then tap again to fill the text box.</div>
      <div id="agri-result-inline" class="voice-result"></div>
    </div>
    <script>
    const wsBaseInline = "{WS_BASE}";
    const browserSpeechLangs = {BROWSER_SPEECH_LANGS};
    let recorderInline = null;
    let socketInline = null;
    let recordingInline = false;
    let recognitionInline = null;
    const buttonInline = document.getElementById("agri-voice-inline");
    const statusInline = document.getElementById("agri-status-inline");
    const resultInline = document.getElementById("agri-result-inline");
    const langInline = document.getElementById("agri-lang-inline");
    function setInlineStatus(text) {{ statusInline.textContent = text; }}
    function fillVoiceText(transcript, language) {{
      const nextUrl = new URL(window.parent.location.href);
      nextUrl.searchParams.set("voice_text", transcript || "");
      nextUrl.searchParams.set("voice_lang", language || langInline.value);
      window.parent.location.href = nextUrl.toString();
    }}
    function startBrowserSpeech() {{
      const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
      if (!SpeechRecognition) return false;
      recognitionInline = new SpeechRecognition();
      recognitionInline.lang = browserSpeechLangs[langInline.value] || "hi-IN";
      recognitionInline.interimResults = true;
      recognitionInline.continuous = false;
      let finalTranscript = "";
      recognitionInline.onstart = () => {{
        recordingInline = true;
        buttonInline.classList.add("recording");
        buttonInline.textContent = "Fill Question";
        setInlineStatus("Listening in the browser. Tap again when finished.");
      }};
      recognitionInline.onresult = (event) => {{
        let interim = "";
        for (let i = event.resultIndex; i < event.results.length; i++) {{
          const piece = event.results[i][0].transcript;
          if (event.results[i].isFinal) finalTranscript += piece;
          else interim += piece;
        }}
        resultInline.innerHTML = `<b>Transcript:</b> ${{finalTranscript || interim || "Listening..."}}`;
      }};
      recognitionInline.onerror = (event) => {{
        setInlineStatus(`Voice recognition error: ${{event.error}}`);
        recordingInline = false;
        buttonInline.classList.remove("recording");
        buttonInline.textContent = "Voice to Text";
      }};
      recognitionInline.onend = () => {{
        recordingInline = false;
        buttonInline.classList.remove("recording");
        buttonInline.textContent = "Voice to Text";
        if (finalTranscript.trim()) fillVoiceText(finalTranscript.trim(), langInline.value);
        else setInlineStatus("No speech captured. Try again close to the microphone.");
      }};
      recognitionInline.start();
      return true;
    }}
    async function startInlineVoice() {{
      if (startBrowserSpeech()) return;
      resultInline.innerHTML = "";
      socketInline = new WebSocket(`${{wsBaseInline}}/api/voice/ws`);
      socketInline.binaryType = "arraybuffer";
      socketInline.onopen = () => {{
        socketInline.send(JSON.stringify({{type: "config", language: langInline.value, mode: "transcribe_only"}}));
        setInlineStatus("Recording. Tap again when finished.");
      }};
      socketInline.onmessage = (event) => {{
        const data = JSON.parse(event.data);
        if (data.type === "transcript") {{
          resultInline.innerHTML = `<b>Transcript:</b> ${{data.transcript || "Processing..."}}`;
        }}
        if (data.type === "voice_text_ready") {{
          fillVoiceText(data.transcript || "", data.language || langInline.value);
        }}
      }};
      socketInline.onerror = () => setInlineStatus("Voice connection failed. Check microphone permission.");
      const stream = await navigator.mediaDevices.getUserMedia({{
        audio: {{ channelCount: 1, echoCancellation: true, noiseSuppression: true, sampleRate: 16000 }}
      }});
      recorderInline = new MediaRecorder(stream, {{ mimeType: "audio/webm;codecs=opus", audioBitsPerSecond: 24000 }});
      recorderInline.ondataavailable = async (event) => {{
        if (event.data.size > 0 && socketInline && socketInline.readyState === WebSocket.OPEN) {{
          socketInline.send(await event.data.arrayBuffer());
        }}
      }};
      recorderInline.start(900);
      recordingInline = true;
      buttonInline.classList.add("recording");
      buttonInline.textContent = "Fill Question";
    }}
    function stopInlineVoice() {{
      if (recognitionInline) {{
        recognitionInline.stop();
        return;
      }}
      if (recorderInline && recorderInline.state !== "inactive") recorderInline.stop();
      if (socketInline && socketInline.readyState === WebSocket.OPEN) {{
        setTimeout(() => socketInline.send(JSON.stringify({{type: "stop"}})), 350);
      }}
      recordingInline = false;
      buttonInline.classList.remove("recording");
      buttonInline.textContent = "Voice to Text";
      setInlineStatus("Transcribing speech to the farmer question field...");
    }}
    buttonInline.addEventListener("click", async () => {{
      try {{
        if (!recordingInline) await startInlineVoice();
        else stopInlineVoice();
      }} catch (err) {{
        setInlineStatus(`Microphone error: ${{err.message}}`);
      }}
    }});
    </script>
    """
    components.html(inline_voice_component, height=160)
    query = st.text_area(
        "Farmer question",
        value=voice_text or "मेरा प्याज का आज मंडी भाव बताइए",
        height=120,
    )
    col_a, col_b, col_c = st.columns(3)
    crop = col_a.selectbox("Crop", CROPS, index=0)
    market = col_b.selectbox("Market", MARKETS, index=0)
    state = col_c.selectbox("State/UT", STATES_AND_UTS, index=STATES_AND_UTS.index("Maharashtra"))

    if st.button("Get Advisory", type="primary", use_container_width=True):
        with st.spinner("Asking Gemini/Ollama agent and MandiPriceEngine..."):
            try:
                payload = post_agent(query, language, crop, market, state)
                st.success(payload["answer_text"])
                if payload.get("audio_path"):
                    st.audio(payload["audio_path"])
                    st.caption("Audio generated inside Streamlit Cloud with gTTS or ElevenLabs.")
                elif payload.get("audio_url"):
                    st.audio(f"{API_BASE}{payload['audio_url']}")
                    st.caption("Audio uses ElevenLabs in production and an audible gTTS fallback in local demo mode.")
                if payload.get("mandi_price"):
                    st.json(payload["mandi_price"])
            except Exception as exc:
                st.error(f"Could not get advisory: {exc}")

with right:
    st.subheader("Mandi Price Engine")
    st.caption("Agmarknet-first lookup with historical CSV AI prediction fallback.")
    try:
        if BACKEND_AVAILABLE:
            coverage = requests.get(f"{API_BASE}/api/india/coverage", timeout=3).json()
        else:
            coverage = {
                "ai_provider": os.getenv("AI_PROVIDER", "mock"),
                "ollama_model": os.getenv("OLLAMA_MODEL", "llama3.1:8b"),
            }
        st.caption(f"AI provider: {coverage['ai_provider']} | Ollama model: {coverage['ollama_model']}")
    except Exception:
        pass
    price_crop = st.selectbox("Price crop", CROPS, index=0, key="price_crop")
    price_market = st.selectbox("Price market", MARKETS, index=MARKETS.index("Lucknow"), key="price_market")
    price_state = st.selectbox("Price state/UT", STATES_AND_UTS, index=STATES_AND_UTS.index("Uttar Pradesh"), key="price_state")
    if st.button("Check Mandi Price", use_container_width=True):
        with st.spinner("Checking live data and fallback model..."):
            try:
                price = post_price(price_crop, price_market, price_state)
                st.metric("Modal Price", f"₹{price['modal_price']}/quintal", price["source"])
                st.write(price["explanation"])
                st.dataframe(price["observations"], use_container_width=True)
            except Exception as exc:
                st.error(f"Could not fetch price: {exc}")

language_options = "\n".join(
    f'<option value="{code}"{" selected" if code == language else ""}>{label}</option>'
    for code, label in LANGUAGES.items()
)

voice_component = f"""
<style>
  .voice-shell {{
    position: fixed; right: 28px; bottom: 26px; z-index: 99999;
  }}
  .voice-panel {{
    width: 340px; border: 1px solid #cfe5d4; background: white; border-radius: 8px;
    box-shadow: 0 16px 44px rgba(31, 70, 49, .18); padding: 12px;
    font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  }}
  .voice-btn {{
    width: 100%; border: 0; border-radius: 8px; background: #1f7a4d; color: white;
    padding: 13px 14px; font-weight: 750; cursor: pointer; font-size: 15px;
  }}
  .voice-btn.recording {{ background: #b42318; }}
  .voice-status {{ color: #42574d; font-size: 13px; min-height: 42px; margin-top: 9px; line-height: 1.35; }}
  .voice-select {{ width: 100%; padding: 8px; margin-bottom: 8px; border: 1px solid #cfe5d4; border-radius: 6px; }}
  .voice-result {{ max-height: 190px; overflow-y: auto; color: #1d2521; font-size: 13px; line-height: 1.45; }}
  @media (max-width: 720px) {{
    .voice-shell {{ right: 12px; left: 12px; bottom: 12px; }}
    .voice-panel {{ width: auto; }}
  }}
</style>
<div class="voice-shell">
  <div class="voice-panel">
    <select id="agri-lang" class="voice-select">
      {language_options}
    </select>
    <button id="agri-voice" class="voice-btn">Voice to Text</button>
    <div id="agri-status" class="voice-status">Tap once to start recording. Tap again to fill the farmer question.</div>
    <div id="agri-result" class="voice-result"></div>
    <audio id="agri-audio" controls style="width:100%; display:none; margin-top:8px;"></audio>
  </div>
</div>
<script>
const wsBase = "{WS_BASE}";
const apiBase = "{API_BASE}";
let recorder = null;
let socket = null;
let recording = false;
const button = document.getElementById("agri-voice");
const statusEl = document.getElementById("agri-status");
const resultEl = document.getElementById("agri-result");
const audioEl = document.getElementById("agri-audio");
const langEl = document.getElementById("agri-lang");

function setStatus(text) {{ statusEl.textContent = text; }}
function appendResult(html) {{ resultEl.innerHTML = html + resultEl.innerHTML; }}

async function startVoice() {{
  resultEl.innerHTML = "";
  audioEl.style.display = "none";
  socket = new WebSocket(`${{wsBase}}/api/voice/ws`);
  socket.binaryType = "arraybuffer";
  socket.onopen = () => {{
    socket.send(JSON.stringify({{type: "config", language: langEl.value, mode: "transcribe_only"}}));
    setStatus("Connected. Speak naturally near the phone mic.");
  }};
  socket.onmessage = (event) => {{
    const data = JSON.parse(event.data);
    if (data.type === "transcript") {{
      appendResult(`<p><b>Transcript:</b> ${{data.transcript || "(waiting for webhook)"}}</p>`);
    }}
    if (data.type === "voice_text_ready") {{
      const nextUrl = new URL(window.parent.location.href);
      nextUrl.searchParams.set("voice_text", data.transcript || "");
      nextUrl.searchParams.set("voice_lang", data.language || langEl.value);
      window.parent.location.href = nextUrl.toString();
    }}
    if (data.type === "pending") {{
      appendResult(`<p>${{data.message}}</p>`);
    }}
    if (data.type === "answer") {{
      appendResult(`<p><b>AgriVani:</b> ${{data.answer_text}}</p>`);
      if (data.audio_url) {{
        audioEl.src = `${{apiBase}}${{data.audio_url}}`;
        audioEl.style.display = "block";
        audioEl.play().catch(() => {{}});
      }}
    }}
  }};
  socket.onerror = () => setStatus("Voice connection failed. Check backend and microphone permissions.");

  const stream = await navigator.mediaDevices.getUserMedia({{
    audio: {{
      channelCount: 1,
      echoCancellation: true,
      noiseSuppression: true,
      sampleRate: 16000
    }}
  }});
  recorder = new MediaRecorder(stream, {{ mimeType: "audio/webm;codecs=opus", audioBitsPerSecond: 24000 }});
  recorder.ondataavailable = async (event) => {{
    if (event.data.size > 0 && socket && socket.readyState === WebSocket.OPEN) {{
      const buffer = await event.data.arrayBuffer();
      socket.send(buffer);
    }}
  }};
  recorder.start(900);
  recording = true;
  button.classList.add("recording");
  button.textContent = "Fill Question";
}}

function stopVoice() {{
  if (recorder && recorder.state !== "inactive") recorder.stop();
  if (socket && socket.readyState === WebSocket.OPEN) {{
    setTimeout(() => socket.send(JSON.stringify({{type: "stop"}})), 350);
  }}
  recording = false;
  button.classList.remove("recording");
  button.textContent = "Voice to Text";
  setStatus("Transcribing speech to farmer question...");
}}

button.addEventListener("click", async () => {{
  try {{
    if (!recording) await startVoice();
    else stopVoice();
  }} catch (err) {{
    setStatus(`Microphone error: ${{err.message}}`);
  }}
}});
</script>
"""
