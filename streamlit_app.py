from __future__ import annotations

import csv
import hashlib
from pathlib import Path

import streamlit as st
from gtts import gTTS


BASE_DIR = Path(__file__).resolve().parent
DATA_PATH = BASE_DIR / "data" / "historical_mandi_prices.csv"
AUDIO_DIR = BASE_DIR / "backend" / "static" / "audio"
AUDIO_DIR.mkdir(parents=True, exist_ok=True)

LANGUAGES = {
    "hi": "Hindi",
    "en": "English",
    "mr": "Marathi",
    "bn": "Bengali",
    "gu": "Gujarati",
    "kn": "Kannada",
    "ml": "Malayalam",
    "pa": "Punjabi",
    "ta": "Tamil",
    "te": "Telugu",
    "ur": "Urdu",
}

STATES_AND_UTS = [
    "India",
    "Maharashtra",
    "Uttar Pradesh",
    "West Bengal",
    "Karnataka",
    "Gujarat",
    "Rajasthan",
    "Punjab",
    "Tamil Nadu",
    "Telangana",
    "Andhra Pradesh",
    "Kerala",
    "Assam",
    "Bihar",
    "Madhya Pradesh",
    "Delhi",
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
    "Kolkata",
    "Bengaluru",
    "Rajkot",
    "Jaipur",
    "Ludhiana",
    "Chennai",
    "Hyderabad",
    "Guntur",
    "Kochi",
    "Guwahati",
    "Patna",
    "Indore",
    "Nashik",
    "Lasalgaon",
    "Nagpur",
    "Delhi",
]


def load_rows() -> list[dict]:
    rows: list[dict] = []
    with DATA_PATH.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            for key in ["min_price", "modal_price", "max_price"]:
                row[key] = float(row[key])
            rows.append(row)
    return rows


def predict_price(crop: str, market: str, state: str) -> dict:
    rows = load_rows()

    def row_matches(row: dict, exact_market: bool) -> bool:
        crop_ok = row["crop"].lower() == crop.lower()
        state_ok = state == "India" or row["state"].lower() == state.lower()
        market_ok = row["market"].lower() == market.lower() if exact_market else True
        return crop_ok and state_ok and market_ok

    sample = [row for row in rows if row_matches(row, True)]
    confidence = 0.79
    if len(sample) < 3:
        sample = [row for row in rows if row_matches(row, False)]
        confidence = 0.64
    if len(sample) < 3:
        sample = [row for row in rows if row["crop"].lower() == crop.lower()]
        confidence = 0.52
    if len(sample) < 3:
        sample = rows
        confidence = 0.4

    sample = sorted(sample, key=lambda row: row["date"])[-8:]
    weights = list(range(1, len(sample) + 1))
    total = sum(weights)

    def weighted(column: str) -> float:
        return round(sum(row[column] * weight for row, weight in zip(sample, weights)) / total, 2)

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
            "Agmarknet live scraping is disabled on Streamlit Cloud. "
            "This is an AI-assisted prediction from recent historical mandi rows."
        ),
        "observations": sample,
    }


def advisory_text(language: str, price: dict) -> str:
    if language == "en":
        return (
            f"Quick advisory: The expected modal price for {price['crop']} in "
            f"{price['market']} is INR {price['modal_price']}/quintal. Check arrivals, "
            "compare transport cost, and avoid distress selling when prices are volatile."
        )
    if language == "mr":
        return (
            f"जलद सल्ला: {price['market']} मध्ये {price['crop']} चा अंदाजे मॉडल भाव "
            f"{price['modal_price']} रुपये/क्विंटल आहे. स्थानिक आवक तपासा आणि विक्री टप्प्याटप्प्याने करा."
        )
    return (
        f"त्वरित सलाह: {price['market']} में {price['crop']} का अनुमानित मॉडल भाव "
        f"{price['modal_price']} रुपये/क्विंटल है. स्थानीय आवक देखें, जल्दबाज़ी में बिक्री न करें, "
        "और भाव बदलने पर किस्तों में बेचें."
    )


def make_audio(text: str, language: str) -> str | None:
    gtts_language = {
        "bn": "bn",
        "en": "en",
        "gu": "gu",
        "hi": "hi",
        "kn": "kn",
        "ml": "ml",
        "mr": "mr",
        "pa": "pa",
        "ta": "ta",
        "te": "te",
        "ur": "ur",
    }.get(language, "hi")
    digest = hashlib.sha256(f"{language}:{text}".encode("utf-8")).hexdigest()[:18]
    path = AUDIO_DIR / f"{digest}.mp3"
    if not path.exists():
        try:
            gTTS(text=text[:1400], lang=gtts_language, slow=False).save(str(path))
        except Exception:
            return None
    return str(path)


st.set_page_config(page_title="AgriVani", page_icon="🌾", layout="wide")

st.markdown(
    """
    <style>
    .block-container { max-width: 1160px; padding-top: 1.5rem; }
    .hero { border-bottom: 1px solid #d8e8dd; padding-bottom: 16px; margin-bottom: 16px; }
    .hero h1 { margin: 0; font-size: 42px; color: #1d2521; }
    .hero p { color: #466055; font-size: 16px; margin-top: 8px; }
    .metric-grid { display:grid; grid-template-columns:repeat(3,1fr); gap:12px; margin:16px 0 24px; }
    .metric-card { border:1px solid #d8e8dd; border-radius:8px; padding:16px; background:#fbfdfb; }
    .metric-card b { display:block; color:#1f7a4d; font-size:26px; margin-bottom:6px; }
    .metric-card span { color:#50635a; font-size:13px; }
    @media (max-width: 720px) { .metric-grid { grid-template-columns: 1fr; } }
    </style>
    <div class="hero">
      <h1>AgriVani</h1>
      <p>Real-time multilingual agri advisory for Indian farmers, optimized for low-bandwidth rural networks.</p>
    </div>
    <div class="metric-grid">
      <div class="metric-card"><b>40%</b><span>Target reduction in advisory and market-discovery cost</span></div>
      <div class="metric-card"><b>&lt; 60 KB</b><span>Low-bandwidth, voice-first rural workflow</span></div>
      <div class="metric-card"><b>Pan-India</b><span>States, UTs, mandis, crops, and local AI-ready design</span></div>
    </div>
    """,
    unsafe_allow_html=True,
)

left, right = st.columns([0.56, 0.44], gap="large")

with left:
    st.subheader("Ask AgriVani")
    language = st.selectbox("Language", list(LANGUAGES), format_func=lambda code: LANGUAGES[code])
    question = st.text_area("Farmer question", "लखनऊ में प्याज का मंडी भाव बताइए", height=120)
    c1, c2, c3 = st.columns(3)
    crop = c1.selectbox("Crop", CROPS, index=0)
    market = c2.selectbox("Market", MARKETS, index=MARKETS.index("Lucknow"))
    state = c3.selectbox("State/UT", STATES_AND_UTS, index=STATES_AND_UTS.index("Uttar Pradesh"))

    if st.button("Get Advisory", type="primary", use_container_width=True):
        price = predict_price(crop, market, state)
        answer = advisory_text(language, price)
        st.success(answer)
        audio_path = make_audio(answer, language)
        if audio_path:
            st.audio(audio_path)
        st.json(price)

with right:
    st.subheader("Mandi Price Engine")
    st.caption("Streamlit Cloud mode: historical CSV prediction fallback.")
    pcrop = st.selectbox("Price crop", CROPS, index=0, key="pcrop")
    pmarket = st.selectbox("Price market", MARKETS, index=MARKETS.index("Lucknow"), key="pmarket")
    pstate = st.selectbox("Price state/UT", STATES_AND_UTS, index=STATES_AND_UTS.index("Uttar Pradesh"), key="pstate")

    if st.button("Check Mandi Price", use_container_width=True):
        price = predict_price(pcrop, pmarket, pstate)
        st.metric("Modal Price", f"₹{price['modal_price']}/quintal", price["source"])
        st.write(price["explanation"])
        st.dataframe(price["observations"], use_container_width=True)

st.caption("Cloud demo uses free historical CSV fallback and gTTS audio. Local repo still contains FastAPI, Deepgram, Gemini/Ollama, and ElevenLabs integrations.")
