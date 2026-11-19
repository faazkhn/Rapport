#!/usr/bin/env bash
# After the final held-out run: does an upset patient stay upset after 10 turns? v0 and v2, judged by Qwen3.5-9B.
cd "$(dirname "$0")/../.."
PY=server/patient-service/.venv/bin/python
S=tests/overnight/rerun/status.md
until grep -q "final run finished" "$S" 2>/dev/null; do sleep 30; done
for v in v0 v2; do
  $PY server/patient-service/learning.py rollback $v >/dev/null
  $PY tools/llm_eval/run_eval.py --label style-upset-$v --style upset --only 12_long_decay,04_judgmental --runs 1 --no-probe --timeout 300 \
    > tests/overnight/rerun/style_$v.log 2>&1
  echo "- $(date '+%F %T') style_$v rc=$?" >> "$S"
  $PY tools/brain/style_hold.py tests/llm-eval/results/style-upset-$v.jsonl > tests/overnight/rerun/style_hold_$v.log 2>&1
  echo "- $(date '+%F %T') style_hold_$v rc=$?" >> "$S"
done
$PY server/patient-service/learning.py rollback v0 >/dev/null
echo "- $(date '+%F %T') style runs finished" >> "$S"
