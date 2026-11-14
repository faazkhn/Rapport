"""Digital Twin: the patient's mind for one live turn. Recall with trust locks (no LLM), label checks and the code-built reason,
the slow-path state and mood update, the expression map, and the brain_snapshot. See docs/TWIN.md.
"""
import json
import re

import brain
import learning

VERSION = "twin-0.2"

_WORD = re.compile(r"[a-z']+")
_SUFFIX = re.compile(r"(ing|ed|es|s)$")


_POSSESSIVE = {"my", "your", "their", "his", "her", "our"}


def _stem(w: str) -> str:
    """Crude stem; possessives fold together so "ending their life" matches the tag "ending your life"."""
    return "your" if w in _POSSESSIVE else _SUFFIX.sub("", w) if len(w) > 4 else w


def _words(text: str) -> list[str]:
    return _WORD.findall(text.lower())


def _lexical(items: list[dict], doctor_text: str) -> list[tuple[float, dict]]:
    """Activation-tag matches, best first: a phrase tag scores 2, a single word 1."""
    stemmed = [_stem(w) for w in _words(doctor_text)]
    stems, phrase = set(stemmed), " " + " ".join(stemmed) + " "
    out = []
    for f in items:
        score = 0
        for tag in f.get("activation_tags", []):
            tw = [_stem(w) for w in _words(tag)]
            if len(tw) > 1:
                score += 2 * (" " + " ".join(tw) + " " in phrase)
            elif tw:
                score += tw[0] in stems
        if score:
            out.append((score, f))
    return sorted(out, key=lambda x: -x[0])


# ---------- hybrid recall: tags + sentence embeddings (twin-0.2) ----------
# bge-small-en-v1.5 (MIT) beat all-MiniLM-L6-v2 on the dev half of tests/recall/paraphrase_set.jsonl (right fact in the top 3:
# 0.93 vs 0.87). Each fact is embedded once per case from its recall_probes (authored doctor questions), tags and text.
RECALL_MODEL = "BAAI/bge-small-en-v1.5"
# thresholds tuned on the dev half (tools/recall_bench.py --split dev); the test half is only for reported numbers
SIM_HIT = 0.82  # a fact comes to mind on similarity alone at or above this
SIM_RISK = 0.74  # risk facts: a missed suicide question costs more than an extra locked hit (which only makes the patient evasive)
SIM_NEAR = 0.02  # below SIM_HIT, the best match still counts if it is at least SIM_FLOOR and ahead of the runner-up by this much
SIM_FLOOR = 0.70
RISK_NEAR, RISK_MARGIN = 0.66, 0.06  # in a risk-domain line, other risk facts this close to the best one count too
SIM_STRONG = 0.83  # "strong": the doctor clearly asked about it (code forces a disclosure only on these, never on a recall-level match)
_tuned = {"done": False}


def _load_tuned():
    """Re-tuned thresholds (tools/brain/tune_recall.py, dev half only) override the defaults above, once."""
    global SIM_HIT, SIM_RISK, SIM_FLOOR, SIM_NEAR, RISK_NEAR, RISK_MARGIN
    _tuned["done"] = True
    try:
        t = brain.load_json("brain/recall.json")
        SIM_HIT, SIM_RISK, SIM_FLOOR, SIM_NEAR, RISK_NEAR, RISK_MARGIN = (t[k] for k in ("sim_hit", "sim_risk", "sim_floor", "sim_near", "risk_near", "risk_margin"))
    except (FileNotFoundError, KeyError):
        pass
_emb = {"fn": "unset"}
_vecs: dict = {}


def _recall_embedder():
    import os
    if os.environ.get("RAPPORT_EMBED") == "off":
        return None
    try:
        import numpy as np
        import onnxruntime as ort
        from huggingface_hub import hf_hub_download
        from tokenizers import Tokenizer
        tok = Tokenizer.from_file(hf_hub_download(RECALL_MODEL, "tokenizer.json"))
        tok.enable_padding()
        tok.enable_truncation(64)
        sess = ort.InferenceSession(hf_hub_download(RECALL_MODEL, "onnx/model.onnx"), providers=["CPUExecutionProvider"])
    except Exception:
        return None

    def run(texts):
        enc = tok.encode_batch(texts)
        ids = np.array([e.ids for e in enc], np.int64)
        mask = np.array([e.attention_mask for e in enc], np.int64)
        v = sess.run(None, {"input_ids": ids, "attention_mask": mask, "token_type_ids": np.zeros_like(ids)})[0][:, 0]  # CLS
        return v / np.linalg.norm(v, axis=1, keepdims=True)
    return run


def embed(texts: list[str]):
    """Recall embeddings (unit vectors), or None when the model is not available (then recall is lexical only)."""
    if _emb["fn"] == "unset":
        _emb["fn"] = _recall_embedder()
    return _emb["fn"](texts) if _emb["fn"] and texts else None


def generated_probes(case_id: str) -> dict[str, list[str]]:
    """Doctor lines written offline per fact (tools/brain/gen_lines.py probes -> data/recall/<case>.json); {} if none."""
    try:
        return brain.load_json(f"recall/{case_id}.json")["probes"]
    except (FileNotFoundError, KeyError):
        return {}


def _probes(f: dict, generated: dict | None = None) -> list[str]:
    return [*f.get("recall_probes", []), *(generated or {}).get(f["id"], []), *(t for t in f.get("activation_tags", []) if "{" not in t), f["text"]]


def fact_vectors(case: dict):
    """(fact ids, probe matrix, probe -> fact index) for this case's facts, computed once per filled case (at case load)."""
    gen = generated_probes(case["id"])
    key = (case["id"], case.get("variant"), json.dumps([(f["id"], _probes(f, gen)) for f in case["facts"]]))
    if key not in _vecs:
        import numpy as np
        probes = [(i, p) for i, f in enumerate(case["facts"]) for p in _probes(f, gen)]
        mat = embed([p for _, p in probes])
        _vecs[key] = None if mat is None else ([f["id"] for f in case["facts"]], mat, np.array([i for i, _ in probes]))
        if len(_vecs) > 64:  # seeds come from clients: bounded
            _vecs.pop(next(iter(_vecs)))
    return _vecs[key]


def similarities(case: dict, doctor_text: str, qvec=None) -> dict[str, float]:
    """Best probe similarity per fact id; {} without the embedding model."""
    fv = fact_vectors(case)
    if fv is None or not doctor_text.strip():
        return {}
    import numpy as np
    ids, mat, owner = fv
    q = qvec if qvec is not None else embed([doctor_text])[0]
    best = np.full(len(ids), -1.0)
    np.maximum.at(best, owner, mat @ q)
    return dict(zip(ids, best.tolist()))


_topic_w = {"data": "unset"}


def topic_weights():
    """Hand-set topic vectors (tools/brain/hand_weights.py -> data/brain/topic_weights.json), or None."""
    if _topic_w["data"] == "unset":
        try:
            _topic_w["data"] = brain.load_json("brain/topic_weights.json")
        except FileNotFoundError:
            _topic_w["data"] = None
    return _topic_w["data"]


def hand_topics(doctor_text: str, qvec=None) -> list[str]:
    """Risk topics whose hand-set vector is close enough to the line (cosine >= its threshold)."""
    w = topic_weights()
    if not w or not doctor_text.strip():
        return []
    import numpy as np
    q = qvec if qvec is not None else embed([doctor_text])
    if q is None:
        return []
    q = q if q.ndim == 1 else q[0]
    return [t for t, v in w["vectors"].items() if float(np.dot(v, q)) >= w["thresholds"][t]]


def recall(case: dict, trust: float, doctor_text: str, limit: int = 3, lexical: bool = False, sims: dict | None = None,
           topics: list[str] | None = None) -> dict:
    """Memory items the doctor's words touch: tag matches plus embedding matches (lexical=True: tags only, brain v0). Open ones
    (trust_min <= trust) come best first, at most `limit`; locked ones are only reported as hits, never their content. Trust locks
    apply after matching, so a paraphrase of a locked question is still only a discomfort signal. `strong`: hits by a tag or a
    similarity past the plain threshold (not the near-best or risk-domain rules); code only forces a disclosure on these.
    sims: precomputed similarities() for this line (prepare() recalls twice around the rubric's state step)."""
    if not _tuned["done"]:
        _load_tuned()
    lex = {f["id"]: s for s, f in _lexical(case["facts"], doctor_text)}
    if sims is None:
        sims = {} if lexical else similarities(case, doctor_text)
    if lexical:
        sims = {}
    hits = dict.fromkeys(lex, 0.0)
    strong = set(lex)
    if sims:
        ranked = sorted(sims.items(), key=lambda x: -x[1])
        kinds = {f["id"]: f.get("kind") for f in case["facts"]}
        for fid, s in ranked:
            if s >= (SIM_RISK if kinds.get(fid) == "risk" else SIM_HIT):
                hits[fid] = s
            if s >= max(SIM_STRONG, SIM_HIT if kinds.get(fid) != "risk" else SIM_STRONG):
                strong.add(fid)
        (top, s1), s2 = ranked[0], ranked[1][1] if len(ranked) > 1 else 0.0
        if s1 >= SIM_FLOOR and s1 - s2 >= SIM_NEAR:
            hits[top] = s1
        # a line that is clearly about risk touches every nearby risk fact (a locked hit only makes the patient evasive)
        risk = [(fid, s) for fid, s in ranked if kinds.get(fid) == "risk"]
        if risk and (risk[0][1] >= SIM_RISK or any(kinds.get(f) == "risk" for f in lex)):
            for fid, s in risk:
                if s >= RISK_NEAR and s >= risk[0][1] - RISK_MARGIN:
                    hits[fid] = s
        hits = {fid: sims.get(fid, 0.0) + 0.05 * lex.get(fid, 0) for fid in hits}
    else:
        hits = {fid: float(s) for fid, s in lex.items()}
    if topics:  # the fine-tuned text model read these clinical topics in the line: the facts they ask about come to mind (strong)
        for f in case["facts"]:
            if set(f.get("topics", [])) & set(topics):
                hits[f["id"]] = max(hits.get(f["id"], 0.0), sims.get(f["id"], 0.0)) + 0.1
                strong.add(f["id"])
    facts = sorted((f for f in case["facts"] if f["id"] in hits), key=lambda f: -hits[f["id"]])
    open_ = [f["id"] for f in facts if f["trust_min"] <= trust][:limit]
    locked = [f["id"] for f in facts if f["trust_min"] > trust]
    hit = set(open_) | set(locked)
    # everyday memories (case["life"]): never locked, never credited as facts; two at most so the prompt stays small
    life = [m["id"] for _, m in _lexical(case.get("life", []), doctor_text) if m.get("trust_min", 0) <= trust][:2]
    return {"open": open_, "locked_hit": locked, "discomfort": any(f.get("generates_discomfort") for f in facts if f["id"] in hit),
            "life": life, "strong": [f for f in open_ + locked if f in strong]}


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


def update(state: dict, mood: dict, reply: dict, case: dict, start: dict | None = None, rubric: bool = False) -> tuple[dict, dict]:
    """Slow path: the reaction's trust step joins the model's delta before the one clamp in brain.apply_turn; the mood then
    drifts part of the way toward the PAD of the new state. rubric=True (twin-0.2): the code already stepped the state before the
    call (rubric.pre_step, state is that stepped state), so the reaction step is not added again and the model's trust delta only
    fine-tunes it (+-3); the per-turn clamp then counts from `start`, the state before the turn."""
    rules = brain.load_json("state_rules.json")
    step = 0 if rubric else next((r["trust_step"] for r in brain.catalogue()["reactions"] if r["id"] == reply.get("reaction")), 0)
    st, d = brain.style(case), dict(reply["state_delta"])
    if rubric:
        d["trust"] = max(-3, min(3, d["trust"]))
    trust = d["trust"] + step * rules["reaction_trust_unit"]
    # a kind move (an intent with a positive trust nudge) cannot lower trust: the persona's mood colours the model's own
    # judgement (an upset patient reacts 'wary' to everything), so what the doctor did decides the direction
    intents = reply.get("doctor_intents", [])
    negative = {i["id"] for i in brain.intents() if i.get("negative")}
    kind = any(rules["intent_nudges"].get(i, {}).get("trust", 0) > 0 for i in intents) and not negative & set(intents)
    trust = max(0, trust) if kind else trust
    agitation = min(0, d["agitation"]) if kind else d["agitation"]  # nor raise agitation: de-escalation must be able to work
    delta = {**d, "trust": round(trust * (st["trust_gain"] if trust > 0 else st["trust_loss"])),
             "agitation": round(agitation * st["agitation_gain"]) if agitation > 0 else agitation}
    new = brain.apply_turn(state, {**reply, "state_delta": delta}, rules)
    if start is not None:
        c = rules["clamp_per_turn"]
        new = {k: min(start[k] + c, max(start[k] - c, v)) for k, v in new.items()}
    target, rate = pad_from(new), rules["mood_rate"]
    return new, {k: _clamp(mood[k] + (target[k] - mood[k]) * rate) for k in "pad"}


# ---------- ward events (docs/literature/personalities-and-randomized-patients.md, R9) ----------

_LEAVE_OK = re.compile(r"\b(you (can|may|could|are free to|'re free to) (now )?(go|leave)|you('re| are) (free to go|discharged|good to go)|"
                       r"(go|get) (back )?(to your )?home|(go|leave) (right )?now|leave (my|the|this) (room|cabin|office)|get out|"
                       r"i('ll| will|'m going to| am going to) (let you go|discharge you|send you home)|we('re| are) done|"
                       r"(appointment|consultation) is (done|over|finished))\b")
_LEAVE_BLOCK = re.compile(r"\b(can't|cannot|can not|not|won't|don't|unless|until|if|when|once|after|before|want to|wanna)\b")


def allows_leave(text: str) -> bool:
    """The doctor tells the patient they may go (a statement, not a question, a condition or a refusal). Lexical, so it is known
    before the reply is generated: intents are tagged only after the voice stream."""
    return any(_LEAVE_OK.search(s) and not _LEAVE_BLOCK.search(s)
               for s in re.split(r"(?<=[.!?])\s+", text.lower().replace("’", "'")) if s and not s.rstrip().endswith("?"))


def due_events(case: dict, state: dict, turn: int, elapsed_min: float, fired: set, doctor_text: str = "") -> list[dict]:
    """Case events whose trigger holds now, each at most once per session (adds their ids to `fired`). Triggers, all of
    which must hold: turn (this turn number or later), after_min, trust_at_least, agitation_at_least, agitation_below,
    after_event (another event already fired), doctor_allows_leave (this doctor line lets the patient go). Code decides when;
    the model only plays it."""
    due, before = [], set(fired)  # after_event needs the earlier event on a previous turn
    for e in case.get("events", []):
        w = e["when"]
        if e["id"] in fired or not all((
                turn >= w.get("turn", 0), elapsed_min >= w.get("after_min", 0),
                state["trust"] >= w.get("trust_at_least", 0), state["agitation"] >= w.get("agitation_at_least", 0),
                state["agitation"] < w.get("agitation_below", 101), w.get("after_event") in before | {None},
                not w.get("doctor_allows_leave") or allows_leave(doctor_text))):
            continue
        fired.add(e["id"])
        due.append(e)
    return due


def ongoing_notes(case: dict, fired: set, now: set) -> list[str]:
    """`then` lines of events fired on earlier turns: what has already happened stays true (the patient told they may go does
    not ask to leave again)."""
    return [e["then"] for e in case.get("events", []) if e.get("then") and e["id"] in fired - now]


def apply_event_deltas(state: dict, events: list[dict]) -> dict:
    out = dict(state)
    for e in events:
        for k, v in e.get("state_delta", {}).items():
            out[k] = min(100, max(0, out[k] + v))
    return out


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
                                      "title": case.get("title"), "style": brain.style(case)["label"],
                                      "seed": case.get("generated", {}).get("seed")},
            "memory_items": [{"id": f["id"], "label": f.get("label") or _topic(f["id"]).capitalize(), "trust_min": f["trust_min"],
                              "gated": bool(f.get("must_be_asked"))} for f in case["facts"]],
            "formulation": case.get("formulation", {}), "state_start": {k: state[k] for k in brain.STATE_KEYS}}


def snapshot(turn: int, doctor: str, reply: dict, recalled: dict, state: dict, mood: dict, why_text: str, speed: float = 1.0,
             version: dict | None = None) -> dict:
    """One brain_snapshot in the Twin view's timeline format (twin/README.md)."""
    return {"type": "brain_snapshot", "turn": turn, "doctor": doctor, "utterance": reply["utterance"], "state": state, "mood": mood,
            "reaction": reply["reaction"], "intensity": reply["intensity"], "behaviour": reply["behaviour"],
            "resistance": reply["resistance"], "why": why_text, "recalled": recalled["open"], "locked_hit": recalled["locked_hit"],
            "cues": reply["event_cues"], "exam_action": reply["exam_action"], "emotion": reply["emotion"], "brain_version": learning.brain_version(version),
            # face preset name as Unity's FacePresets builds it; body = the cues this reply fired
            "expression": {"face": f"face_{reply['emotion']}", "body": [c["id"] for c in reply["event_cues"]],
                           "voice": f"{reply['emotion']}, speed ×{speed:.2f} next turn", "nonverbal": None}}
