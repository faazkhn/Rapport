"""Build a Digital Twin timeline JSON from the staged demo script.

Inputs: demo/staged/script.json (turns with `brain` blocks), the case file (facts, state_start) and a turn-times JSON
[{"turn": i, "doctor_start": s, "doctor_end": s, "patient_start": s, "patient_end": s}] in seconds from video start
(turn is 1-based). Output format: server/patient-service/twin/README.md.

Usage (from Med/, python3 stdlib only):
  python3 tools/demo/staged_timeline.py --fake-times -o server/patient-service/twin/demo_timeline.json
  python3 tools/demo/staged_timeline.py --times demo/staged/turn_times.json -o demo/staged/timeline.json
An output path ending in .js is written as `window.TWIN_TIMELINE = {...};` so file:// pages can load it with a script tag.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "demo/staged/script.json"
CASES = ROOT / "unity/PsychSim/Assets/StreamingAssets/data/cases"
KEYS = ("trust", "distress", "agitation", "engagement")

# Short human labels for memory items (fact ids in mdd_01).
LABELS = {
    "f_pc": "Tired, not myself",
    "f_onset": "Onset: 2 months ago",
    "f_sleep": "Sleep: wakes at 4 a.m.",
    "f_medical": "Medical: all clear",
    "f_appetite": "Appetite: −4 kg",
    "f_energy_concentration": "Energy, focus low",
    "f_substances": "Substances: none",
    "f_no_psychosis": "Psychosis: none",
    "f_mood": "Mood: low, empty",
    "f_work_family": "Work, family strain",
    "f_no_mania_no_psych_hx": "No mania, no past hx",
    "f_pregnancy": "Not pregnant",
    "f_anhedonia": "Stopped singing",
    "f_anxiety": "Tense, hands shake",
    "f_family_history": "Aunt 'on tablets'",
    "f_guilt": "Guilt: a burden",
    "f_protective": "Amma and Rohan",
    "f_passive_si": "Wish not to wake",
    "f_no_plan_no_attempt": "No plan, no attempt",
    "f_no_means": "No means at home",
}

# 5Ps written from mdd_01 facts. Draft, not faculty-validated.
FORMULATION = {
    "status": "Draft — not faculty-validated",
    "presenting": "Two months of low, empty mood, early waking, poor appetite (−4 kg), loss of interest and "
                  "concentration; passive wishes not to wake, no plan or intent.",
    "predisposing": "Maternal aunt treated for 'nerves'; self-critical, minimising temperament; "
                    "first move away from home.",
    "precipitating": "New project with a demanding manager who criticises {them} in front of the team.",
    "perpetuating": "Guilt and shame at 'being weak', isolation from friends and singing, money pressure "
                    "for Rohan's fees, appraisal next month, marriage talk at home.",
    "protective": "Close to {their} mother and brother Rohan; kind flatmate; came when advised; wants help.",
}

# Cue id -> gaze description for the expression card.
GAZE = {"gaze_avoid": "averted, down and away"}


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def mood_pad(s):
    """Deterministic PAD mood (-1..1) from the 4 state values (0..100). Metaphor, not a validated model."""
    t, d, a, e = (s[k] for k in KEYS)
    p = ((t - 50) * 0.35 + (e - 50) * 0.35 - (d - 50) * 0.9) / 45
    ar = ((a - 30) * 1.0 + (d - 50) * 0.5 + (e - 50) * 0.2) / 40
    dom = ((t - 50) * 0.5 + (e - 50) * 0.5 - (d - 50) * 0.6 - (a - 30) * 0.4) / 50
    return {"p": round(clamp(p, -1, 1), 3), "a": round(clamp(ar, -1, 1), 3), "d": round(clamp(dom, -1, 1), 3)}


def fake_times(turns, start=1.0, doctor_s=4.0, gap=0.6, s_per_word=0.33, between=1.4):
    out, t = [], start
    for i, turn in enumerate(turns, 1):
        ds, de = t, t + doctor_s
        ps = de + gap + (0.4 if turn.get("nonverbal") else 0)
        pe = ps + max(1.2, len(turn["patient"].split()) * s_per_word)
        out.append({"turn": i, "doctor_start": round(ds, 2), "doctor_end": round(de, 2),
                    "patient_start": round(ps, 2), "patient_end": round(pe, 2)})
        t = pe + between
    return out


def build(script, case, variant, times, turns_key="turns"):
    turns = script[turns_key]
    if len(times) < len(turns):
        sys.exit(f"turn-times has {len(times)} entries, script has {len(turns)} turns")
    times = {int(x["turn"]): x for x in times}
    v = case["variants"][variant]
    facts = [f for f in case["facts"] if f.get("variant") in (None, variant)]
    items = [{"id": f["id"], "label": LABELS.get(f["id"], f["id"]), "trust_min": f.get("trust_min", 0),
              "gated": bool(f.get("must_be_asked"))} for f in facts]
    items.sort(key=lambda m: (m["trust_min"], m["id"]))
    state = {k: case["state_start"][k] for k in KEYS}
    events = []
    for i, turn in enumerate(turns, 1):
        tt = times[i]
        b = turn["brain"]
        state = {k: clamp(state[k] + turn["state_delta"].get(k, 0), 0, 100) for k in KEYS}
        cues = [c["id"] for c in turn.get("cues", [])]
        gaze = next((GAZE[c] for c in cues if c in GAZE), "toward the doctor")
        events += [
            {"t": tt["doctor_start"], "type": "doctor_start", "turn": i, "doctor": turn["doctor"]},
            {"t": tt["doctor_end"], "type": "doctor_end", "turn": i},
            {"t": tt["patient_start"], "type": "snapshot", "turn": i, "doctor": turn["doctor"],
             "utterance": turn["patient"], "state": dict(state), "mood": mood_pad(state),
             "reaction": b["reaction"], "intensity": b["intensity"], "behaviour": b["behaviour"],
             "resistance": b["resistance"], "why": b["why"], "recalled": list(b.get("memory", [])),
             "locked_hit": list(b.get("locked_hit", [])), "cues": turn.get("cues", []),
             "exam_action": turn.get("exam_action"), "emotion": turn.get("emotion"),
             "expression": {"face": "face_" + (turn.get("emotion") or "neutral"), "body": cues, "gaze": gaze,
                            "voice": turn.get("voice"), "nonverbal": turn.get("nonverbal")},
             "latency_ms": round((tt["patient_start"] - tt["doctor_end"]) * 1000)},
            {"t": tt["patient_start"], "type": "patient_start", "turn": i},
            {"t": tt["patient_end"], "type": "patient_end", "turn": i},
        ]
    tl = {"meta": {"case_id": case["id"], "patient": v["name"], "age": case["patient"]["age"], "variant": variant,
                   "staged": True, "title": case.get("title")},
          "memory_items": items,
          "formulation": {k: x.format(**v["pronouns"]) for k, x in FORMULATION.items()},
          "state_start": {k: case["state_start"][k] for k in KEYS}, "events": events}
    check(tl)
    return tl


def check(tl):
    ts = [e["t"] for e in tl["events"]]
    assert ts == sorted(ts), "events must be in time order"
    ids = {m["id"] for m in tl["memory_items"]}
    for e in tl["events"]:
        if e["type"] == "snapshot":
            assert all(0 <= e["state"][k] <= 100 for k in KEYS), e["turn"]
            assert all(-1 <= e["mood"][k] <= 1 for k in "pad"), e["turn"]
            assert set(e["recalled"]) <= ids, f"turn {e['turn']}: unknown memory id"
            assert e["latency_ms"] >= 0, f"turn {e['turn']}: patient starts before doctor ends"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--script", type=Path, default=SCRIPT)
    ap.add_argument("--case", type=Path, default=None, help="case JSON (default: cases/<script case_id>.json)")
    ap.add_argument("--variant", default="female", choices=["female", "male"])
    ap.add_argument("--turns-key", default=None, help="script key for turns (default: turns, or arjun_turns for male)")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--times", type=Path, help="turn-times JSON")
    g.add_argument("--fake-times", action="store_true", help="invent plausible times (doctor 4 s, 0.6 s gap, 0.33 s/word)")
    ap.add_argument("-o", "--out", type=Path, required=True)
    a = ap.parse_args()
    script = json.loads(a.script.read_text())
    case = json.loads((a.case or CASES / f"{script['case_id']}.json").read_text())
    key = a.turns_key or ("arjun_turns" if a.variant == "male" else "turns")
    times = fake_times(script[key]) if a.fake_times else json.loads(a.times.read_text())
    tl = build(script, case, a.variant, times, key)
    text = json.dumps(tl, indent=1, ensure_ascii=False)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(f"window.TWIN_TIMELINE = {text};\n" if a.out.suffix == ".js" else text + "\n")
    last = tl["events"][-1]["t"]
    print(f"wrote {a.out} ({len(script[key])} turns, {len(tl['memory_items'])} memory items, ends at {last:.1f} s)")


if __name__ == "__main__":
    main()
