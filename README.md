# AgriVani

Production-ready FastAPI + Streamlit prototype for a multilingual, voice-first AgriTech advisory platform.

## Quick Start

```bash
./setup.sh
.venv/bin/python start.py
```

Open `http://127.0.0.1:8501`.

## Deploy To Streamlit Community Cloud

Streamlit Community Cloud runs a single Streamlit process, so the root [streamlit_app.py](/Users/saurabhkumarbajpaiai/Documents/Codex/2026-05-14/act-as-a-senior-ai-architect/streamlit_app.py) entrypoint automatically falls back to in-process services when the local FastAPI backend is not available.

1. Push this folder to a GitHub repository.
2. In Streamlit Community Cloud, choose **New app**.
3. Select the repository and branch.
4. Set **Main file path** to `streamlit_app.py`.
5. Add secrets from `.streamlit/secrets.toml.example`.
6. Deploy.

Cloud behavior:

- Mandi price prediction runs in-process from `data/historical_mandi_prices.csv`.
- Advisory uses Ollama only if reachable from the cloud runtime, otherwise Gemini if `GEMINI_API_KEY` is set, otherwise demo fallback.
- Audio uses ElevenLabs if configured, otherwise gTTS fallback.
- Voice-to-text uses browser speech recognition on Streamlit Cloud; local FastAPI still supports the Deepgram WebSocket path.

## Environment

Copy `.env.example` to `.env` and fill:

- `GEMINI_API_KEY`
- `DEEPGRAM_API_KEY`
- `ELEVENLABS_API_KEY`
- `PUBLIC_BASE_URL` for Deepgram webhooks in production
- `AI_PROVIDER=auto`, `ollama`, or `gemini`
- `OLLAMA_BASE_URL=http://127.0.0.1:11434`
- `OLLAMA_MODEL=llama3.1:8b`

Blank keys are allowed for local demo mode.

## Ollama Local AI

AgriVani supports Ollama as a local/offline reasoning provider. With `AI_PROVIDER=auto`, the backend tries Ollama first, then Gemini, then a deterministic demo fallback.

```bash
ollama pull llama3.1:8b
ollama serve
```

Then run:

```bash
AI_PROVIDER=ollama python start.py
```

If `python` is not available on your shell, use:

```bash
.venv/bin/python start.py
```

## Pan-India Coverage

The app includes structured selectors for Indian states/UTs, major mandis, and common crops. The fallback CSV includes representative historical observations across north, south, east, west, central, and northeast India.

## Project Tree

```text
.
├── backend/
│   └── app/
│       ├── main.py
│       ├── config.py
│       ├── models.py
│       └── services/
│           ├── deepgram_service.py
│           ├── gemini_agent.py
│           ├── mandi_price_engine.py
│           └── tts_service.py
├── data/
│   └── historical_mandi_prices.csv
├── frontend/
│   └── streamlit_app.py
├── JUDGES_README.md
├── README.md
├── requirements.txt
├── setup.sh
└── start.py
```

## API Highlights

- `POST /api/agent/ask`: Text query to Gemini agent with mandi context.
- `POST /api/mandi/price`: Agmarknet-first price lookup with historical CSV fallback.
- `WS /api/voice/ws`: Browser audio chunks to Deepgram, Gemini, and ElevenLabs.
- `POST /webhooks/deepgram`: Deepgram callback endpoint.
- `GET /api/india/coverage`: States/UTs, major mandis, crops, and AI provider metadata.
