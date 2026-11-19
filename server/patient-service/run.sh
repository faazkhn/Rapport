#!/usr/bin/env bash
# Start everything for the Rapport voice loop: llama-server (local patient LLM) on :8080, then the patient service on :8765 (the network sees only the Twin view).
#   ./run.sh            local LLM (default; nothing leaves the Mac)
#   ./run.sh --mock     keyword mock LLM, no model
#   PATIENT_LLM=grok ./run.sh   Grok via xAI, only if XAI_API_KEY is set (environment or repo .env); no llama-server
# LLM_GGUF overrides the model file (default: the bake-off winner, see models/README.md).
set -euo pipefail
cd "$(dirname "$0")"
REPO="$(cd ../.. && pwd)"
LLM_GGUF="${LLM_GGUF:-$REPO/models/gemma-4-E4B-it-Q4_K_M.gguf}"
LLAMA_PORT="${LLAMA_PORT:-8080}"

RAPPORT_LLM="${RAPPORT_LLM:-${PSYCHSIM_LLM:-}}"  # PSYCHSIM_* is the deprecated alias, until v0.3
if [ "${1:-}" = "--mock" ]; then RAPPORT_LLM=mock; shift; fi
export RAPPORT_LLM
if [ "$RAPPORT_LLM" != "mock" ] && [ "${PATIENT_LLM:-local}" != "grok" ]; then
  if ! curl -sf "http://127.0.0.1:$LLAMA_PORT/health" >/dev/null; then
    [ -f "$LLM_GGUF" ] || { echo "missing $LLM_GGUF (see models/README.md)"; exit 1; }
    # Gemma 4: a template without the thinking channel, so the JSON grammar applies from the first token (see gemma4-nothink.jinja)
    TPL=(); case "$LLM_GGUF" in *gemma-4*) TPL=(--chat-template-file "$PWD/gemma4-nothink.jinja");; esac
    # -np 2: slot 0 = patient voice, slot 1 = intent tagging. Thinking off. Logs hold no conversation text.
    llama-server -m "$LLM_GGUF" ${TPL[@]+"${TPL[@]}"} --host 127.0.0.1 --port "$LLAMA_PORT" -np 2 -c 16384 -ngl 99 -fa on \
      --reasoning-budget 0 --no-webui --log-disable &
    LLAMA_PID=$!
    trap 'kill $LLAMA_PID 2>/dev/null' EXIT
    until curl -sf "http://127.0.0.1:$LLAMA_PORT/health" >/dev/null; do sleep 0.5; kill -0 $LLAMA_PID || exit 1; done
  fi
  export LLAMA_URL="http://127.0.0.1:$LLAMA_PORT/v1"
fi
# every interface, so a second laptop on the same Wi-Fi can open the Twin view; app.LocalOnly keeps the rest on this Mac.
# RAPPORT_HOST=127.0.0.1 keeps it off the network.
PORT="${PORT:-8765}"
LAN_IP="$(ipconfig getifaddr en0 || ipconfig getifaddr en1 || true)"
echo "Digital Twin: http://127.0.0.1:$PORT/twin/${LAN_IP:+   on this Wi-Fi: http://$LAN_IP:$PORT/twin/}"
.venv/bin/uvicorn app:app --host "${RAPPORT_HOST:-0.0.0.0}" --port "$PORT" "$@"
