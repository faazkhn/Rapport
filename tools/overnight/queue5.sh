#!/usr/bin/env bash
# Papers A and B (2026-11-18): the compute-only additions, most important first. Patient Gemma on 8080, judge Qwen3.5-9B on 8081.
# A failed step is logged in tests/overnight/papers/status.md and the queue goes on; rerunning skips finished pieces where it can.
#   nohup caffeinate -dims bash tools/overnight/queue5.sh > tests/overnight/papers/queue.log 2>&1 &
set -u
cd "$(dirname "$0")/../.."
PY=server/patient-service/.venv/bin/python
OUT=tests/overnight/papers
RES=tests/llm-eval/results/learning
JUDGE=http://127.0.0.1:8081/v1
mkdir -p "$OUT"
S="$OUT/status.md"
echo "# Papers queue $(date '+%F %T')" >> "$S"

step() {  # step <name> <command...>
  local name=$1; shift
  echo "- $(date '+%F %T') start $name" >> "$S"
  ( "$@" ) > "$OUT/$name.log" 2>&1
  echo "- $(date '+%F %T') end $name rc=$?" >> "$S"
}
up() { curl -sf "http://127.0.0.1:$1/health" >/dev/null; }
servers() {
  up 8080 || tools/llm_eval/serve.sh models/gemma-4-E4B-it-Q4_K_M.gguf 8080
  up 8081 || tools/llm_eval/serve.sh models/Qwen3.5-9B-Q4_K_M.gguf 8081
}
heldout() {  # heldout <vid> <case> <seeds>: only the seeds without a saved run
  local todo=()
  for s in ${3//,/ }; do [ -s "$RES/$1.$2.s$s.jsonl" ] || todo+=("$s"); done
  [ ${#todo[@]} -eq 0 ] && return 0
  servers
  step "heldout_${1}_${2}" "$PY" tools/learning/loop.py heldout "$1" --case "$2" --seeds "$(IFS=,; echo "${todo[*]}")" --judge-url "$JUDGE"
}

# 1. prompt-only baseline (must-add A1), same 14 scripts and three seeds, then the three extra alcohol seeds
heldout p0 mdd_01 11,23,42
heldout p0 alc_01 11,23,42,5,7,13

# 2. missed risk inside conversations (must-add A2): v2, v0 and the baseline
for v in v2 v0 p0; do servers; step "riskprobe_$v" "$PY" tools/learning/risk_probe.py run "$v" --seeds 11,23,42 --judge-url "$JUDGE"; done
step riskprobe_report "$PY" tools/learning/risk_probe.py report

# 3. the same words-based disclosure judge on the Twin's saved held-out runs, so every arm is scored alike
servers
step disclosure_saved "$PY" tools/learning/judge_disclosure.py $RES/v2.mdd_01.s{11,23,42}.jsonl $RES/v2.alc_01.s{11,23,42}.jsonl \
  $RES/v0.mdd_01.s{11,23,42}.jsonl $RES/v0.alc_01.s{11,23,42}.jsonl --judge-url "$JUDGE"

# 4. more alcohol runs (should-add): three more seeds for v2 and v0
heldout v2 alc_01 5,7,13
heldout v0 alc_01 5,7,13

# 5. paper B: the CPU baselines and the zero-shot LLM classifier (fast; rerun so the files match tonight's code)
step recall_baselines_cpu "$PY" tools/recall_baselines.py cpu
[ -s tests/overnight/recall_llm_lines.jsonl ] || { servers; step recall_baselines_llm "$PY" tools/recall_baselines.py llm; }

# 6. tables for both papers from everything above
step paper_numbers "$PY" papers/analysis/new_results.py
echo "- $(date '+%F %T') papers queue finished" >> "$S"
