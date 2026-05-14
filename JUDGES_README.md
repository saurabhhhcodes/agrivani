# AgriVani: Real-Time Multilingual AgriTech Platform

AgriVani is a voice-first advisory platform for Indian farmers. It combines Gemini 3 Flash or local Ollama agentic reasoning, Deepgram speech recognition, ElevenLabs multilingual speech output, and a resilient mandi price engine that keeps working when live government sources fail.

## Why It Matters

**Impact: 40% cost reduction.** Farmers usually spend money and time calling middlemen, traveling to mandis, or waiting for local updates. AgriVani compresses advisory, price discovery, and voice support into one phone-first workflow, targeting a 40% reduction in advisory and market-discovery costs.

**Practicality: rural-first architecture.** The UI records low-bitrate Opus audio in short chunks and streams it over WebSockets. This performs better on unstable 3G/4G links than heavy video calls or full-page reload apps. The backend also degrades gracefully with Ollama, mocks for demos, and historical CSV prediction when Agmarknet is unavailable.

## Killer Feature: MandiPriceEngine

`MandiPriceEngine` follows production fallback logic:

1. Try Agmarknet live scraping for the requested crop, market, and state.
2. If Agmarknet fails, times out, or returns no row, load `data/historical_mandi_prices.csv`.
3. Use recent weighted observations and trend adjustment to produce an AI-assisted min, modal, and max price.
4. Return source and confidence so farmers know whether the number is live or predicted.

## Architecture

```text
Streamlit browser UI
  ├─ Text advisory form
  └─ Floating voice-first recorder
        ↓ WebSocket audio chunks
FastAPI backend
  ├─ /api/voice/ws
  ├─ /webhooks/deepgram
  ├─ Deepgram STT
  ├─ Ollama local agent or Gemini 3 Flash agent
  ├─ MandiPriceEngine
  └─ ElevenLabs TTS
        ↓
Text + MP3 response back to farmer
```

## Running Locally

```bash
./setup.sh
cp .env.example .env
# Add real API keys to .env
python start.py
```

Frontend: `http://127.0.0.1:8501`

Backend docs: `http://127.0.0.1:8000/docs`

## Demo Without Paid Keys

Set `USE_MOCK_AI=true` or leave API keys blank. The application still runs end-to-end with a mock transcript, local/deterministic advisory, audible gTTS MP3 fallback, and real MandiPriceEngine fallback prediction.

## Ollama Mode

For offline or low-connectivity deployments, run a local model:

```bash
ollama pull llama3.1:8b
ollama serve
AI_PROVIDER=ollama .venv/bin/python start.py
```

With `AI_PROVIDER=auto`, AgriVani tries Ollama first, then Gemini, then demo fallback.

## Pan-India Scope

AgriVani exposes structured state/UT, mandi, crop, and language selectors. The sample fallback CSV includes representative data across Uttar Pradesh, West Bengal, Bihar, Gujarat, Rajasthan, Punjab, Karnataka, Telangana, Andhra Pradesh, Tamil Nadu, Kerala, Assam, Maharashtra, Madhya Pradesh, Delhi, and more.

## Production Notes

- Use a public HTTPS URL in `PUBLIC_BASE_URL` for Deepgram webhook callbacks.
- Use `DEEPGRAM_CALLBACK_SECRET` to prevent forged webhook calls.
- Put FastAPI behind a reverse proxy with TLS.
- Run backend and frontend as separate services in production rather than `start.py`.
- Replace in-memory webhook storage with Redis or Postgres for multi-worker deployments.
- Schedule a daily Agmarknet ingestion job to grow the historical CSV or database table.

## Low-Bandwidth Optimizations

- Browser records mono Opus audio at 24 kbps.
- WebSocket chunks are sent every 900 ms.
- Text responses are short and voice-first.
- Price fallback avoids repeated live scraping when government pages are slow.
- Streamlit UI keeps the first screen operational with minimal assets.
