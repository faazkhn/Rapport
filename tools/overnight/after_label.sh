#!/usr/bin/env bash
# After the two-pass relabelling: fine-tune the text model on CPU, evaluate it, measure recall with it on the test half.
cd "$(dirname "$0")/../.."
PY=server/patient-service/.venv/bin/python
S=tests/overnight/rerun/status.md
until grep -q "label2 rc=" "$S" 2>/dev/null; do sleep 60; done
$PY tools/brain/finetune.py train --id tm-v1 > tests/overnight/rerun/finetune.log 2>&1; echo "- $(date '+%F %T') finetune rc=$?" >> "$S"
$PY tools/brain/finetune.py eval --id tm-v1 > tests/overnight/rerun/finetune_eval.log 2>&1; echo "- $(date '+%F %T') finetune_eval rc=$?" >> "$S"
$PY tools/recall_bench.py --split test --text-model tm-v1 --misses --json tests/overnight/rerun/recall_test_tm.json > tests/overnight/rerun/recall_tm.log 2>&1
echo "- $(date '+%F %T') recall_tm rc=$?" >> "$S"
