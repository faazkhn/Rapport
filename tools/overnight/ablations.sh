#!/usr/bin/env bash
# Feature ablations of brain v2 on the depression held-out set (two seeds), one run at a time on the patient's model server.
cd "$(dirname "$0")/../.."
S=tests/overnight/ablation/status.md
for v in v2nr v2nc v2nm v2nh; do
  echo "- $(date '+%F %T') start $v" >> $S
  server/patient-service/.venv/bin/python tools/learning/loop.py heldout $v --case mdd_01 --seeds 11,23 --judge-url http://127.0.0.1:8081/v1 \
    > tests/overnight/ablation/$v.log 2>&1
  echo "- $(date '+%F %T') end $v rc=$?" >> $S
done
echo "- $(date '+%F %T') ablations finished" >> $S
