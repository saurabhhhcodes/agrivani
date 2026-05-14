#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

echo "Creating virtual environment..."
python3 -m venv .venv

echo "Installing Python dependencies..."
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -r requirements-backend.txt

if [ ! -f .env ]; then
  echo "Creating .env from .env.example..."
  cp .env.example .env
fi

echo ""
echo "Setup complete."
echo "Edit .env with Gemini, Deepgram, and ElevenLabs keys, then run:"
echo "  python start.py"
