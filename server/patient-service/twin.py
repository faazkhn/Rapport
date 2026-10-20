"""Digital Twin: the patient's mind for one live turn. Recall with trust locks (no LLM), label checks and the code-built reason,
the slow-path state and mood update, the expression map, and the brain_snapshot. See docs/TWIN.md.
"""
import re

import brain

VERSION = "twin-0.1"

_WORD = re.compile(r"[a-z']+")
_SUFFIX = re.compile(r"(ing|ed|es|s)$")


_POSSESSIVE = {"my", "your", "their", "his", "her", "our"}


def _stem(w: str) -> str:
    """Crude stem; possessives fold together so "ending their life" matches the tag "ending your life"."""
    return "your" if w in _POSSESSIVE else _SUFFIX.sub("", w) if len(w) > 4 else w


def _words(text: str) -> list[str]:
    return _WORD.findall(text.lower())


def recall(case: dict, trust: float, doctor_text: str, limit: int = 3) -> dict:
    """Memory items the doctor's words touch. Open ones (trust_min <= trust) come best first, at most `limit`; locked ones are
    only reported as hits, never their content."""
    # shortcut: lexical tags only, no embeddings; upgrade when an embedding model is chosen (Phase D2)
    stemmed = [_stem(w) for w in _words(doctor_text)]
    stems, phrase = set(stemmed), " " + " ".join(stemmed) + " "
    scored = []
    for f in case["facts"]:
        score = 0
        for tag in f.get("activation_tags", []):
            tw = [_stem(w) for w in _words(tag)]
            if len(tw) > 1:
                score += 2 * (" " + " ".join(tw) + " " in phrase)
            elif tw:
                score += tw[0] in stems
        if score:
            scored.append((score, f))
    scored.sort(key=lambda x: -x[0])
    open_ = [f["id"] for _, f in scored if f["trust_min"] <= trust][:limit]
    locked = [f["id"] for _, f in scored if f["trust_min"] > trust]
    hit = set(open_) | set(locked)
    return {"open": open_, "locked_hit": locked, "discomfort": any(f.get("generates_discomfort") for _, f in scored if f["id"] in hit)}


def _topic(fact_id: str) -> str:
    return fact_id.removeprefix("f_").replace("_", " ")


def why(recalled: dict, reply: dict, trust: float, case: dict) -> str:
    """One plain sentence for the examiner: what came to mind, what stayed locked, and how the patient chose to answer."""
    mins = {f["id"]: f["trust_min"] for f in case["facts"]}
    parts = []
    if recalled.get("open"):
        top = recalled["open"][0]
        parts.append(f"{_topic(top).capitalize()} memory open (trust {trust:.0f} ≥ {mins[top]:.0f}).")
    if recalled.get("locked_hit"):
        need = min(mins[i] for i in recalled["locked_hit"])
        parts.append(f"Touched something locked (needs trust {need:.0f})" + ("; showed discomfort." if recalled.get("discomfort") else "; stayed vague."))
    behaviour = reply.get("behaviour", "answers_plainly").replace("_", " ")
    parts.append(f"Reaction {reply.get('reaction', 'none').replace('_', ' ')}, {behaviour}.")
    return " ".join(parts)


def enforce_discomfort(reply: dict, recalled: dict) -> list[dict]:
    """Code decides: a painful locked hit never gets a reaction that raises trust; returns what was changed, for guard_dropped."""
    steps = {r["id"]: r["trust_step"] for r in brain.catalogue()["reactions"]}
    if not (recalled.get("locked_hit") and recalled.get("discomfort")) or steps.get(reply.get("reaction"), 0) < 0:
        return []
    old, reply["reaction"] = reply.get("reaction"), "wary"
    return [{"kind": "label", "id": "reaction", "reason": f"locked hit: {old!r} -> 'wary'"}]


def _clamp(v: float, lo: float = -1.0, hi: float = 1.0) -> float:
    return min(hi, max(lo, v))


def pad_from(s: dict) -> dict:
    """Pleasure-arousal-dominance from the four state values; the same formula as padFrom in twin/twin.js."""
    t, d, a, e = (s[k] for k in brain.STATE_KEYS)
    return {"p": _clamp(((t - 50) * .35 + (e - 50) * .35 - (d - 50) * .9) / 45),
            "a": _clamp(((a - 30) + (d - 50) * .5 + (e - 50) * .2) / 40),
            "d": _clamp(((t - 50) * .5 + (e - 50) * .5 - (d - 50) * .6 - (a - 30) * .4) / 50)}


def update(state: dict, mood: dict, reply: dict, case: dict) -> tuple[dict, dict]:
    """Slow path: the reaction's trust step joins the model's delta before the one clamp in brain.apply_turn; the mood then
    drifts part of the way toward the PAD of the new state."""
    rules = brain.load_json("state_rules.json")
    step = next((r["trust_step"] for r in brain.catalogue()["reactions"] if r["id"] == reply.get("reaction")), 0)
    delta = {**reply["state_delta"], "trust": reply["state_delta"]["trust"] + step * rules["reaction_trust_unit"]}
    new = brain.apply_turn(state, {**reply, "state_delta": delta}, rules)
    target, rate = pad_from(new), rules["mood_rate"]
    return new, {k: _clamp(mood[k] + (target[k] - mood[k]) * rate) for k in "pad"}


def expression(reply: dict, case: dict) -> dict:
    """Extra cues and a TTS speed factor for this reaction and behaviour; only cues the case has."""
    m = brain.load_json("brain/expression_map.json")
    have = {c["id"] for c in case["cues"]}
    cues, speed = [], 1.0
    for group, key in (("reactions", "reaction"), ("behaviours", "behaviour")):
        e = m[group].get(reply.get(key))
        if not e:
            continue
        speed *= e["speed"]
        cues += [{"id": c["id"], "intensity": round(c["intensity"] * reply.get("intensity", 0) / 10, 2), "duration_s": 3.0}
                 for c in e["cues"] if c["id"] in have]
    return {"cues": cues, "speed": _clamp(speed, 0.8, 1.2)}


def init_event(case: dict, state: dict) -> dict:
    """What the Twin view needs before the first turn. Memory labels are short; full fact text never leaves the service."""
    p = case["patient"]
    return {"event": "init", "meta": {"case_id": case["id"], "patient": p["name"], "age": p["age"], "variant": case["variant"],
                                      "title": case.get("title")},
            "memory_items": [{"id": f["id"], "label": f.get("label") or _topic(f["id"]).capitalize(), "trust_min": f["trust_min"],
                              "gated": bool(f.get("must_be_asked"))} for f in case["facts"]],
            "formulation": case.get("formulation", {}), "state_start": {k: state[k] for k in brain.STATE_KEYS}}


def snapshot(turn: int, doctor: str, reply: dict, recalled: dict, state: dict, mood: dict, why_text: str, speed: float = 1.0) -> dict:
    """One brain_snapshot in the Twin view's timeline format (twin/README.md)."""
    return {"type": "brain_snapshot", "turn": turn, "doctor": doctor, "utterance": reply["utterance"], "state": state, "mood": mood,
            "reaction": reply["reaction"], "intensity": reply["intensity"], "behaviour": reply["behaviour"],
            "resistance": reply["resistance"], "why": why_text, "recalled": recalled["open"], "locked_hit": recalled["locked_hit"],
            "cues": reply["event_cues"], "exam_action": reply["exam_action"], "emotion": reply["emotion"], "brain_version": VERSION,
            # face preset name as Unity's FacePresets builds it; body = the cues this reply fired
            "expression": {"face": f"face_{reply['emotion']}", "body": [c["id"] for c in reply["event_cues"]],
                           "voice": f"{reply['emotion']}, speed ×{speed:.2f} next turn", "nonverbal": None}}
