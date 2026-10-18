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
    c["facts"][0]["text"] += " {sibling} feels depressed."
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
    assert any("unknown template {sibling}" in e for e in errs)
    assert any("banned word ['depressed']" in e for e in errs)
