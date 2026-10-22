import json
import re

import brain
import twin

RISK = ("f_passive_si", "f_no_plan_no_attempt", "f_no_means", "f_protective")
SEEDS = range(40)


def _strings(node):
    if isinstance(node, str):
        yield node
    elif isinstance(node, (list, dict)):
        for x in (node.values() if isinstance(node, dict) else node):
            yield from _strings(x)


def test_no_seed_gives_the_authored_case():
    c = brain.load_case("mdd_01", "female")
    text = json.dumps(c)
    assert "Carnatic singing" in text and "Rohan" in text and "Mysuru" in text
    assert c["style"] == "plain" and "generated" not in c


def test_same_seed_same_case():
    assert brain.load_case("mdd_01", "male", seed=7) == brain.load_case("mdd_01", "male", seed=7)


def test_seeds_vary_the_patient():
    picks = {(c["generated"]["style"], json.dumps(c["generated"]["slots"], sort_keys=True))
             for c in (brain.load_case("mdd_01", "female", seed=s) for s in SEEDS)}
    assert len(picks) > 10
    assert {s for s, _ in picks} == set(brain.load_raw_case("mdd_01")["styles_allowed"])


def test_generated_case_keeps_answer_key_risk_and_exam():
    base = brain.load_case("mdd_01", "female")
    facts = {f["id"]: f for f in base["facts"]}
    for s in SEEDS:
        c = brain.load_case("mdd_01", "female", seed=s)
        for k in ("answer_key", "scales", "exam", "exam_actions", "rubric", "banned_words"):
            assert c[k] == base[k], (s, k)
        for f in c["facts"]:
            assert f["trust_min"] == facts[f["id"]]["trust_min"], (s, f["id"])
            if f["id"] in RISK[:3]:
                assert f == facts[f["id"]], (s, f["id"])
        assert not [t for t in _strings(c) if re.search(r"\{[a-zA-Z_]+\}", t)], s


def test_assessment_mode_keeps_the_authored_style():
    assert {brain.load_case("mdd_01", "female", seed=s, mode="assessment")["style"] for s in SEEDS} == {"plain"}


def test_recall_follows_the_slot_values():
    for s in SEEDS:
        c = brain.load_case("mdd_01", "female", seed=s)
        hobby = c["generated"]["slots"]["hobby"]["hobby_short"]
        sib = c["generated"]["slots"]["sibling"]["sibling"]
        assert "f_anhedonia" in twin.recall(c, 50, f"Do you still have time for {hobby}?")["open"], (s, hobby)
        assert sib in next(f["text"] for f in c["facts"] if f["id"] == "f_protective")


def _with_style(style, variant="female"):
    s = next(s for s in range(200) if brain.load_case("mdd_01", variant, seed=s)["style"] == style)
    return brain.load_case("mdd_01", variant, seed=s)


def test_style_offsets_start_state_and_plain_changes_nothing():
    base = brain.load_case("mdd_01", "female")
    assert _with_style("plain")["state_start"] == base["state_start"]
    up = _with_style("upset")
    assert up["state_start"]["trust"] == base["state_start"]["trust"] - 10
    assert up["state_start"]["agitation"] == base["state_start"]["agitation"] + 15


def test_style_shows_in_prompt_and_reminder():
    c = _with_style("reserved")
    sp = brain.build_system_prompt(c)
    assert "reserved" in sp and "Fine." in sp
    assert "one short sentence" in brain.style_reminder(c, {**c["state_start"], "engagement": 90})


def test_style_scales_trust_change():
    up, pl = _with_style("upset"), _with_style("plain")
    state = {"trust": 40, "distress": 50, "agitation": 20, "engagement": 40}
    mood = twin.pad_from(state)
    reply = {"reaction": "none", "state_delta": {"trust": -6, "distress": 0, "agitation": 4, "engagement": 0}, "doctor_intents": []}
    s_up, _ = twin.update(state, mood, reply, up)
    s_pl, _ = twin.update(state, mood, reply, pl)
    assert s_up["trust"] < s_pl["trust"] and s_up["agitation"] > s_pl["agitation"]


def test_word_cap_keeps_whole_sentences():
    text = "I don't know. Maybe it is work. Maybe it is everything, doctor, all of it together at once."
    assert brain.cap_words(text, 5) == "I don't know."
    assert brain.cap_words(text, 100) == text
    assert brain.cap_words("One very long sentence without any stop at all here", 3) == "One very long sentence without any stop at all here"


def test_every_allowed_style_can_reach_every_required_fact_in_time():
    """Answer-key replay in code: a kind doctor (trust +6 a turn before the style's gain) every 30 s reaches the highest
    trust_min among the facts within the time limit, for every style the case allows."""
    raw = brain.load_raw_case("mdd_01")
    need = max(f["trust_min"] for f in brain.load_case("mdd_01")["facts"])
    for style in raw["styles_allowed"]:
        c = _with_style(style)
        st = dict(c["state_start"])
        for turn in range(raw["time_limit_min"] * 2):
            st, _ = twin.update(st, twin.pad_from(st), {"reaction": "none", "doctor_intents": [],
                                "state_delta": {"trust": 6, "distress": 0, "agitation": 0, "engagement": 0}}, c)
            if st["trust"] >= need:
                break
        assert st["trust"] >= need, (style, turn, st["trust"])
