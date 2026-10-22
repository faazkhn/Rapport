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
