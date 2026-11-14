#!/usr/bin/env bash
# v0.3 overnight queue: every GPU job one after another, most important first, so nothing shares the GPU while latency is measured.
# A failed step is logged (tests/overnight/status.md) and the queue goes on. Start it detached and awake:
#   nohup caffeinate -dims bash tools/overnight/queue.sh > tests/overnight/queue.log 2>&1 &
# Keep the lid open (macOS sleeps on lid close without an external display, caffeinate cannot stop that).
set -u
cd "$(dirname "$0")/../.."
REPO="$PWD"
PY="$REPO/server/patient-service/.venv/bin/python"
OUT="$REPO/tests/overnight"
RES="$REPO/tests/llm-eval/results/learning"
TASKS=/private/tmp/claude-501/-Users-faazkhn-Documents-Med/9a7164fa-f5f2-4adb-8307-a6d8573fcc67/tasks
GEMMA="$REPO/models/gemma-4-E4B-it-Q4_K_M.gguf"
QWEN9="$REPO/models/Qwen3.5-9B-Q4_K_M.gguf"
QWEN4="$REPO/models/Qwen3.5-4B-Q4_K_M.gguf"
JUDGE=http://127.0.0.1:8081/v1
mkdir -p "$OUT"
STATUS="$OUT/status.md"
echo "# Overnight queue $(date '+%F %T')" >> "$STATUS"
"$PY" server/patient-service/learning.py rollback v0 >/dev/null

step() {  # step <name> <command...>: runs it, logs to tests/overnight/<name>.log, records the exit code; never stops the queue
  local name=$1; shift
  echo "- $(date '+%F %T') start $name" >> "$STATUS"
  ( "$@" ) > "$OUT/$name.log" 2>&1
  local rc=$?
  echo "- $(date '+%F %T') end $name rc=$rc" >> "$STATUS"
  return 0
}

serving() { curl -sf "http://127.0.0.1:$1/health" >/dev/null && pgrep -f "llama-server.*$(basename "$2").*--port $1" >/dev/null; }
serve() {  # serve <gguf> <port>: (re)start that model on that port unless it is already up
  serving "$2" "$1" && return 0
  for i in 1 2 3; do "$REPO/tools/llm_eval/serve.sh" "$1" "$2" && return 0; sleep 20; done
  echo "- $(date '+%F %T') could not serve $(basename "$1") on $2" >> "$STATUS"; return 1
}
stop_port() { pkill -f "llama-server.*--port $1" ; sleep 3; }
eval_servers() { serve "$GEMMA" 8080; serve "$QWEN9" 8081; }  # patient Gemma, judge Qwen 9B (not the patient's model)
live() { "$PY" server/patient-service/learning.py rollback "$1"; }

service_up() {  # the full voice stack (run.sh reuses llama-server on 8080); waits for /health
  stop_service
  (cd server/patient-service && nohup ./run.sh > "$OUT/service_$1.log" 2>&1 &)
  for i in $(seq 120); do curl -sf http://127.0.0.1:8765/health >/dev/null && sleep 20 && return 0; sleep 5; done
  return 1
}
stop_service() { pkill -f "uvicorn app:app" ; sleep 3; }

latency() {  # latency <label> [gguf] [runs]: 26 turns a run through the real WebSocket path, nothing else on the GPU
  stop_port 8081
  serve "${2:-$GEMMA}" 8080
  service_up "$1" && "$PY" tools/latency/ws_bench.py "$OUT/bench_audio" --runs "${3:-2}" --barge 10 --json "$OUT/latency_$1.json"
  local rc=$?
  stop_service
  return $rc
}

# ---- 0. wait for the jobs started before the queue (baseline held-out, probe and move-line generation); if they died, redo them ----
# ---- re-run after the 2026-11-14 morning fixes (recall precision, forced disclosure, volunteered risk, bench race, round scoring) ----
OUT="$REPO/tests/overnight/rerun"; mkdir -p "$OUT"; STATUS="$OUT/status.md"
echo "# Re-run $(date '+%F %T')" >> "$STATUS"
step recall_test "$PY" tools/recall_bench.py --split test --misses --json "$OUT/recall_test.json"
for c in mdd_01 alc_01; do
  eval_servers
  step "heldout_v2_${c}" "$PY" tools/learning/loop.py heldout v2 --case "$c" --seeds 11,23,42 --judge-url "$JUDGE"
done
live v0 && step latency_v0 latency v0
live v2 && step latency_v2 latency v2
live v2
for r in 1 2 3 4 5; do
  eval_servers
  step "learning_round_$r" "$PY" tools/learning/loop.py round --judge-url "$JUDGE"
done
step learning_report "$PY" tools/learning/loop.py report
live v0
echo "- $(date '+%F %T') re-run finished" >> "$STATUS"
