import json

import pytest

import brain

RAW = brain.load_raw_case("mdd_01")


def test_fill_templates():
    v = RAW["variants"]["male"]
    assert brain.fill("{They} said {name} told {them} about {their} day.", v) == "He said Arjun Rao told him about his day."
    assert brain.fill("{Their} {they}", RAW["variants"]["female"]) == "Her she"
    assert brain.fill("no {templates} here", v) == "no {templates} here"


@pytest.mark.parametrize("variant,name,model,voice,pron", [
    ("female", "Ananya Rao", "female_20s_a", "Luna", "she"), ("male", "Arjun Rao", "male_20s_a", "Leo", "he")])
def test_resolve_variant(variant, name, model, voice, pron):
    c = brain.load_case("mdd_01", variant)
    p = c["patient"]
    assert (p["name"], p["model_id"], p["voice_id"], p["sex"], c["variant"]) == (name, model, voice, variant, variant)
    assert p["age"] == 24 and c["status"] == "draft"
    blob = json.dumps(c)
    assert "{" + "they}" not in blob and "{name}" not in blob and "{Their}" not in blob
    assert c["referral_note"].startswith(name)
    assert f" {pron} " in next(f["text"] for f in c["facts"] if f["id"] == "f_passive_si")
    assert "variants" not in c


def test_variants_share_clinical_facts_except_tagged():
    f, m = brain.load_case("mdd_01", "female"), brain.load_case("mdd_01", "male")
    fid, mid = [x["id"] for x in f["facts"]], [x["id"] for x in m["facts"]]
    assert "f_pregnancy" in fid and "f_pregnancy" not in mid
    assert [i for i in fid if i != "f_pregnancy"] == mid
    for a, b in zip([x for x in f["facts"] if x["id"] != "f_pregnancy"], m["facts"]):
        assert a["trust_min"] == b["trust_min"] and a.get("unlock_intents") == b.get("unlock_intents")
        # same text once pronouns are normalised: no duplicated or diverging clinical content
        norm = lambda t: t.replace("Ananya Rao", "N").replace("Arjun Rao", "N")  # noqa: E731
        for w, x in [("herself", "X"), ("himself", "X"), ("She", "X"), ("He", "X"), ("Her", "Y"), ("His", "Y"), ("she", "x"), ("he", "x"), ("her", "y"), ("his", "y"), ("him", "y")]:
            norm = (lambda f0, w=w, x=x: lambda t: __import__("re").sub(rf"\b{w}\b", x, f0(t)))(norm)
        assert norm(a["text"]) == norm(b["text"]), a["id"]


def test_resolve_is_a_copy_and_bad_variant_fails():
    c = brain.load_case("mdd_01", "female")
    c["facts"].clear()
    assert brain.load_case("mdd_01", "female")["facts"]
    with pytest.raises(KeyError):
        brain.load_case("mdd_01", "other")
