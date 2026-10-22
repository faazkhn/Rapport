import validate_data


def test_all_data_files_valid():
    assert validate_data.validate_all() == []


def test_validator_catches_bad_template_and_banned_word(tmp_path, monkeypatch):
    import json
    import shutil

    import brain
    d = tmp_path / "data"
    shutil.copytree(brain.DATA_DIR, d, ignore=shutil.ignore_patterns("*.meta"))
    p = d / "cases/mdd_01.json"
    c = json.loads(p.read_text())
    c["facts"][0]["text"] += " {cousin} feels depressed."
    c["slots"]["hobby"].append({"hobby": "sertraline club", "hobby_short": "chess"})
    c["slots"]["town"] = [{"hometown": "Udupi"}]
    c["events"] = [{"id": "e", "when": {"after_event": "nope"}, "say": "x", "action": "dance"}]
    p.write_text(json.dumps(c))
    for mod in (brain, validate_data):
        monkeypatch.setattr(mod, "DATA_DIR", d)
    brain.load_json.cache_clear()
    brain._resolved.cache_clear()
    try:
        errs = validate_data.validate_all()
    finally:
        brain.load_json.cache_clear()
        brain._resolved.cache_clear()
    assert any("unknown template {cousin}" in e for e in errs)
    assert any("slot hobby: clinical word" in e for e in errs)
    assert any("the same placeholder in two slots" in e for e in errs)
    assert any("after_event: unknown id 'nope'" in e for e in errs) and any("action: unknown id 'dance'" in e for e in errs)
    assert any("banned word ['depressed']" in e for e in errs)


REACTIONS = ["none", "understood", "hopeful", "relieved", "warm", "calm", "wary", "startled", "afraid", "ashamed",
             "self_conscious", "sad", "numb", "resigned", "challenged", "misunderstood"]
BEHAVIOURS = ["answers_plainly", "minimises", "denies", "deflects", "vague_timeline", "answers_different_question", "tangential",
              "guarded_short", "hostile", "tearful_disclosure", "asks_back", "complies_without_engaging", "complies"]
RESISTANCE = ["none", "quantity", "content", "style"]


def test_brain_catalogue_ids():
    import brain
    cat = brain.load_json("brain/behaviours.json")
    assert [i["id"] for i in cat["reactions"]] == REACTIONS
    assert [i["id"] for i in cat["behaviours"]] == BEHAVIOURS
    assert [i["id"] for i in cat["resistance"]] == RESISTANCE
    for group in ("reactions", "behaviours", "resistance"):
        for i in cat[group]:
            assert i["description"].strip() and i["example"].strip(), i["id"]
    for r in cat["reactions"]:
        assert r["trust_step"] in {-2, -1, 0, 1, 2}, r["id"]


def test_expression_map_refs():
    import brain
    ids = {g: {i["id"] for i in brain.load_json("brain/behaviours.json")[g]} for g in ("reactions", "behaviours")}
    cue_ids = {c["id"] for c in brain.load_json("cues.json")["cues"]}
    m = brain.load_json("brain/expression_map.json")
    for g in ("reactions", "behaviours"):
        for k, e in m[g].items():
            assert k in ids[g], k
            assert {c["id"] for c in e["cues"]} <= cue_ids, k
            assert 0.8 <= e["speed"] <= 1.2, k


def test_mdd01_memory_items():
    import brain
    case = brain.load_raw_case("mdd_01")
    for f in case["facts"]:
        assert f["activation_tags"] and "kind" in f and "generates_discomfort" in f, f["id"]
    flags = {f["id"]: f["generates_discomfort"] for f in case["facts"]}
    assert flags["f_passive_si"] and flags["f_guilt"]
    assert set(case["formulation"]) == {"presenting", "predisposing", "precipitating", "perpetuating", "protective"}


def test_migrate_idempotent():
    from scripts import migrate_memory
    case = {"facts": [{"id": "f_x", "text": "t", "trust_min": 0, "unlock_intents": ["ask_sleep_pattern"]},
                      {"id": "f_y", "text": "t", "trust_min": 0, "activation_tags": ["keep"], "kind": "risk", "generates_discomfort": True}]}
    once = migrate_memory.migrate(json_copy(case))
    assert once["facts"][0]["activation_tags"] == ["sleep pattern"]
    assert once["facts"][1] == case["facts"][1]
    assert migrate_memory.migrate(json_copy(once)) == once


def json_copy(x):
    import json
    return json.loads(json.dumps(x))
