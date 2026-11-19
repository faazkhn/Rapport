#!/usr/bin/env bash
# Stop the re-run queue once its latency step is done, before the learning rounds start on a brain that is about to change;
# then bring back the patient (8080) and the judge (8081) for the relabelling and later runs.
cd "$(dirname "$0")/../.."
until grep -q "end latency_v2" tests/overnight/rerun/status.md 2>/dev/null; do sleep 20; done
pkill -f "tools/overnight/queue2.sh"; sleep 2; pkill -f "tools/learning/loop.py round"
server/patient-service/.venv/bin/python server/patient-service/learning.py rollback v0 >/dev/null
for i in 1 2 3; do curl -sf http://127.0.0.1:8080/health >/dev/null || tools/llm_eval/serve.sh models/gemma-4-E4B-it-Q4_K_M.gguf 8080; done
for i in 1 2 3; do curl -sf http://127.0.0.1:8081/health >/dev/null || tools/llm_eval/serve.sh models/Qwen3.5-9B-Q4_K_M.gguf 8081; done
echo "- $(date '+%F %T') stopped before the learning rounds (brain still changing); live = v0; servers 8080/8081 up" >> tests/overnight/rerun/status.md
