"""Turn a Digital Twin session log (logs/twin/*.jsonl) into a Twin view replay timeline (server/patient-service/twin/README.md).

Usage (from Med/): python3 tools/demo/log_to_timeline.py logs/twin/<session>.jsonl -o <timeline.json>
Then open http://127.0.0.1:8765/twin/?timeline=<url of the timeline>.
"""
import argparse
import json
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("log", type=Path)
    ap.add_argument("-o", "--out", type=Path, required=True)
    a = ap.parse_args()
    events = [json.loads(line) for line in a.log.read_text(encoding="utf-8").splitlines() if line.strip()]
    init = next(e for e in events if e["type"] == "init")
    tl = {k: init.get(k, {}) for k in ("meta", "memory_items", "formulation", "state_start")}
    tl["events"] = sorted((e for e in events if e["type"] != "init"), key=lambda e: e["t"])
    a.out.write_text(json.dumps(tl, ensure_ascii=False, indent=1))
    print(f"wrote {a.out} ({len(tl['events'])} events)")


if __name__ == "__main__":
    main()
