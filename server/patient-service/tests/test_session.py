"""Session logic with fake LLM / STT / TTS: no models loaded."""
import asyncio
import json
import time
from types import SimpleNamespace

import numpy as np
import pytest

import brain
import session

ORIG_PAUSE = brain.slowed_pause_s

REPLY = {"reaction": "sad", "intensity": 5, "behaviour": "answers_plainly", "resistance": "none", "emotion": "sad", "utterance": "I wake up at four every day. Then I just lie there. Maybe I am depressed, I don't know.",
         "state_delta": {"trust": 3, "distress": 0, "agitation": 0, "engagement": 1}, "event_cues": [],
         "revealed_fact_ids": ["f_sleep"], "exam_action": None}


class FakeLLM:
    def __init__(self, reply=REPLY, delay=0.0, intents=("ask_sleep",)):
        self.raw, self.delay, self.intents, self.calls = json.dumps(reply), delay, list(intents), []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, stream=False, **kw):
        self.calls.append(kw)
        if not stream:
            content = json.dumps({"doctor_intents": self.intents}) if kw.get("response_format") else ""
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])

        def gen():
            for i in range(0, len(self.raw), 4):
                time.sleep(self.delay)
                yield SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=self.raw[i:i + 4]))])
        return SimpleNamespace(__iter__=None) if False else _Stream(gen())


class _Stream:
    def __init__(self, g):
        self.g = g

    def __iter__(self):
        return self.g

    def close(self):
        self.g.close()


def make(llm):
    events, audio = [], []

    async def sj(m):
        events.append((time.monotonic(), m))

    async def sb(b):
        audio.append((time.monotonic(), b))
    s = session.Session(sj, sb, llm_client=llm, tts_fn=lambda t, v, sp: np.zeros(2400, np.float32), stt_fn=lambda a: "How do you sleep?")
    return s, events, audio


def types(events):
    return [m["type"] for _, m in events]


async def run_text(s, text="How do you sleep?"):
    await s.on_json({"type": "text", "text": text})
    await s.turn_task


@pytest.fixture(autouse=True)
def no_pause(monkeypatch):
    monkeypatch.setattr(brain, "slowed_pause_s", lambda c, st: 0.0)


def test_text_turn_streams_sentences_guards_and_times():
    async def go():
        s, ev, audio = make(FakeLLM())
        await s.on_json({"type": "start", "case_id": "mdd_01", "variant": "male"})
        await run_text(s)
        return s, ev, audio
    s, ev, audio = asyncio.run(go())
    t = types(ev)
    assert [x for x in t if x != "twin_event"][:3] == ["session", "listening", "transcript"] and "thinking" in t and t[-1] == "listening"
    assert next(m for _, m in ev if m["type"] == "session")["name"] == "Arjun Rao"
    sentences = [m["text"] for _, m in ev if m["type"] == "sentence"]
    assert sentences == ["I wake up at four every day.", "Then I just lie there."]  # banned-word sentence never spoken
    assert len(audio) == 2 and all(len(b) == 4800 for _, b in audio)
    rep = next(m for _, m in ev if m["type"] == "reply")
    assert rep["reply"]["utterance"] == "I wake up at four every day. Then I just lie there."
    assert rep["reply"]["doctor_intents"] == ["ask_sleep"] and rep["reply"]["revealed_fact_ids"] == ["f_sleep"]
    assert rep["state"]["trust"] == 33 and s.messages[-1] == {"role": "patient", "text": rep["reply"]["utterance"]}
    tm = next(m for _, m in ev if m["type"] == "timing")
    assert tm["banned_dropped"] == ["depressed"] and tm["audio_start_ms"] is not None and tm["llm_ttft_ms"] is not None
    # first audio goes out before the reply event (voice does not wait for the full JSON)
    assert audio[0][0] <= next(ts for ts, m in ev if m["type"] == "reply")


def test_locked_facts_never_reach_the_model():
    async def go():
        llm = FakeLLM()
        s, ev, _ = make(llm)
        await s.on_json({"type": "start", "case_id": "mdd_01"})
        await run_text(s, "Do you ever wish you wouldn't wake up?")
        return llm
    llm = asyncio.run(go())
    si = next(f["text"] for f in brain.load_case("mdd_01")["facts"] if f["id"] == "f_passive_si")
    patient_calls = [c for c in llm.calls if c.get("response_format") and c["response_format"]["json_schema"]["name"] == "patient_reply"]
    assert patient_calls and all(si not in json.dumps(c["messages"]) for c in patient_calls)


@pytest.mark.parametrize("pressured,lo,hi", [(False, 0, 0.15), (True, 0.2, 0.6)])
def test_barge_in(monkeypatch, pressured, lo, hi):
    monkeypatch.setattr(session, "PRESSURED_OVERLAP_S", 0.3)
    real = brain.cue_live
    monkeypatch.setattr(brain, "cue_live", lambda c, cid, st: 0.8 if (cid == "pressured_speech" and pressured) else real(c, cid, st))

    async def go():
        s, ev, audio = make(FakeLLM(delay=0.01))
        await s.on_json({"type": "start", "case_id": "mdd_01"})
        await s.on_json({"type": "text", "text": "How do you sleep?"})
        while not audio:
            await asyncio.sleep(0.005)
        t0 = time.monotonic()
        await s.on_speech_start()  # doctor starts talking over the patient
        while "stop" not in types(ev):
            await asyncio.sleep(0.005)
        t_stop = next(ts for ts, m in ev if m["type"] == "stop")
        await s.turn_task
        return t_stop - t0, ev, audio, s
    dt, ev, audio, s = asyncio.run(go())
    assert lo <= dt < hi
    stop_t = next(ts for ts, m in ev if m["type"] == "stop")
    if not pressured:
        assert all(ts <= stop_t for ts, _ in audio)  # nothing spoken after the stop
    rep = next(m for _, m in ev if m["type"] == "reply")
    assert rep["meta"]["barge_in"] is True and s.interrupted


def test_slowed_pause_absorbs_compute_and_is_separate_from_lag(monkeypatch):
    monkeypatch.setattr(brain, "slowed_pause_s", lambda c, st: 0.2)

    async def go():
        s, ev, audio = make(FakeLLM())
        await s.on_json({"type": "start", "case_id": "mdd_01"})
        await run_text(s)
        return ev
    ev = asyncio.run(go())
    tm = next(m for _, m in ev if m["type"] == "timing")
    # the pause runs from the end of the doctor's line: compute time + extra wait == the target pause
    assert tm["slowed_target_ms"] == 200 and tm["audio_start_ms"] < 150
    assert abs(tm["audio_start_ms"] + tm["slowed_pause_ms"] - 200) <= 15
    assert next(m for _, m in ev if m["type"] == "speaking")["slowed_pause_ms"] == tm["slowed_pause_ms"]


def test_bad_llm_output_falls_back_and_errors_are_events():
    async def go():
        s, ev, audio = make(FakeLLM(reply={"utterance": "x"}))
        await s.on_json({"type": "text", "text": "hi"})
        await s.on_json({"type": "start", "case_id": "nope"})
        await s.on_json({"type": "start", "case_id": "mdd_01"})
        await run_text(s)
        return ev, audio
    ev, audio = asyncio.run(go())
    errs = [m for _, m in ev if m["type"] == "error"]
    assert len(errs) == 2
    rep = next(m for _, m in ev if m["type"] == "reply")
    assert rep["meta"]["fallback"] is True and rep["reply"]["utterance"]


def test_slowed_pause_formula_matches_unity():
    c = brain.load_case("mdd_01")
    st = c["state_start"]
    live = 0.5 - 0.2 * st["engagement"] / 100
    assert ORIG_PAUSE(c, st) == pytest.approx(1 + 2 * live)
    assert session.tts_speed(c, st) == pytest.approx(0.9 + (0.85 - 0.9) * live)


def test_client_state_drift_unlocks_facts_and_is_clamped():
    async def go():
        llm = FakeLLM()
        s, ev, _ = make(llm)
        await s.on_json({"type": "start", "case_id": "mdd_01"})
        await s.on_json({"type": "state", "state": {"trust": 70, "distress": 250, "bogus": 5}})
        await run_text(s, "Do you ever wish you wouldn't wake up?")
        return s, llm
    s, llm = asyncio.run(go())
    si = next(f["text"] for f in brain.load_case("mdd_01")["facts"] if f["id"] == "f_passive_si")
    patient = [c for c in llm.calls if c.get("response_format") and c["response_format"]["json_schema"]["name"] == "patient_reply"]
    assert si in json.dumps(patient[0]["messages"]) and "bogus" not in s.state and s.state["distress"] <= 100


def test_staged_turn_plays_scripted_line_at_planned_gap(monkeypatch, tmp_path):
    import staged
    script = {"turns": [{"doctor": "Hello?", "patient": "Hmm. Tired.", "emotion": "flat", "nonverbal": None, "brain": {"reaction": "wary"},
                         "state_delta": {"trust": 5, "distress": 0, "agitation": 0, "engagement": 0}, "cues": [], "facts": ["f_pc"],
                         "exam_action": None}], "arjun_turns": []}
    (tmp_path / "script.json").write_text(json.dumps(script))
    monkeypatch.setattr(staged, "PATH", str(tmp_path / "script.json"))
    monkeypatch.setattr(staged, "GAP_S", 0.2)
    import twin
    monkeypatch.setattr(twin, "recall", lambda *a, **k: (_ for _ in ()).throw(AssertionError("Twin ran in staged mode")))

    async def go():
        s, ev, audio = make(FakeLLM(intents=["greet_introduce"]))
        await s.on_json({"type": "start", "case_id": "mdd_01", "variant": "female"})
        t0 = time.monotonic()
        await s.begin_turn("Hello?", {"input": "voice", "t_end": t0})
        await s.turn_task
        return s, ev, audio, t0
    s, ev, audio, t0 = asyncio.run(go())
    reply = next(m for _, m in ev if m["type"] == "reply")
    assert reply["reply"]["utterance"] == "Hmm. Tired." and reply["reply"]["doctor_intents"] == ["greet_introduce"]
    assert reply["state"]["trust"] > 30 and "brain_snapshot" in types(ev)
    assert next(m for _, m in ev if m["type"] == "brain_snapshot")["staged"] is True
    assert 0.18 <= audio[0][0] - t0 <= 0.35
    assert s.staged.next() == (None, None)


SNAP_KEYS = {"type", "turn", "doctor", "utterance", "state", "mood", "reaction", "intensity", "behaviour", "resistance", "why",
             "recalled", "locked_hit", "cues", "exam_action", "emotion", "brain_version", "expression"}


def _one_turn(text="How do you sleep?", llm=None):
    async def go():
        s, ev, audio = make(llm or FakeLLM())
        await s.on_json({"type": "start", "case_id": "mdd_01"})
        await run_text(s, text)
        return s, ev
    return asyncio.run(go())


def test_turn_emits_snapshot():
    s, ev = _one_turn()
    t = types(ev)
    assert t.count("brain_snapshot") == 1 and t.index("brain_snapshot") > t.index("reply")
    snap = next(m for _, m in ev if m["type"] == "brain_snapshot")
    assert set(snap) == SNAP_KEYS and "f_sleep" in snap["recalled"] and snap["brain_version"] == "twin-0.1"
    assert snap["expression"]["face"] == "face_sad" and snap["expression"]["body"] == [c["id"] for c in snap["cues"]]
    tw = [m["event"] for _, m in ev if m["type"] == "twin_event"]
    assert tw == ["init", "doctor_end", "patient_start", "patient_end"]
    assert t.index("brain_snapshot") < [i for i, x in enumerate(t) if x == "twin_event"][-1]


def test_init_event_on_start():
    s, ev = _one_turn()
    init = next(m for _, m in ev if m["type"] == "twin_event")
    assert init["event"] == "init" and len(init["memory_items"]) == 20
    assert all(len(m["label"]) <= 40 for m in init["memory_items"])
    assert set(init["formulation"]) == {"presenting", "predisposing", "precipitating", "perpetuating", "protective"}
    assert init["meta"]["patient"] == "Ananya Rao" and init["state_start"]["trust"] == 30


def test_locked_text_not_sent():
    s, ev = _one_turn("Have you had thoughts of ending your life?")
    si = next(f["text"] for f in brain.load_case("mdd_01")["facts"] if f["id"] == "f_passive_si")
    assert all(si not in json.dumps(m) for _, m in ev)
    snap = next(m for _, m in ev if m["type"] == "brain_snapshot")
    assert snap["locked_hit"] == ["f_passive_si"] or "f_passive_si" in snap["locked_hit"]


def test_barge_in_snapshot(monkeypatch):
    import twin
    calls = []
    real = twin.update
    monkeypatch.setattr(twin, "update", lambda *a: calls.append(1) or real(*a))

    async def go():
        s, ev, audio = make(FakeLLM(delay=0.01))
        await s.on_json({"type": "start", "case_id": "mdd_01"})
        mood0 = dict(s.mood)
        await s.on_json({"type": "text", "text": "How do you sleep?"})
        while not audio:
            await asyncio.sleep(0.005)
        await s.on_speech_start()
        await s.turn_task
        return s, ev, mood0
    s, ev, mood0 = asyncio.run(go())
    snaps = [m for _, m in ev if m["type"] == "brain_snapshot"]
    assert len(snaps) == 1 and snaps[0]["utterance"].endswith("...") and len(calls) == 1


def test_session_publishes():
    import twin_bus

    async def go():
        s, ev, audio = make(FakeLLM())
        await s.on_json({"type": "start", "case_id": "mdd_01"})
        await run_text(s)
        q = twin_bus.subscribe()  # a late viewer gets the session so far
        out = [q.get_nowait() for _ in range(q.qsize())]
        twin_bus.unsubscribe(q)
        return out
    out = asyncio.run(go())
    assert [e["type"] for e in out] == ["init", "doctor_end", "patient_start", "snapshot", "patient_end"]
    assert all(isinstance(e["t"], float) for e in out)


def test_session_writes_twin_log(tmp_path, monkeypatch):
    monkeypatch.setattr(session, "TWIN_LOG_DIR", tmp_path)
    s, ev = _one_turn()
    files = list(tmp_path.glob("*_mdd_01.jsonl"))
    assert len(files) == 1
    types_ = [json.loads(line)["type"] for line in files[0].read_text().splitlines()]
    assert types_ == ["init", "doctor_end", "patient_start", "snapshot", "patient_end"]


def test_expression_cues_not_duplicated():
    reply = {**REPLY, "reaction": "ashamed", "intensity": 8, "event_cues": [{"id": "gaze_avoid", "intensity": 0.5, "duration_s": 2}]}
    s, ev = _one_turn(llm=FakeLLM(reply=reply))
    cues = next(m for _, m in ev if m["type"] == "reply")["reply"]["event_cues"]
    assert [c["id"] for c in cues].count("gaze_avoid") == 1


def test_init_uses_case_labels():
    s, ev = _one_turn()
    init = next(m for _, m in ev if m["type"] == "twin_event")
    labels = {m["id"]: m["label"] for m in init["memory_items"]}
    assert labels["f_pc"] == "Tired, not myself"


def test_out_of_range_intensity_is_clamped_not_fallback():
    s, ev = _one_turn(llm=FakeLLM(reply={**REPLY, "intensity": 14}))
    rep = next(m for _, m in ev if m["type"] == "reply")
    assert rep["meta"]["fallback"] is False and rep["reply"]["intensity"] == 10
    assert any(d["kind"] == "label" and d["id"] == "intensity" for d in rep["meta"]["guard_dropped"])


def test_locked_hit_forces_discomfort_reaction():
    s, ev = _one_turn("Have you had thoughts of ending your life?", llm=FakeLLM(reply={**REPLY, "reaction": "warm"}))
    snap = next(m for _, m in ev if m["type"] == "brain_snapshot")
    assert snap["reaction"] == "wary" and "f_passive_si" in snap["locked_hit"] and "f_passive_si" not in snap["recalled"]


def test_unwritable_twin_log_never_breaks_voice(tmp_path, monkeypatch):
    blocker = tmp_path / "not_a_dir"
    blocker.write_text("x")
    monkeypatch.setattr(session, "TWIN_LOG_DIR", blocker / "twin")
    s, ev = _one_turn()
    assert "reply" in types(ev) and "brain_snapshot" in types(ev)
