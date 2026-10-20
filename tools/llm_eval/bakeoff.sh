#!/usr/bin/env bash
# Full bake-off: serve each candidate on :8080 and run the eval set (5 runs). Results in tests/llm-eval/results/<label>.jsonl
cd "$(dirname "$0")/../.."
PY=server/patient-service/.venv/bin/python
for m in ${MODELS:-gemma-4-E2B-it gemma-4-E4B-it Qwen3.5-4B Qwen3.5-9B}; do
  echo "== $m"
  tools/llm_eval/serve.sh "models/$m-Q4_K_M.gguf" 8080 || { echo "serve failed $m"; continue; }
  $PY tools/llm_eval/run_eval.py --label "$m" --runs "${RUNS:-5}" 2>&1 | grep -v "^HTTP"
done
pkill -f "llama-server.*--port 8080"
echo BAKEOFF DONE
