#!/usr/bin/env bash
# After queue7: paper B's second-writer test sets (no human participants). Qwen3.5-4B and Gemma 4 E2B each write a set from the memory
# descriptions; every recall method (and the zero-shot Gemma E4B on 8080) is scored on each, with cut-offs still from the original dev half.
cd "$(dirname "$0")/../.."
PY=server/patient-service/.venv/bin/python
S=tests/overnight/papers/status.md
L=tests/overnight/papers
until grep -q "rater sheets written" "$S" 2>/dev/null; do sleep 60; done
curl -sf localhost:8080/health >/dev/null || tools/llm_eval/serve.sh models/gemma-4-E4B-it-Q4_K_M.gguf 8080
for w in qwen4b:models/Qwen3.5-4B-Q4_K_M.gguf gemma2b:models/gemma-4-E2B-it-Q4_K_M.gguf; do
  name=${w%%:*}; set=tests/recall/writer_$name.jsonl
  if [ ! -s "$set" ]; then
    tools/llm_eval/serve.sh "${w#*:}" 8082
    echo "- $(date '+%F %T') start writer_$name" >> "$S"
    $PY tools/recall_writer.py "$set" --url http://127.0.0.1:8082/v1 > $L/writer_$name.log 2>&1
    echo "- $(date '+%F %T') end writer_$name rc=$?" >> "$S"
    pkill -f "llama-server.*--port 8082"; sleep 3
  fi
  [ -s "$set" ] || continue
  RECALL_TEST_SET=$set $PY tools/recall_baselines.py cpu > $L/recall_cpu_$name.log 2>&1; echo "- $(date '+%F %T') recall_cpu_$name rc=$?" >> "$S"
  RECALL_TEST_SET=$set $PY tools/recall_baselines.py llm > $L/recall_llm_$name.log 2>&1; echo "- $(date '+%F %T') recall_llm_$name rc=$?" >> "$S"
  $PY tools/human/packets.py labels "$set" >> $L/flags_packet.log 2>&1
done
$PY papers/analysis/new_results.py > $L/paper_numbers_final.log 2>&1
for d in papers/paperA_jms papers/paper; do (cd $d && for f in *.tex; do tectonic -X compile "$f" >> ../../tests/overnight/papers/build.log 2>&1; done); done
echo "- $(date '+%F %T') second-writer sets done, papers rebuilt" >> "$S"
