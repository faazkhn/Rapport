"""Add the Digital Twin memory-item fields to every fact of a case file; existing values are kept, so it is safe to rerun.

Usage (from server/patient-service): .venv/bin/python scripts/migrate_memory.py <case.json>
"""
import json
import sys


def migrate(case: dict) -> dict:
    for f in case["facts"]:
        f.setdefault("activation_tags", [i.removeprefix("ask_").replace("_", " ") for i in f.get("unlock_intents", [])])
        f.setdefault("kind", "symptom")
        f.setdefault("generates_discomfort", False)
    return case


if __name__ == "__main__":
    path = sys.argv[1]
    with open(path, encoding="utf-8") as fh:
        case = json.load(fh)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(migrate(case), fh, indent=1, ensure_ascii=False)
        fh.write("\n")
