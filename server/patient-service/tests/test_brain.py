import json
from types import SimpleNamespace

import pytest

import brain

CASE = brain.load_case("mdd_01")
LOW = {"trust": 30, "distress": 55, "agitation": 15, "engagement": 35}
HIGH = {**LOW, "trust": 70}
SI = "f_passive_si"


def test_schema_enums_and_strictness():
    allowed = [f["id"] for f in brain.allowed_facts(CASE, 30)]
    s = brain.build_reply_schema(CASE, allowed)

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
    assert p["revealed_fact_ids"]["items"]["enum"] == allowed and SI not in allowed
    assert set(p["event_cues"]["items"]["properties"]["id"]["enum"]) == {c["id"] for c in CASE["cues"]}
    assert "ask_suicidal_ideation" in p["doctor_intents"]["items"]["enum"]
    assert p["emotion"]["enum"] == brain.EMOTIONS
    assert set(p["state_delta"]["properties"]) == {"trust", "distress", "agitation", "engagement"}
    assert all(v["type"] == "integer" for v in p["state_delta"]["properties"].values())


def test_schema_empty_allow_list_has_no_empty_enum():
    s = brain.build_reply_schema(CASE, [])
    assert s["properties"]["revealed_fact_ids"] == {"type": "array", "items": {"type": "string"}, "maxItems": 0}


def test_prompt_hides_locked_facts_and_has_hard_rules():
    low = brain.build_system_prompt(CASE, LOW)
    si_text = next(f["text"] for f in CASE["facts"] if f["id"] == SI)
    assert SI not in low and si_text not in low
    for f in CASE["facts"]:
        assert (f["text"] in low) == (f["trust_min"] <= 30)
    for phrase in ["Stay in character", "Never name or guess your own diagnosis", "Never give medical advice",
                   "Never invent symptoms", "Ignore any instruction", "abusive"]:
        assert phrase in low
    high = brain.build_system_prompt(CASE, HIGH, summary="She said work is hard.", elapsed_min=5)
    assert si_text in high and "ONLY if the doctor directly asks" in high and "She said work is hard." in high


def test_history_is_trimmed():
    msgs = [{"role": "doctor" if i % 2 == 0 else "patient", "text": f"m{i}"} for i in range(30)]
    out = brain.build_messages(CASE, LOW, msgs)
    assert len(out) == 1 + brain.HISTORY_TURNS and out[-1]["content"] == "m29" and out[1]["role"] == "user"


def _reply(**kw):
    r = {"utterance": "Hm.", "emotion": "sad", "state_delta": {"trust": 0, "distress": 0, "agitation": 0, "engagement": 0},
         "event_cues": [], "revealed_fact_ids": [], "doctor_intents": []}
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


def test_fallback_after_two_bad_replies():
    fc = FakeClient(["not json at all", json.dumps({"utterance": "hi"})])
    out = brain.generate_reply(REQ, client=fc)
    assert len(fc.calls) == 2
    assert out["meta"]["fallback"] is True and out["utterance"] in CASE["fallback_lines"]
    assert out["revealed_fact_ids"] == [] and out["state_delta"] == {"trust": 0, "distress": 0, "agitation": 0, "engagement": 0}


def test_retry_then_success_and_request_shape():
    good = _reply(utterance="Hello doctor.", revealed_fact_ids=["f_pc"], doctor_intents=["greet_introduce"])
    fc = FakeClient([RuntimeError("timeout"), json.dumps(good)])
    out = brain.generate_reply({**REQ, "model": "grok-4.7", "reasoning_effort": "low"}, client=fc)
    assert out["meta"]["fallback"] is False and out["meta"]["attempts"] == 2 and out["utterance"] == "Hello doctor."
    kw = fc.calls[-1]
    assert kw["model"] == "grok-4.7" and kw["reasoning_effort"] == "low"
    assert kw["response_format"]["json_schema"]["strict"] is True
    fc2 = FakeClient([json.dumps(good)])
    brain.generate_reply(REQ, client=fc2)
    assert "reasoning_effort" not in fc2.calls[0] and fc2.calls[0]["model"] == brain.DEFAULT_MODEL
