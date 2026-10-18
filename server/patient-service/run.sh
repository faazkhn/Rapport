#!/usr/bin/env bash
# Start the PsychSim patient service on 127.0.0.1:8765. XAI_API_KEY comes from the environment or the repo's .env.
set -euo pipefail
cd "$(dirname "$0")"
exec .venv/bin/uvicorn app:app --host 127.0.0.1 --port "${PORT:-8765}" "$@"
