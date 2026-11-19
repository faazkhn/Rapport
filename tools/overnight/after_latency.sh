#!/usr/bin/env bash
# Two-pass relabelling for the fine-tuned classifier, once the re-run's latency step no longer needs the GPU to itself.
cd "$(dirname "$0")/../.."
until grep -q "end latency_v2" tests/overnight/rerun/status.md 2>/dev/null; do sleep 60; done
until curl -sf http://127.0.0.1:8081/health >/dev/null; do sleep 30; done
server/patient-service/.venv/bin/python tools/brain/moves_model.py label2 --url http://127.0.0.1:8081/v1 > tests/overnight/rerun/label2.log 2>&1
echo "- $(date '+%F %T') label2 rc=$?" >> tests/overnight/rerun/status.md
