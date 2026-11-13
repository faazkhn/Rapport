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
waitjob() {  # waitjob <task output> <process pattern>: until the job printed done, or its process is gone
  until grep -q '^done' "$1" 2>/dev/null; do
    if ! pgrep -f "$2" >/dev/null; then sleep 60; pgrep -f "$2" >/dev/null || break; fi  # gone twice in a row (not between phases)
    sleep 60
  done
}
waitjob "$TASKS/bpka7h508.output" "loop.py heldout v0"
waitjob "$TASKS/bnxuhk3tj.output" "gen_lines.py"
echo "- $(date '+%F %T') earlier jobs finished" >> "$STATUS"
eval_servers
if ! ls "$REPO/../v03-baseline/tests/llm-eval/results/learning/v0.alc_01.s42.jsonl" >/dev/null 2>&1; then
  for c in mdd_01 alc_01; do
    step "baseline_redo_$c" bash -c "cd '$REPO/../v03-baseline' && '$PY' tools/learning/loop.py heldout v0 --case $c --seeds 11,23,42 --judge-url $JUDGE"
  done
  cp "$REPO/../v03-baseline/tests/llm-eval/results/learning/"v0.*.jsonl "$RES/" 2>/dev/null
fi
for c in mdd_01 alc_01 ward_01 ward_02; do
  [ -f "unity/PsychSim/Assets/StreamingAssets/data/recall/$c.json" ] || step "gen_probes_$c" "$PY" tools/brain/gen_lines.py probes --case "$c"
done
[ -s tests/brain/gen_moves.jsonl ] || step gen_moves "$PY" tools/brain/gen_lines.py moves
mkdir -p "$RES/baseline" && mv "$RES"/v0.mdd_01.s*.jsonl "$RES"/v0.alc_01.s*.jsonl "$RES/baseline/" 2>/dev/null
cp "$REPO/../v03-baseline/server/patient-service/learned/versions/v0.json" "$RES/baseline/v0-version.json" 2>/dev/null

# ---- 1. recall on the held-out paraphrase half (CPU) ----
step recall_tune "$PY" tools/brain/tune_recall.py
step recall_test "$PY" tools/recall_bench.py --split test --misses --json "$OUT/recall_test.json"
step recall_test_lexical "$PY" tools/recall_bench.py --split test --lexical --json "$OUT/recall_test_lexical.json"
step recall_dev "$PY" tools/recall_bench.py --split dev --json "$OUT/recall_dev.json"

# ---- 2. the new brain (v2) and v0 under the same harness, held out, three seeds, both cases ----
eval_servers
for v in v2 v0; do
  for c in mdd_01 alc_01; do
    eval_servers
    step "heldout_${v}_${c}" "$PY" tools/learning/loop.py heldout "$v" --case "$c" --seeds 11,23,42 --judge-url "$JUDGE"
  done
done

# ---- 3. latency, v0 then v2 (live brain switched only for the measurement) ----
live v0 && step latency_v0 latency v0
live v2 && step latency_v2 latency v2
live v0

# ---- 4. baseline stills of all four bodies (Unity batch; before any rendering change) ----
step stills_baseline /Applications/Unity/Hub/Editor/6000.6.2f1/Unity.app/Contents/MacOS/Unity -batchmode -projectPath unity/PsychSim \
  -executeMethod Rapport.Editor.LightingStills.CaptureAllBodiesBatch -stillsDir "$REPO/docs/media/v0.3/baseline" -logFile "$OUT/stills_unity.log"
for f in docs/media/v0.3/baseline/*.png; do step "luminance_$(basename "$f" .png)" "$PY" tools/lighting/face_luminance.py "$f"; done

# ---- 5. move and intent classifier: label (judge), gold, train, compare with the lexical rubric and the LLM tagger ----
eval_servers
step moves_label "$PY" tools/brain/moves_model.py label --url "$JUDGE"
step moves_gold "$PY" tools/brain/moves_model.py gold --url "$JUDGE"
step moves_train "$PY" tools/brain/moves_model.py train --id moves-v1
step moves_eval "$PY" tools/brain/moves_model.py eval --id moves-v1
# v3 = v2 + the classifier, only if it reads moves better than the lexical patterns on the gold set
step make_v3 "$PY" - <<'PYEOF'
import json, sys, time
sys.path.insert(0, "server/patient-service")
import learning
e = json.load(open("tests/brain/eval_moves-v1.json"))
c, l = e["moves_classifier"]["micro_f1"], e["moves_lexical"]["micro_f1"]
print("classifier", c, "lexical", l)
if c > l:
    v = learning.load_version("v2")
    learning.save_version({**{k: x for k, x in v.items() if k not in ("scores", "scores_by_run", "decision", "status")}, "id": "v3", "parent": "v2",
                           "status": "candidate", "created": time.strftime("%Y-%m-%d %H:%M"), "features": v["features"] + ["move_model"],
                           "move_model": "moves-v1", "scores": {}, "notes": f"v2 + move classifier moves-v1 (gold micro F1 {c} vs lexical {l})"})
    print("made v3")
PYEOF
if [ -f server/patient-service/learned/versions/v3.json ]; then
  for c in mdd_01 alc_01; do
    eval_servers
    step "heldout_v3_${c}" "$PY" tools/learning/loop.py heldout v3 --case "$c" --seeds 11,23,42 --judge-url "$JUDGE"
  done
fi

# ---- 6. model bake-off on the new brain: Qwen3.5-4B and -9B as the patient (judged by Gemma, a different model), latency each ----
for m in 4 9; do
  GG=$QWEN4; [ $m = 9 ] && GG=$QWEN9
  "$PY" - "$m" <<'PYEOF'
import sys
sys.path.insert(0, "server/patient-service")
import learning
v = learning.load_version("v2")
learning.save_version({**{k: x for k, x in v.items() if k not in ("scores", "scores_by_run", "decision")}, "id": f"v2q{sys.argv[1]}", "parent": "v2",
                       "status": "bakeoff", "scores": {}, "notes": f"v2 spoken by Qwen3.5-{sys.argv[1]}B (model bake-off)"})
PYEOF
  stop_port 8080; stop_port 8081
  serve "$GG" 8080; serve "$GEMMA" 8081
  step "bakeoff_q${m}_heldout" "$PY" tools/learning/loop.py heldout "v2q$m" --seeds 11 --judge-url "$JUDGE"
  live v2 && step "bakeoff_q${m}_latency" latency "q$m" "$GG" 2
  live v0
  stop_port 8080; stop_port 8081
done
eval_servers

# ---- 7. learning: five rounds on the new brain with the separate judge; promotion needs a three-seed win and every safety gate ----
BASE=v2; [ -f server/patient-service/learned/versions/v3.json ] && BASE=v3
live "$BASE"
for r in 1 2 3 4 5; do
  eval_servers
  step "learning_round_$r" "$PY" tools/learning/loop.py round --judge-url "$JUDGE"
done
step learning_report "$PY" tools/learning/loop.py report
live v0  # v0 stays live until the judge flags are reviewed by hand and the gates are read

echo "- $(date '+%F %T') queue finished" >> "$STATUS"
