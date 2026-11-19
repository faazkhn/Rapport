#!/usr/bin/env bash
# After queue6: the blinded judge-flag rating sheets for the two human raters (all three arms' final runs).
cd "$(dirname "$0")/../.."
S=tests/overnight/papers/status.md
until grep -q "follow-up finished" "$S" 2>/dev/null; do sleep 60; done
server/patient-service/.venv/bin/python tools/human/packets.py flags > tests/overnight/papers/flags_packet.log 2>&1
echo "- $(date '+%F %T') rater sheets written rc=$? (docs/human/)" >> "$S"
