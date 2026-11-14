"""One Digital Twin turn, the same for both paths (the voice session and typed POST /reply). Before the call: exam routing, ward
events, the rubric's read of the doctor's move and its state step, recall, the decision, memory and the prompt. While speaking:
every sentence passes the same filter. After the call: guard, consistency, the slow-path state and mood update, memory, the
snapshot. The per-session `mind` is plain JSON, so the typed path can carry it between requests.

Features are switched on by the brain version (learned/versions/<id>.json `features`), so `learning.py rollback v0` restores the
old brain: hybrid_recall, rubric, memory, consistency, mse, improvise. See docs/TWIN.md.
"""
import hashlib
import hmac
import json
import os
import random
import secrets

import brain
import consistency
import learning
import memory
import rubric
import stream
import twin

FEATURES = ("hybrid_recall", "rubric", "memory", "consistency", "mse", "improvise", "move_model", "text_model", "hand_topics")
_models: dict = {}


def move_model(model_id: str):
    """The move/intent classifier head (learned/models/<id>.npz, tools/brain/moves_model.py), or None if it is not there."""
    if model_id not in _models:
        import numpy as np
        p = learning.DIR / "models" / f"{model_id}.npz"
        _models[model_id] = dict(np.load(p, allow_pickle=False)) if model_id.replace("-", "").isalnum() and p.exists() else None
    return _models[model_id]


def text_model(model_id: str):
    """The fine-tuned topic/manner model (tools/brain/finetune.py -> learned/models/<id>.onnx), or None if it is not there."""
    key = ("tm", model_id)
    if key not in _models:
        _models[key] = None
        p = learning.DIR / "models"
        if model_id.replace("-", "").isalnum() and (p / f"{model_id}.onnx").exists():
            import json
            import onnxruntime as ort
            from tokenizers import Tokenizer
            tok = Tokenizer.from_file(str(p / f"{model_id}-tokenizer" / "tokenizer.json"))
            tok.enable_truncation(48)
            meta = json.loads((p / f"{model_id}.json").read_text())
            _models[key] = {"sess": ort.InferenceSession(str(p / f"{model_id}.onnx"), providers=["CPUExecutionProvider"]), "tok": tok, **meta}
    return _models[key]


def read_line(model: dict, text: str) -> dict:
    """What the doctor's line asks about (topics) and how it is said (manner), by the fine-tuned model; a few ms on CPU."""
    import numpy as np
    e = model["tok"].encode(text)
    ids, mask = np.array([e.ids], np.int64), np.array([e.attention_mask], np.int64)
    p = 1 / (1 + np.exp(-model["sess"].run(None, {"input_ids": ids, "attention_mask": mask})[0][0]))
    labs = model["topics"] + model["manner"]
    hit = [lab for lab, x, t in zip(labs, p, model["thresholds"]) if x >= t]
    return {"topics": [x for x in hit if x in model["topics"]], "manner": [x for x in hit if x in model["manner"]],
            "p": {lab: round(float(x), 3) for lab, x in zip(labs, p) if x >= 0.2}}


def classify(model: dict, text: str, qvec=None) -> list[str]:
    """Labels whose probability passes their threshold; [] without the embedding model."""
    import numpy as np
    q = qvec if qvec is not None else twin.embed([text])
    if q is None:
        return []
    q = q if q.ndim == 1 else q[0]
    p = 1 / (1 + np.exp(-(model["W"] @ q + model["b"])))
    return [str(lab) for lab, x, t in zip(model["labels"], p, model["thr"]) if x >= t]
MODEL_TRUST_CLAMP = 3  # with the rubric on, the model's own trust delta only fine-tunes the code's step


def features(version: dict | None) -> set[str]:
    return set((version or learning.current()).get("features", [])) & set(FEATURES)


def new(case: dict, state: dict) -> dict:
    return {"turn": 0, "mood": twin.pad_from(state), "fired": [], "memory": memory.new(), "behaviours": [], "calm": 0, "hurt_turns": [],
            "resistance": rubric.base_resistance(case, state["trust"]), "next_speed": 1.0, "interrupted": False, "asked": None,
            "ended": False}


_KEY = (os.environ.get("RAPPORT_TWIN_KEY") or secrets.token_hex(32)).encode()  # per service run unless set


def _sig(m: dict) -> str:
    body = json.dumps({k: v for k, v in m.items() if k != "sig"}, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hmac.new(_KEY, body.encode(), hashlib.sha256).hexdigest()


def sign(m: dict) -> dict:
    """The mind as the typed path returns it: signed, so only minds this service issued are accepted back."""
    return {**m, "sig": _sig(m)}


def load(blob, case: dict, state: dict) -> dict:
    """A mind that came back from a client (typed /reply): only one this service signed, then checked types and bounded sizes;
    anything else starts a fresh mind (a client can neither forge memory nor inject prompt text)."""
    m = new(case, state)
    if not isinstance(blob, dict) or not isinstance(blob.get("sig"), str) or not hmac.compare_digest(blob["sig"], _sig(blob)):
        return m
    try:
        return _load(blob, case, m)
    except (TypeError, ValueError, KeyError, AttributeError):
        return new(case, state)


def _load(blob: dict, case: dict, m: dict) -> dict:
    num = lambda v, lo, hi: isinstance(v, (int, float)) and not isinstance(v, bool) and lo <= v <= hi  # noqa: E731
    if num(blob.get("turn"), 0, 10_000):
        m["turn"] = int(blob["turn"])
    if isinstance(blob.get("mood"), dict) and all(num(blob["mood"].get(k), -1, 1) for k in "pad"):
        m["mood"] = {k: float(blob["mood"][k]) for k in "pad"}
    ids = {e["id"] for e in case.get("events", [])}
    m["fired"] = [e for e in blob.get("fired", []) if e in ids] if isinstance(blob.get("fired"), list) else []
    beh = set(brain.label_ids("behaviours"))
    m["behaviours"] = [b for b in blob.get("behaviours", []) if b in beh][-8:] if isinstance(blob.get("behaviours"), list) else []
    m["hurt_turns"] = [t for t in blob.get("hurt_turns", []) if num(t, 0, 10_000)][-20:] if isinstance(blob.get("hurt_turns"), list) else []
    for k, hi in (("calm", 10_000), ("resistance", 3)):
        if num(blob.get(k), 0, hi):
            m[k] = int(blob[k])
    if num(blob.get("next_speed"), 0.8, 1.2):
        m["next_speed"] = float(blob["next_speed"])
    m["ended"] = blob.get("ended") is True
    m["interrupted"] = blob.get("interrupted") is True
    m["memory"] = memory.sanitize(blob.get("memory"))
    return m


def _should_end(case: dict, mind: dict, state: dict, mv: list[str]) -> bool:
    r = rubric.table()["end_interview"]
    recent = [t for t in mind["hurt_turns"] if t > mind["turn"] - r["window"]]
    return (len(recent) >= r["hurts"] and state["trust"] <= r["trust_max"] and bool(rubric.HURTFUL & set(mv))) or state["agitation"] >= r["agitation_min"]


def _end_event(case: dict) -> dict:
    name = case["patient"]["name"]
    return {"id": "patient_ends", "say": f"{name} has had enough of this doctor and ends the interview: says so in a few words and gets up to leave.",
            "then": f"{name} has ended the interview and is leaving; at most a few words, no more answers.", "action": "stand_up"}


def prepare(case: dict, state: dict, mind: dict, messages: list[dict], elapsed_min: float | None = None, mode: str = "practice",
            version: dict | None = None, summary: str | None = None) -> dict:
    """Everything decided before the model speaks. messages end with this turn's doctor line. Mutates `mind` (turn number, fired
    events, exam ask-back); the rest of the mind changes in finish()."""
    v = version or learning.current()
    on = features(v)
    doctor = next((m["text"] for m in reversed(messages) if m["role"] == "doctor"), "")
    prev_doctor = next((m["text"] for m in reversed(messages[:-1]) if m["role"] == "doctor"), None)
    mind["turn"] += 1
    exam = brain.exam_for_turn(case, state, doctor, mind.get("asked"))
    mind["asked"] = exam and exam.get("asked")
    fired = set(mind["fired"])
    events = twin.due_events(case, state, mind["turn"], elapsed_min or 0.0, fired, doctor)
    mind["fired"] = sorted(fired)
    start = dict(state)
    st = twin.apply_event_deltas(state, events) if events else dict(state)
    after_events = dict(st)
    lexical = "hybrid_recall" not in on
    model = move_model(v.get("move_model", "moves-v1")) if "move_model" in on else None
    qvec = twin.embed([doctor]) if (not lexical or model) and doctor.strip() else None  # one embedding for recall and the classifier
    qvec = qvec[0] if qvec is not None else None
    sims = {} if lexical else twin.similarities(case, doctor, qvec)
    tm = text_model(v.get("text_model", "tm-v1")) if "text_model" in on else None
    read = read_line(tm, doctor) if tm and doctor.strip() else None
    topics = read["topics"] if read else None
    if "hand_topics" in on and not lexical:  # hand-set topic weights (no training): a clear risk topic strongly touches its facts
        topics = list(dict.fromkeys((topics or []) + twin.hand_topics(doctor, qvec)))
    recalled = twin.recall(case, st["trust"], doctor, lexical=lexical, sims=sims, topics=topics)
    mv, plan = [], None
    if "rubric" in on:
        rep = memory.repeated(mind["memory"], recalled, mind["turn"]) if "memory" in on else False
        text_moves = None
        if read and "manner" in v.get("text_model_use", ["topics"]):
            text_moves = [m for m in read["manner"] if m in rubric.table()["moves"]]
        elif model is not None and qvec is not None:  # the classifier replaces the lexical patterns; context moves stay in code
            text_moves = [m for m in classify(model, doctor, qvec) if m in rubric.table()["moves"]]
        mv = rubric.moves(doctor, recalled, case, rep, mind.get("interrupted", False), prev_doctor, text_moves)
        st = rubric.pre_step(st, mv, case)
        c = brain.load_json("state_rules.json")["clamp_per_turn"]  # event + step together stay within one turn's clamp
        st = {k: min(start[k] + c, max(start[k] - c, v)) for k, v in st.items()}
        recalled = twin.recall(case, st["trust"], doctor, lexical=lexical, sims=sims, topics=topics)  # the step may open a lock
        level = rubric.resistance(mind["resistance"], mv, case, st["trust"], mind["calm"])
        if not mind["ended"] and _should_end(case, {**mind, "hurt_turns": mind["hurt_turns"] + [mind["turn"]] * bool(rubric.HURTFUL & set(mv))}, st, mv):
            events = events + [_end_event(case)]
            mind["fired"].append("patient_ends")
        plan = rubric.decide(case, st, level, mv, recalled, mind["behaviours"], exam, mind["ended"] or any(e["id"] == "patient_ends" for e in events))
    mem_lines = []
    if "memory" in on:
        mem_lines = memory.lines(mind["memory"], case, mind["turn"], recalled, mv, doctor)
        if "improvise" in on:
            mem_lines += [f"(said earlier, keep it the same) {t}" for t in memory.improvised_lines(mind["memory"], doctor)]
    examples = learning.retrieve(case["id"], doctor, mode, v.get("examples_k", 0), v.get("library_upto"))
    allowed = [f["id"] for f in brain.allowed_facts(case, st["trust"])]
    schema = brain.build_reply_schema(case, allowed, [], plan=plan, mse=case.get("mse") if "mse" in on else None)
    ended_before = mind["ended"]
    fired_now = {e["id"] for e in events}
    ongoing = twin.ongoing_notes(case, set(mind["fired"]), fired_now)
    if ended_before:
        ongoing.append(_end_event(case)["then"])
    msgs = brain.build_messages(case, st, messages, summary, elapsed_min, recalled, exam, examples, v, events, ongoing, plan=plan,
                                memory_lines=mem_lines,
                                # the cached prefix uses the start state, but never shows a fact the lower of the two trusts locks
                                prefix_state={**start, "trust": min(start["trust"], st["trust"])} if "rubric" in on else after_events)
    turn = {"turn": mind["turn"], "doctor": doctor, "start": start, "state": st, "exam": exam, "events": events, "recalled": recalled,
            "moves": mv, "plan": plan, "allowed": allowed, "schema": schema, "messages": msgs, "examples": examples, "version": v,
            "features": sorted(on), "memory_lines": mem_lines, "clashes": []}
    turn["ctx"] = consistency.context(case, st["trust"], recalled, plan, mind["memory"], "improvise" in on) if "consistency" in on else None
    return turn


def speakable(case: dict, turn: dict, sentence: str, spoken: list[str], earlier: list[str]) -> tuple[str, list[str]]:
    """One sentence on its way to speech: banned words dropped, stage-direction read-outs dropped (event turns), and with the
    consistency feature the code checks. Returns (text to say or "", banned words hit). Clashes go on turn["clashes"]."""
    sentence, hits = brain.strip_banned(sentence, case["banned_words"])
    if turn["events"] and brain.is_stage_direction(sentence, turn["events"], case["patient"]["name"]):
        return "", hits
    if turn["ctx"] and sentence:
        sentence, clashes = consistency.check_sentence(sentence, turn["ctx"], earlier + spoken)
        turn["clashes"] += clashes
    return sentence, hits


def hold(turn: dict, sentence: str, spoken: list[str]) -> bool:
    """On a turn where a denial would break a rule (an open risk fact asked kindly, or a locked one touched), the whole reply is
    held until it is complete and checked as one: a "no" can come in any sentence. Costs latency on those turns only."""
    p = turn["plan"] or {}
    return bool(turn["ctx"]) and not spoken and bool(p.get("must_disclose") or p.get("evasive"))


def final_check(turn: dict, utterance: str) -> str | None:
    """Whole-reply check once the utterance is complete: a replacement line, or None."""
    if not turn["ctx"]:
        return None
    new, clashes = consistency.check_utterance(utterance, turn["ctx"])
    turn["clashes"] += clashes
    return new


def filter_utterance(case: dict, turn: dict, utterance: str, earlier: list[str]) -> tuple[str, list[str]]:
    """The typed path: the same sentence filter and whole-reply check as the voice path, on a finished utterance."""
    spoken, banned = [], []
    for s in stream.split_sentences(utterance):
        s, hits = speakable(case, turn, s, spoken, earlier)
        banned += hits
        if s:
            spoken.append(s)
    text = " ".join(spoken)
    return (final_check(turn, text) or text), banned


def guard_reply(case: dict, turn: dict, raw: dict, tagged: list[str]) -> tuple[dict, list[dict]]:
    """Guard plus the code's decision: labels outside the decided shortlist fall back to its first item, intensity follows the
    MSE cap, and a painful locked hit never gets a reaction that raises trust."""
    reply, dropped = brain.guard({**raw, "doctor_intents": tagged}, case, turn["state"]["trust"])
    p = turn["plan"]
    if p:
        for key, opts in (("behaviour", p["behaviours"]), ("reaction", p["reactions"]), ("resistance", p["resistance"])):
            if reply[key] not in opts:
                dropped.append({"kind": "label", "id": key, "reason": f"{reply[key]!r} not decided -> {opts[0]!r}"})
                reply[key] = opts[0]
        if reply["intensity"] > p["max_intensity"]:
            dropped.append({"kind": "label", "id": "intensity", "reason": f"MSE cap {reply['intensity']} -> {p['max_intensity']}"})
            reply["intensity"] = p["max_intensity"]
    dropped += twin.enforce_discomfort(reply, turn["recalled"])
    return reply, dropped


def finish(case: dict, mind: dict, turn: dict, reply: dict, spoken_ok: bool = True) -> dict:
    """After the reply (already guarded, utterance final): state and mood update, mind update, memory. spoken_ok=False when the
    doctor never heard the reply (barge-in before any sentence): fired events may fire again and their nudges are undone.
    Returns the new state."""
    on = set(turn["features"])
    if turn["events"] and not spoken_ok:
        mind["fired"] = [e for e in mind["fired"] if e not in {x["id"] for x in turn["events"]}]
        base, start = turn["start"], turn["start"]
    else:
        base, start = turn["state"], turn["start"]
        if any(e["id"] == "patient_ends" for e in turn["events"]):
            mind["ended"] = True
    expr = twin.expression(reply, case)
    have = {c["id"] for c in reply["event_cues"]}
    reply["event_cues"] = (reply["event_cues"] + [c for c in expr["cues"] if c["id"] not in have])[:2]
    mind["next_speed"] = expr["speed"]
    new, mind["mood"] = twin.update(base, mind["mood"], reply, case, start=start if "rubric" in on else None, rubric="rubric" in on)
    mind["interrupted"] = False
    if turn["plan"]:
        p, mv = turn["plan"], turn["moves"]
        mind["resistance"] = p["resistance_level"]
        mind["behaviours"] = (mind["behaviours"] + [reply["behaviour"]])[-8:]
        hurtish = rubric.HURTFUL | {"interrupt", "rushed", "premature_reassurance", "repeat_question"}
        mind["calm"] = 0 if hurtish & set(mv) else mind["calm"] + 1
        if rubric.HURTFUL & set(mv):
            mind["hurt_turns"] = (mind["hurt_turns"] + [turn["turn"]])[-20:]
    if "memory" in on and reply["utterance"]:
        memory.record(mind["memory"], case, turn["turn"], turn["doctor"], turn["moves"], turn["recalled"], reply["utterance"],
                      reply["revealed_fact_ids"], twin.allows_leave(turn["doctor"]))
        if "improvise" in on:
            memory.record_improvised(mind["memory"], case, turn["turn"], reply["utterance"])
    return new


def fallback_text(case: dict) -> str:
    return random.choice(case["fallback_lines"])


def snapshot(case: dict, mind: dict, turn: dict, reply: dict, state: dict) -> dict:
    s = twin.snapshot(turn["turn"], turn["doctor"], reply, turn["recalled"], state, mind["mood"],
                      twin.why(turn["recalled"], reply, turn["state"]["trust"], case), mind["next_speed"], turn["version"])
    if turn["plan"]:
        s["decision"] = {k: turn["plan"][k] for k in ("moves", "resistance_level", "behaviours", "reactions", "must_disclose", "evasive", "ended")}
    if turn["clashes"]:
        s["consistency"] = turn["clashes"]
    if turn["memory_lines"]:
        s["memory"] = turn["memory_lines"]
    return s
