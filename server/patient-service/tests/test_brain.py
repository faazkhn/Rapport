import json
from types import SimpleNamespace

import pytest

import brain

CASE = brain.load_case("mdd_01")
LOW = {"trust": 30, "distress": 55, "agitation": 15, "engagement": 35}
HIGH = {**LOW, "trust": 70}
SI = "f_passive_si"


def test_schema_enums_order_and_strictness():
    allowed = [f["id"] for f in brain.allowed_facts(CASE, 30)]
    s = brain.build_reply_schema(CASE, allowed, brain.allowed_actions(CASE, 30))

    def walk(node):  # strict mode: every object lists all properties as required and forbids extras
        if node.get("type") == "object":
            assert node["additionalProperties"] is False
            assert set(node["required"]) == set(node["properties"])
        for child in node.get("properties", {}).values():
            walk(child)
        if "items" in node:
            walk(node["items"])

    walk(s)
    p = s["properties"]
    assert list(p)[:6] == ["behaviour", "emotion", "utterance", "reaction", "intensity", "resistance"]  # choose how to answer, then speak; the rest after (latency)
    assert p["revealed_fact_ids"]["items"]["enum"] == allowed and SI not in allowed
    assert set(p["event_cues"]["items"]["properties"]["id"]["enum"]) == {c["id"] for c in CASE["cues"]}
    assert p["emotion"]["enum"] == brain.EMOTIONS
    assert p["exam_action"]["anyOf"][1]["enum"] == ["hold_out_hands", "roll_up_sleeves", "look_at_light"]
    assert brain.build_reply_schema(CASE, allowed, [])["properties"]["exam_action"] == {"type": "null"}
    assert "ask_suicidal_ideation" in brain.build_intent_schema()["properties"]["doctor_intents"]["items"]["enum"]
    # the published contract has the same order and the merged fields
    pub = brain.load_json("schemas/patient_reply.schema.json")
    assert list(pub["properties"]) == pub["required"] == ["behaviour", "emotion", "utterance", "reaction", "intensity", "resistance",
                                                          "state_delta", "event_cues", "revealed_fact_ids", "exam_action", "doctor_intents"]


def test_schema_empty_allow_list_has_no_empty_enum():
    s = brain.build_reply_schema(CASE, [])
    assert s["properties"]["revealed_fact_ids"] == {"type": "array", "items": {"type": "string"}, "maxItems": 0}


def test_prompt_fixed_prefix_and_locked_facts_never_sent():
    sys_low, sys_high = brain.build_system_prompt(CASE), brain.build_system_prompt(CASE)
    assert sys_low == sys_high  # fixed prefix: independent of state, so the KV cache is reused
    for f in CASE["facts"]:
        assert f["text"] not in sys_low  # facts only go in the per-turn context
    for phrase in ["next line of Ananya Rao", "Never name or guess any diagnosis", "Never give medical advice",
                   "Never invent symptoms", "abusive", "depressed", "everyday words"]:
        assert phrase in sys_low
    low = brain.build_messages(CASE, LOW, [{"role": "doctor", "text": "Hi"}])
    ctx = low[-1]["content"]
    si_text = next(f["text"] for f in CASE["facts"] if f["id"] == SI)
    assert len(low) == 2 and "\n---\nDoctor: Hi" in ctx and SI not in ctx and si_text not in ctx
    for f in CASE["facts"]:
        assert (f["text"] in ctx) == (f["trust_min"] <= 30)
    assert "Reminder:" in ctx and ctx.rstrip().endswith("Write Ananya Rao's next line in this dialogue.")
    high = brain.build_messages(CASE, HIGH, [{"role": "doctor", "text": "Hi"}], summary="Work is hard.", elapsed_min=5)[-1]["content"]
    assert si_text in high and "ONLY if the doctor asks directly" in high and "Work is hard." in high
    # facts sit at the start of the conversation (cached), the per-turn tail holds no facts
    long = brain.build_messages(CASE, LOW, [{"role": "doctor", "text": "a"}, {"role": "patient", "text": "b"}, {"role": "doctor", "text": "c"}])
    assert long[1]["content"].startswith("WHAT THE PATIENT CAN SHARE NOW") and long[1]["content"].endswith("Doctor: a")
    assert not any(f["text"] in long[-1]["content"] for f in CASE["facts"])


def test_style_reminder_is_transient():
    msgs = [{"role": "doctor", "text": "a"}, {"role": "patient", "text": "b"}, {"role": "doctor", "text": "c"}]
    out = brain.build_messages(CASE, LOW, msgs)
    assert out[1]["content"].endswith("Doctor: a") and out[2]["content"] == "b"  # history verbatim, no reminder stored
    assert sum("Reminder:" in m["content"] for m in out) == 1 and "Reminder:" in out[-1]["content"]
    assert msgs[-1]["text"] == "c"  # caller's history untouched


def test_exam_actions_follow_trust():
    assert brain.allowed_actions(CASE, 20) == ["hold_out_hands", "look_at_light"]
    ctx = brain.facts_block(CASE, {**LOW, "trust": 20})
    assert "roll_up_sleeves: hesitates or refuses" in ctx and "do I have to?" in ctx
    r, d = brain.guard(_reply(exam_action="roll_up_sleeves"), CASE, trust=20)
    assert r["exam_action"] is None and d == [{"kind": "exam_action", "id": "roll_up_sleeves", "reason": "trust"}]
    r, d = brain.guard(_reply(exam_action="roll_up_sleeves"), CASE, trust=40)
    assert r["exam_action"] == "roll_up_sleeves" and d == []
    r, d = brain.guard(_reply(exam_action="stand_up"), CASE, trust=90)  # not listed in this case
    assert r["exam_action"] is None and d[0]["reason"] == "unknown"


def test_guard_strips_banned_sentences():
    r, d = brain.guard(_reply(utterance="I don't know. Maybe I am depressed, doctor. I just feel tired all day."), CASE, trust=30)
    assert r["utterance"] == "I don't know. I just feel tired all day."
    assert d == [{"kind": "banned_word", "id": "depressed", "reason": "sentence removed"}]


def test_history_is_trimmed():
    msgs = [{"role": "doctor" if i % 2 == 0 else "patient", "text": f"m{i}"} for i in range(30)]
    out = brain.build_messages(CASE, LOW, msgs)
    assert len(out) == 2 + brain.HISTORY_TURNS and out[-2]["content"] == "m29" and out[1]["role"] == "user" and out[-1]["role"] == "user"


def _reply(**kw):
    r = {"reaction": "sad", "intensity": 5, "behaviour": "guarded_short", "resistance": "quantity", "emotion": "sad", "utterance": "Hm.", "state_delta": {"trust": 0, "distress": 0, "agitation": 0, "engagement": 0},
         "event_cues": [], "revealed_fact_ids": [], "exam_action": None, "doctor_intents": []}
    r.update(kw)
    return r


def test_guard_drops_unknown_locked_and_unasked_and_clamps():
    r, dropped = brain.guard(_reply(
        revealed_fact_ids=["f_pc", "f_made_up", SI, "f_sleep"],
        event_cues=[{"id": "tearful", "intensity": 3, "duration_s": 2}, {"id": "sweating", "intensity": 0.5, "duration_s": 2}],
        doctor_intents=["ask_sleep", "bogus"],
        state_delta={"trust": 25, "distress": -40, "agitation": 3, "engagement": 0}), CASE, trust=30)
    assert r["revealed_fact_ids"] == ["f_pc", "f_sleep"]
    assert r["event_cues"] == [{"id": "tearful", "intensity": 1.0, "duration_s": 2.0}]
    assert r["doctor_intents"] == ["ask_sleep"]
    assert r["state_delta"] == {"trust": 10, "distress": -10, "agitation": 3, "engagement": 0}
    reasons = {(d["kind"], d["id"]): d["reason"] for d in dropped}
    assert reasons[("fact", "f_made_up")] == "unknown" and reasons[("fact", SI)] == "locked"
    assert reasons[("cue", "sweating")] == "unknown" and ("intent", "bogus") in reasons
    # SI at high trust: kept only if the doctor asked about it this turn
    r2, d2 = brain.guard(_reply(revealed_fact_ids=[SI], doctor_intents=["ask_mood"]), CASE, trust=70)
    assert r2["revealed_fact_ids"] == [] and d2[0]["reason"] == "not_asked"
    r3, _ = brain.guard(_reply(revealed_fact_ids=[SI], doctor_intents=["ask_suicidal_ideation"]), CASE, trust=70)
    assert r3["revealed_fact_ids"] == [SI]


def test_apply_turn_nudges_and_clamps():
    s = brain.apply_turn(LOW, _reply(state_delta={"trust": 8, "distress": 0, "agitation": 0, "engagement": 0},
                                     doctor_intents=["empathy_statement", "explain_confidentiality"]))
    assert s["trust"] == 40  # 8 + 4 + 5 = 17, clamped to 10
    s = brain.apply_turn({**LOW, "trust": 3}, _reply(doctor_intents=["judgmental_language"]))
    assert s["trust"] == 0


class FakeClient:
    def __init__(self, contents):
        self.contents, self.calls = list(contents), []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kw):
        self.calls.append(kw)
        content = self.contents.pop(0)
        if isinstance(content, Exception):
            raise content
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


REQ = {"case_id": "mdd_01", "messages": [{"role": "doctor", "text": "Hello, I'm Dr Rao."}], "state": LOW}
TAG = lambda: ["greet_introduce"]  # noqa: E731


def test_fallback_after_two_bad_replies():
    fc = FakeClient(["not json at all", json.dumps({"utterance": "hi"})])
    out = brain.generate_reply(REQ, client=fc, tagger=TAG)
    assert len(fc.calls) == 2
    assert out["meta"]["fallback"] is True and out["utterance"] in CASE["fallback_lines"]
    assert out["revealed_fact_ids"] == [] and out["state_delta"] == {"trust": 0, "distress": 0, "agitation": 0, "engagement": 0}
    assert out["doctor_intents"] == ["greet_introduce"]


def test_retry_then_success_and_request_shape(monkeypatch):
    good = _reply(utterance="Hello doctor.", revealed_fact_ids=["f_pc"])
    del good["doctor_intents"]
    fc = FakeClient([RuntimeError("timeout"), json.dumps(good)])
    out = brain.generate_reply({**REQ, "model": "grok-4.7", "reasoning_effort": "low"}, client=fc, tagger=TAG)
    assert out["meta"]["fallback"] is False and out["meta"]["attempts"] == 2 and out["utterance"] == "Hello doctor."
    assert out["doctor_intents"] == ["greet_introduce"] and out["revealed_fact_ids"] == ["f_pc"]
    kw = fc.calls[-1]
    assert kw["model"] == "grok-4.7" and kw["reasoning_effort"] == "low" and "extra_body" not in kw
    assert kw["response_format"]["json_schema"]["strict"] is True
    monkeypatch.delenv("PATIENT_LLM", raising=False)
    fc2 = FakeClient([json.dumps(good)])
    brain.generate_reply(REQ, client=fc2, tagger=TAG)
    kw2 = fc2.calls[0]
    assert "reasoning_effort" not in kw2 and kw2["model"] == brain.LOCAL_MODEL
    assert kw2["extra_body"]["cache_prompt"] is True and kw2["extra_body"]["id_slot"] == 0


def test_backend_switch_needs_both_env_vars(monkeypatch):
    monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **k: None)
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    monkeypatch.setenv("PATIENT_LLM", "grok")
    assert brain.use_grok() is False and brain.default_model() == brain.LOCAL_MODEL
    monkeypatch.setenv("XAI_API_KEY", "x")
    assert brain.use_grok() is True and brain.default_model() == brain.GROK_MODEL
    monkeypatch.delenv("PATIENT_LLM")
    assert brain.use_grok() is False


def test_tagger_uses_slot_1_and_never_raises():
    fc = FakeClient([json.dumps({"doctor_intents": ["ask_sleep", "ask_mood"]}), RuntimeError("down")])
    assert brain.tag_intents("How do you sleep?", client=fc, model="local") == ["ask_sleep", "ask_mood"]
    assert fc.calls[0]["extra_body"]["id_slot"] == 1 and fc.calls[0]["temperature"] == 0
    assert brain.tag_intents("x", client=fc, model="local") == []


def test_schema_label_order():
    assert list(brain.build_reply_schema(CASE, [])["properties"])[:6] == ["behaviour", "emotion", "utterance", "reaction", "intensity", "resistance"]


def test_prompt_hides_locked():
    si_text = next(f["text"] for f in CASE["facts"] if f["id"] == SI)
    recalled = {"open": [], "locked_hit": [SI], "discomfort": True}
    out = brain.build_messages(CASE, LOW, [{"role": "doctor", "text": "Any thoughts of ending your life?"}], recalled=recalled)
    assert not any(si_text in m["content"] for m in out)
    assert any("not ready to talk about" in m["content"] for m in out)


def test_prompt_lists_open_recall():
    recalled = {"open": ["f_sleep"], "locked_hit": [], "discomfort": False}
    out = brain.build_messages(CASE, LOW, [{"role": "doctor", "text": "How do you sleep?"}], recalled=recalled)
    assert "WHAT COMES TO MIND" in out[-1]["content"] and "[f_sleep]" in out[-1]["content"]


def test_guard_bad_labels():
    r, dropped = brain.guard(_reply(reaction="furious", intensity=14, behaviour="dances", resistance="sulks"), CASE, trust=30)
    assert (r["reaction"], r["intensity"], r["behaviour"], r["resistance"]) == ("none", 10, "answers_plainly", "none")
    assert sum(d["kind"] == "label" for d in dropped) == 4


def test_generate_reply_uses_twin_recall():
    good = _reply(reaction="warm")
    del good["doctor_intents"]
    llm = FakeClient([json.dumps(good)])
    out = brain.generate_reply({"case_id": "mdd_01", "messages": [{"role": "doctor", "text": "Have you had thoughts of ending your life?"}],
                          "state": LOW}, client=llm, tagger=lambda: [])
    assert any("WHAT COMES TO MIND" in m["content"] and "do not flatly deny" in m["content"] for m in llm.calls[0]["messages"])
    assert out["reaction"] == "wary"


def test_guard_non_finite_intensity():
    r, dropped = brain.guard(_reply(intensity=float("nan")), CASE, trust=30)
    assert r["intensity"] == 0 and any(d["id"] == "intensity" for d in dropped)
