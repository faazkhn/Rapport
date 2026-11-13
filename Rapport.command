#!/usr/bin/env bash
# Double-click to play: starts the local patient service (llama-server + STT + TTS) if it is not already up, opens the Rapport app,
# and stops the service when the app quits. Service log: ~/Library/Logs/Rapport/service.log (timings only, no conversation text).
set -euo pipefail
cd "$(dirname "$0")"
APP="unity/PsychSim/Builds/Rapport.app"
LOG="$HOME/Library/Logs/Rapport"; mkdir -p "$LOG"
[ -d "$APP" ] || { echo "No build at $APP. Build it in Unity (File > Build Profiles > macOS, Development Build)."; exit 1; }

if ! curl -sf http://127.0.0.1:8765/health >/dev/null; then
  echo "Starting the patient service (first start loads the models, ~20 s)..."
  server/patient-service/run.sh >"$LOG/service.log" 2>&1 &
  SVC=$!
  trap 'pkill -P $SVC 2>/dev/null; kill $SVC 2>/dev/null' EXIT
  until curl -sf http://127.0.0.1:8765/health >/dev/null; do
    kill -0 $SVC 2>/dev/null || { echo "The service failed to start; see $LOG/service.log"; tail -5 "$LOG/service.log"; exit 1; }
    sleep 0.5
  done
fi
LAN_IP="$(ipconfig getifaddr en0 || ipconfig getifaddr en1 || true)"
echo "Service ready. Digital Twin: http://127.0.0.1:8765/twin/${LAN_IP:+  (other laptops on this Wi-Fi: http://$LAN_IP:8765/twin/)}"
open "http://127.0.0.1:8765/twin/"
echo "Opening Rapport."
open -W "$APP"
