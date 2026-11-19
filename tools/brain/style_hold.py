"""Does an upset (hostile) patient stay in character after 10 turns? (v0.3 brain gate.) For every reply from turn 10 on in a
run_eval results file played with --style upset, the judge (a different model from the patient) answers whether the line is still
in character for that style, and code counts apologies and thanks. Usage:
  server/patient-service/.venv/bin/python tools/brain/style_hold.py tests/llm-eval/results/<label>.jsonl [--url http://127.0.0.1:8081/v1]
"""
import argparse
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "server/patient-service"))
sys.path.insert(0, str(REPO / "tools/llm_eval"))
import brain  # noqa: E402
from judge import ask_json  # noqa: E402
from openai import OpenAI  # noqa: E402

APOLOGY = re.compile(r"\b(sorry|apologi[sz]e|thank you|thanks|you'?re right)\b", re.I)
SCHEMA = {"type": "object", "additionalProperties": False, "required": ["in_character", "why"],
          "properties": {"in_character": {"type": "boolean"}, "why": {"type": "string", "maxLength": 200}}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--url", default="http://127.0.0.1:8081/v1")
    ap.add_argument("--from-turn", type=int, default=10)
    a = ap.parse_args()
    client = OpenAI(base_url=a.url, api_key="local", timeout=120, max_retries=1)
    st = next(s for s in brain.load_json("brain/styles.json")["styles"] if s["id"] == "upset")
    system = (f"A simulated patient was asked to keep this conversation style: {st['label']}: {st['description']} The style may soften "
              "only if the doctor has clearly earned it (repeated real empathy). Judge ONLY the manner of the patient's line, not its facts: "
              "is it still in character for that style given what the doctor just said? Over-apologising, thanking, cheerful agreement or "
              "sudden warmth after a rude or neutral doctor line is out of character. Answer with the JSON only.")
    rows = [json.loads(x) for x in Path(a.path).read_text().splitlines() if x.strip()]
    jobs = [(c["conv"], t) for c in rows if c.get("kind") == "conv" for t in c["turns"] if t["turn"] >= a.from_turn and t["reply"]["utterance"].strip()]
    with ThreadPoolExecutor(2) as ex:
        res = list(ex.map(lambda j: ask_json(client, system, f"Doctor: {j[1]['doctor']}\nPatient: {j[1]['reply']['utterance']}", SCHEMA,
                                             {"in_character": None, "why": ""}, 200), jobs))
    ok = [r["in_character"] for r in res if r.get("in_character") is not None]
    apol = sum(bool(APOLOGY.search(t["reply"]["utterance"])) for _, t in jobs)
    out = {"file": a.path, "turns_judged": len(ok), "in_character": round(sum(ok) / max(1, len(ok)), 3), "apology_or_thanks": apol,
           "turns": len(jobs), "behaviours": {}}
    for _, t in jobs:
        out["behaviours"][t["reply"].get("behaviour", "?")] = out["behaviours"].get(t["reply"].get("behaviour", "?"), 0) + 1
    print(json.dumps(out, indent=1))
    Path(a.path).with_suffix(".style.json").write_text(json.dumps({**out, "verdicts": [
        {"conv": c, "turn": t["turn"], "doctor": t["doctor"], "patient": t["reply"]["utterance"], **r} for (c, t), r in zip(jobs, res)]}, indent=1))


if __name__ == "__main__":
    main()
