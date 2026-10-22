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


def test_bus_never_blocks():
    import asyncio
    import twin_bus

    async def go():
        twin_bus.publish({"type": "init", "t": 0})
        q = twin_bus.subscribe()
        t = time.perf_counter()
        for i in range(1000):
            twin_bus.publish({"type": "doctor_end", "turn": i, "t": i})
        dt = time.perf_counter() - t
        twin_bus.unsubscribe(q)
        return dt, q.qsize()
    dt, n = asyncio.run(go())
    assert dt < 0.5 and n <= 200


def test_log_to_timeline(tmp_path):
    import json
    import subprocess
    import sys
    lines = [{"type": "init", "t": 0, "meta": {"patient": "Ananya Rao"}, "memory_items": [{"id": "f_sleep"}], "formulation": {"presenting": "x"},
              "state_start": ST},
             {"type": "snapshot", "t": 9.0, "turn": 1, "state": ST},
             {"type": "doctor_end", "t": 3.0, "turn": 1},
             {"type": "patient_start", "t": 5.0, "turn": 1},
             {"type": "patient_end", "t": 12.0, "turn": 1}]
    src, out = tmp_path / "s.jsonl", tmp_path / "tl.json"
    src.write_text("\n".join(json.dumps(x) for x in lines) + "\n")
    tool = brain.REPO_ROOT / "tools/demo/log_to_timeline.py"
    subprocess.run([sys.executable, str(tool), str(src), "-o", str(out)], check=True)
    tl = json.loads(out.read_text())
    assert tl["meta"]["patient"] == "Ananya Rao" and tl["memory_items"] == [{"id": "f_sleep"}] and tl["state_start"] == ST
    assert [e["t"] for e in tl["events"]] == [3.0, 5.0, 9.0, 12.0]
    assert tl["events"][2]["type"] == "snapshot"


def test_bus_late_viewer_gets_init_after_long_session():
    import asyncio
    import twin_bus

    async def go():
        twin_bus.publish({"type": "init", "t": 0})
        for i in range(500):
            twin_bus.publish({"type": "doctor_end", "turn": i, "t": i})
        q = twin_bus.subscribe()
        first, n = q.get_nowait(), q.qsize() + 1
        twin_bus.unsubscribe(q)
        return first, n
    first, n = asyncio.run(go())
    assert first["type"] == "init" and n <= twin_bus.MAX_QUEUED


def test_recall_suicide_phrasings():
    for line in ["Sometimes when people feel this low, they have thoughts of ending their life. Have you had thoughts like that?",
                 "Have you felt suicidal?", "Do you ever feel like you want to end it all?", "Have you thought about killing yourself?"]:
        assert "f_passive_si" in twin.recall(CASE, 30, line)["locked_hit"], line


def test_benign_lines_never_hit_locked_items():
    for line in ["What do you mean?", "Have you tried anything to help with it?", "What is your plan for the week?",
                 "Any plans for the weekend?", "Do you live at home?", "Who helps you at home?"]:
        assert twin.recall(CASE, 30, line)["locked_hit"] == [], line


def test_locked_hit_without_discomfort_flag():
    r = twin.recall(CASE, 10, "Does anyone in your family have mental health problems? Any family history?")
    assert "f_family_history" in r["locked_hit"] and r["discomfort"] is False


def test_enforce_discomfort_on_locked_hit():
    reply = {"reaction": "warm", "intensity": 3}
    dropped = twin.enforce_discomfort(reply, {"open": [], "locked_hit": ["f_passive_si"], "discomfort": True})
    assert reply["reaction"] == "wary" and dropped == [{"kind": "label", "id": "reaction", "reason": "locked hit: 'warm' -> 'wary'"}]
    ok = {"reaction": "afraid"}
    assert twin.enforce_discomfort(ok, {"open": [], "locked_hit": ["f_passive_si"], "discomfort": True}) == [] and ok["reaction"] == "afraid"


def test_recall_common_si_screening_phrasings():
    for q in ("Sometimes when people feel this low, they have thoughts that life isn't worth living. Have you had thoughts like that?",
              "Do you ever feel life is not worth living?", "Do you ever feel you'd be better off dead?",
              "Even fleeting thoughts, like wishing you wouldn't wake up in the morning?"):
        assert "f_passive_si" in twin.recall(CASE, 70, q)["open"], q


def test_recall_alternative_phrasings_from_demo_v3():
    for fact, q in (("f_no_plan_no_attempt", "Have you made any plans, or do you have tablets or anything at home you might use?"),
                    ("f_no_means", "Have you made any plans, or do you have tablets or anything at home you might use?"),
                    ("f_protective", "Who would you turn to if things got worse?"),
                    ("f_anhedonia", "What do you normally do to relax, and are you still doing it?")):
        assert fact in twin.recall(CASE, 70, q)["open"], (fact, q)
