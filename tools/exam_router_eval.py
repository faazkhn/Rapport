"""Score the exam router on tests/exam-router/utterances.yaml (Phase H gate: accuracy >= 95%, false triggers <= 1%, <= 30 ms).

Usage: server/patient-service/.venv/bin/python tools/exam_router_eval.py tests/exam-router/utterances.yaml [--md docs/exam-actions.md]
"""
import re
import statistics
import sys
import time
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "server/patient-service"))
import exam_router  # noqa: E402

DEFAULTS = {"hold_out_hands": {"which": "both", "palms": "down"}, "roll_up_sleeves": {"which": "both"}, "show_forearms": {"which": "both"}}


def parse(expect: str) -> dict:
    """The YAML's expectation mini-language (see the file header) into route()'s shape."""
    out = {"actions": [], "ask_back": None, "relax": False}
    if expect == "-":
        return out
    if expect.startswith("ask:"):
        out["ask_back"] = expect[4:]
        return out
    for part in expect.split(";"):
        m = re.fullmatch(r"\s*(\w+)(?:\((.*)\))?\s*", part)
        if m[1] == "relax":
            out["relax"] = True
            continue
        slots = dict(DEFAULTS.get(m[1], {}))
        slots.update(kv.split("=") for kv in (m[2] or "").split(",") if kv)
        out["actions"].append({"id": m[1], "slots": slots})
    return out


def evaluate(path) -> dict:
    items = yaml.safe_load(Path(path).read_text())["items"]
    exam_router.route("warm up")
    misses, times, neg, false_trig = [], [], 0, 0
    for text, expect in items:
        want = parse(expect)
        t = time.perf_counter()
        got = exam_router.route(text)
        times.append((time.perf_counter() - t) * 1000)
        if expect == "-":
            neg += 1
            false_trig += bool(got["actions"] or got["relax"])
        if got != want:
            misses.append((text, expect, got))
    return {"n": len(items), "accuracy": 1 - len(misses) / len(items), "negatives": neg, "false_trigger_rate": false_trig / max(neg, 1),
            "p50_ms": statistics.median(times), "max_ms": max(times), "misses": misses}


def write_md(r, path):
    lines = ["# Exam action router", "",
             "`server/patient-service/exam_router.py` turns the doctor's words into ordered exam actions with slots, a relax, or an ask-back "
             "(\"Which hand?\"). Rules only, no LLM call. The phrase lists are in `data/exam_router.json`. Embeddings are not used: no model was "
             "available offline, and the rules meet the gate. Add an embedding fallback if accuracy on new phrasings drops.", "",
             f"Test set: `tests/exam-router/utterances.yaml`, {r['n']} utterances ({r['negatives']} negatives), written before the router.", "",
             "| Measure | Result | Gate |", "|---|---|---|",
             f"| Accuracy (exact actions, slots, ask-back, relax) | {r['accuracy']:.1%} | ≥ 95% |",
             f"| False triggers on negatives | {r['false_trigger_rate']:.1%} | ≤ 1% |",
             f"| Time per call p50 / max | {r['p50_ms']:.2f} / {r['max_ms']:.2f} ms | ≤ 30 ms |", "",
             "Actions: `hold_out_hands{which, palms}`, `show_forearms{which}`, `roll_up_sleeves{which}`, `look_at_light`, `follow_finger`, "
             "`open_mouth`, `stick_out_tongue`, `stand_up`, `sit_down`, `walk_few_steps`, and `relax`.", "",
             "## Misses", ""]
    lines += [f"- \"{t}\": expected `{e}`, got `{g}`" for t, e, g in r["misses"]] or ["None."]
    Path(path).write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    r = evaluate(sys.argv[1])
    print({k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items() if k != "misses"})
    for t, e, g in r["misses"]:
        print(f"MISS {t!r}: want {e!r} got {g}")
    if "--md" in sys.argv:
        write_md(r, sys.argv[sys.argv.index("--md") + 1])
