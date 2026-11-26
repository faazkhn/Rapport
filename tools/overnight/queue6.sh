#!/usr/bin/env bash
# After queue5: re-time the zero-shot LLM classifier with nothing else on the GPU (the first timing overlapped queue5), then rebuild
# the paper tables and both papers.
cd "$(dirname "$0")/../.."
PY=server/patient-service/.venv/bin/python
S=tests/overnight/papers/status.md
until grep -q "papers queue finished" "$S" 2>/dev/null; do sleep 60; done
pkill -f "llama-server.*--port 8081"; sleep 3   # judge off: the GPU holds only the patient model, as in a live session
echo "- $(date '+%F %T') start recall_llm_idle" >> "$S"
$PY tools/recall_baselines.py llm > tests/overnight/papers/recall_llm_idle.log 2>&1
echo "- $(date '+%F %T') end recall_llm_idle rc=$?" >> "$S"
$PY papers/analysis/new_results.py > tests/overnight/papers/paper_numbers_final.log 2>&1
for d in papers/paperA_jms papers/paper; do (cd $d && for f in *.tex; do tectonic -X compile "$f" >> ../../tests/overnight/papers/build.log 2>&1; done); done
echo "- $(date '+%F %T') follow-up finished (tables and papers rebuilt)" >> "$S"
