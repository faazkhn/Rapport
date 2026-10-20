"""Digital Twin: recall, labels, slow-path update, expression, snapshots. No models loaded."""
import time

import brain
import twin

CASE = brain.load_case("mdd_01")


def test_recall_sleep_open():
    assert "f_sleep" in twin.recall(CASE, 30, "How have you been sleeping?")["open"]


def test_recall_locked_suicide():
    r = twin.recall(CASE, 30, "Have you had thoughts of ending your life?")
    assert "f_passive_si" in r["locked_hit"]
    assert "f_passive_si" not in r["open"]
    assert r["discomfort"] is True


def test_recall_same_line_unlocked():
    assert "f_passive_si" in twin.recall(CASE, 90, "Have you had thoughts of ending your life?")["open"]


def test_recall_no_match():
    assert twin.recall(CASE, 30, "Nice weather today") == {"open": [], "locked_hit": [], "discomfort": False}


def test_recall_fast():
    lines = ["How have you been sleeping?", "Any thoughts of ending your life?", "How is work?", "Nice weather today"]
    t = time.perf_counter()
    for i in range(200):
        twin.recall(CASE, 30, lines[i % 4])
    assert time.perf_counter() - t < 2.0


def test_why_locked():
    reply = {"reaction": "afraid", "behaviour": "deflects"}
    w = twin.why({"open": [], "locked_hit": ["f_passive_si"], "discomfort": True}, reply, 30, CASE)
    assert "locked" in w and "55" in w


def test_why_open():
    w = twin.why({"open": ["f_sleep"], "locked_hit": [], "discomfort": False}, {"reaction": "wary", "behaviour": "guarded_short"}, 42, CASE)
    assert "f_sleep" not in w and "trust 42" in w and "wary" in w


ST = {"trust": 30, "distress": 55, "agitation": 15, "engagement": 35}
ZERO = {k: 0 for k in brain.STATE_KEYS}


def _r(**kw):
    r = {"reaction": "none", "intensity": 5, "behaviour": "answers_plainly", "resistance": "none", "state_delta": dict(ZERO),
         "doctor_intents": []}
    r.update(kw)
    return r


def test_pad_from_matches_js():
    m = twin.pad_from(ST)
    assert (round(m["p"], 4), round(m["a"], 4), round(m["d"], 4)) == (-0.3722, -0.3875, -0.29)


def test_update_understood_raises_trust():
    unit = brain.load_json("state_rules.json")["reaction_trust_unit"]
    new, _ = twin.update(ST, twin.pad_from(ST), _r(reaction="understood"), CASE)
    assert new["trust"] == ST["trust"] + unit
    assert {k: new[k] for k in ("distress", "agitation", "engagement")} == {k: ST[k] for k in ("distress", "agitation", "engagement")}


def test_update_clamped():
    clamp = brain.load_json("state_rules.json")["clamp_per_turn"]
    reply = _r(reaction="warm", state_delta={**ZERO, "trust": 10}, doctor_intents=["explain_confidentiality", "empathy_statement"])
    new, _ = twin.update(ST, twin.pad_from(ST), reply, CASE)
    assert new["trust"] - ST["trust"] <= clamp


def test_mood_moves_toward_target():
    mood = twin.pad_from(ST)
    new, m2 = twin.update(ST, mood, _r(reaction="warm", state_delta={**ZERO, "trust": 8, "engagement": 8}), CASE)
    target = twin.pad_from(new)
    for k in "pad":
        lo, hi = sorted((mood[k], target[k]))
        assert lo <= m2[k] <= hi and m2[k] != mood[k]


def test_expression_filters_unknown_cues():
    e = twin.expression(_r(reaction="startled", behaviour="tearful_disclosure", intensity=10), CASE)  # startle is not an mdd_01 cue
    assert [c["id"] for c in e["cues"]] == ["tearful"]
    assert e["cues"][0]["intensity"] == 0.9 and e["cues"][0]["duration_s"] == 3.0
    assert 0.8 <= e["speed"] <= 1.2
    assert twin.expression(_r(), CASE) == {"cues": [], "speed": 1.0}
