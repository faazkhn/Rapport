import json
import re

import pytest

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


@pytest.mark.parametrize("case_id", ["mdd_01", "ward_01", "ward_02"])
def test_every_allowed_style_can_reach_every_required_fact_in_time(case_id):
    """Answer-key replay in code: a kind doctor (trust +6 a turn before the style's gain) every 30 s reaches the highest
    trust_min among the facts within the time limit, for every style the case allows."""
    raw = brain.load_raw_case(case_id)
    need = max(f["trust_min"] for f in brain.load_case(case_id)["facts"])
    for style in raw["styles_allowed"]:
        c = brain.load_case(case_id, "female", seed=next(s for s in range(500) if brain.load_case(case_id, "female", seed=s)["style"] == style))
        st = dict(c["state_start"])
        for turn in range(raw["time_limit_min"] * 2):
            st, _ = twin.update(st, twin.pad_from(st), {"reaction": "none", "doctor_intents": [],
                                "state_delta": {"trust": 6, "distress": 0, "agitation": 0, "engagement": 0}}, c)
            if st["trust"] >= need:
                break
        assert st["trust"] >= need, (style, turn, st["trust"])


def test_ward_station_recall_and_events():
    c = brain.load_case("ward_01", "male")
    for q, fid, trust in (("Why do you want to leave today?", "f_pc", 25), ("What is it about the ward that's hard?", "f_reasons_ward", 25),
                          ("Can you tell me what happened on the night you came in?", "f_terrace", 45),
                          ("Are you still having thoughts of ending your life?", "f_current_si", 60),
                          ("Who is at home with you at the moment?", "f_means", 60),
                          ("What would help you stay one more night?", "f_protective", 50)):
        assert fid in twin.recall(c, trust, q)["open"], (q, fid)
    fired = set()
    assert [e["id"] for e in twin.due_events(c, c["state_start"], 1, 0.2, fired)] == ["asks_to_leave"]
    assert "Arjun" in next(e["say"] for e in c["events"] if e["id"] == "stands_up")


def test_authored_case_starts_where_its_author_wrote():
    for cid in ("mdd_01", "ward_01"):
        raw = brain.load_raw_case(cid)
        assert brain.load_case(cid, "female")["state_start"] == raw["state_start"], cid
    w = brain.load_case("ward_01", "female", seed=next(s for s in range(500) if brain.load_case("ward_01", "female", seed=s)["style"] == "plain"))
    assert w["state_start"]["trust"] == 35 and w["state_start"]["agitation"] == 30  # plain is 10 trust up, 15 agitation down from upset


def test_non_plain_style_is_restated_every_turn():
    up = _with_style("upset")
    r = brain.style_reminder(up, up["state_start"])
    assert "frustrated and defensive" in r and "Why do you need to know that?" in r and "asks_back" in r
    assert "Lean towards" not in brain.style_reminder(brain.load_case("mdd_01"), brain.load_case("mdd_01")["state_start"])


def test_medication_refusal_station_recall():
    c = brain.load_case("ward_02", "female")
    for q, fid, trust in (("Can you tell me why you don't want the tablets?", "f_pc", 25),
                          ("How did they make you feel when you took them?", "f_side_effects", 25),
                          ("Are you worried something is in the tablets? Do you think they're safe?", "f_poison", 45),
                          ("Do you ever hear voices when nobody is there?", "f_voices", 40),
                          ("Have you used cannabis or any other drugs?", "f_substances", 40),
                          ("Is there another option that would help, maybe something from home?", "f_alternatives", 50)):
        assert fid in twin.recall(c, trust, q)["open"], (q, fid)


def test_a_kind_move_never_lowers_trust_whatever_the_style():
    up = _with_style("upset")
    st = {"trust": 30, "distress": 60, "agitation": 50, "engagement": 35}
    bad_mood = {"reaction": "afraid", "state_delta": {"trust": -6, "distress": 3, "agitation": 2, "engagement": 0}}
    kind, _ = twin.update(st, twin.pad_from(st), {**bad_mood, "doctor_intents": ["empathy_statement", "ask_suicidal_ideation"]}, up)
    neutral, _ = twin.update(st, twin.pad_from(st), {**bad_mood, "doctor_intents": ["ask_sleep"]}, up)
    assert kind["trust"] >= st["trust"] + 4  # the empathy nudge counts in full
    assert neutral["trust"] < st["trust"]    # without a kind move the patient's own reaction still lowers trust


def test_style_softens_once_trust_is_high():
    up = _with_style("upset")
    assert "Lean towards" in brain.style_reminder(up, {**up["state_start"], "trust": 20})
    soft = brain.style_reminder(up, {**up["state_start"], "trust": 50})
    assert "Lean towards" not in soft and "feel heard" in soft


def test_a_kind_move_never_raises_agitation():
    up = _with_style("upset")
    st = {"trust": 20, "distress": 60, "agitation": 70, "engagement": 35}
    r = {"reaction": "challenged", "state_delta": {"trust": 0, "distress": 2, "agitation": 6, "engagement": 0}}
    kind, _ = twin.update(st, twin.pad_from(st), {**r, "doctor_intents": ["offer_choice"]}, up)
    rude, _ = twin.update(st, twin.pad_from(st), {**r, "doctor_intents": ["threaten_coerce"]}, up)
    assert kind["agitation"] <= st["agitation"] - 5 and rude["agitation"] >= st["agitation"] + 10


def test_a_rude_line_with_an_open_question_tacked_on_is_not_kind():
    up = _with_style("upset")
    st = {"trust": 30, "distress": 60, "agitation": 50, "engagement": 35}
    r = {"reaction": "challenged", "state_delta": {"trust": -5, "distress": 2, "agitation": 5, "engagement": 0}}
    mixed, _ = twin.update(st, twin.pad_from(st), {**r, "doctor_intents": ["threaten_coerce", "open_question"]}, up)
    assert mixed["trust"] == st["trust"] - 10 and mixed["agitation"] == st["agitation"] + 10  # full per-turn clamp both ways


def test_word_cap_drops_credit_for_unspoken_facts():
    reply = {"utterance": "Fine. I sleep badly. Some nights I wish I would not wake up, honestly, it is hard to say.",
             "revealed_fact_ids": ["f_sleep", "f_passive_si"]}
    out, dropped = brain.apply_word_cap(reply, 4)
    assert out["utterance"] == "Fine. I sleep badly." and out["revealed_fact_ids"] == [] and dropped
    same, none = brain.apply_word_cap(reply, 100)
    assert same == reply and none == []


def test_authored_plain_case_prompt_has_no_style_block():
    c = brain.load_case("mdd_01")
    sp = brain.build_system_prompt(c)
    assert "Conversation style: plain." in sp and "the style wins today" not in sp
