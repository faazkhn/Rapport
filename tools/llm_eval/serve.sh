#!/usr/bin/env bash
# Serve one bake-off GGUF on a port with the same flags as server/patient-service/run.sh. Usage: serve.sh <gguf> [port]
GGUF="$1"; PORT="${2:-8080}"
pkill -f "llama-server.*--port $PORT" ; sleep 1
TPL=(); case "$GGUF" in *gemma-4*) TPL=(--chat-template-file "$(dirname "$0")/../../server/patient-service/gemma4-nothink.jinja");; esac
llama-server -m "$GGUF" ${TPL[@]+"${TPL[@]}"} --host 127.0.0.1 --port "$PORT" -np 2 -c 16384 -ngl 99 -fa on --reasoning-budget 0 --no-webui --log-disable >/dev/null 2>&1 &
for i in $(seq 120); do curl -sf "localhost:$PORT/health" >/dev/null && exit 0; sleep 1; done; exit 1
