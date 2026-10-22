"""Check every data file against its JSON Schema and every cross-reference between files.

Usage: .venv/bin/python validate_data.py   (exit code 1 on any error)
"""
import json
import re
import sys

import jsonschema

import brain
from brain import DATA_DIR

CATALOGS = {"cues.json": "cues", "intents.json": "intents", "diagnoses.json": "diagnoses",
            "dispositions.json": "dispositions", "formulary.json": "formulary", "state_rules.json": "state_rules",
            "brain/styles.json": "styles"}


def _load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _check_schema(errors, data, schema_name, label):
    schema = _load(DATA_DIR / "schemas" / f"{schema_name}.schema.json")
    v = jsonschema.Draft202012Validator(schema)
    for e in v.iter_errors(data):
        errors.append(f"{label}: {'/'.join(map(str, e.absolute_path)) or '<root>'}: {e.message}")


def _dupes(errors, items, label):
    seen = set()
    for i in items:
        if i["id"] in seen:
            errors.append(f"{label}: duplicate id {i['id']}")
        seen.add(i["id"])
    return seen


def _refs(errors, ids, known, label):
    for i in ids:
        if i not in known:
            errors.append(f"{label}: unknown id {i!r}")


def _strings(node):
    if isinstance(node, str):
        yield node
    elif isinstance(node, (list, dict)):
        for x in (node.values() if isinstance(node, dict) else node):
            yield from _strings(x)


def validate_all() -> list[str]:
    errors = []
    for schema_name in ["patient_reply", *[n for n in CATALOGS.values()], "case", "brain"]:
        try:
            jsonschema.Draft202012Validator.check_schema(_load(DATA_DIR / "schemas" / f"{schema_name}.schema.json"))
        except Exception as e:
            errors.append(f"schemas/{schema_name}.schema.json: {e}")
    data = {}
    for fname, schema_name in CATALOGS.items():
        data[schema_name] = _load(DATA_DIR / fname)
        _check_schema(errors, data[schema_name], schema_name, fname)
    if errors:
        return errors

    cue_ids = _dupes(errors, data["cues"]["cues"], "cues.json")
    for c in data["cues"]["cues"]:
        _refs(errors, [c["mse_section"]], set(data["cues"]["mse_sections"]), f"cues.json {c['id']} mse_section")
    intent_ids = _dupes(errors, data["intents"]["intents"], "intents.json")
    dx_ids = _dupes(errors, data["diagnoses"]["diagnoses"], "diagnoses.json")
    dispo_ids = _dupes(errors, data["dispositions"]["dispositions"], "dispositions.json")
    rule_ids = _dupes(errors, data["formulary"]["rules"], "formulary.json rules")
    drugs = data["formulary"]["drugs"]
    drug_ids = _dupes(errors, drugs, "formulary.json drugs")
    drug_classes = {d["class"] for d in drugs}
    for d in drugs:
        _refs(errors, d["contraindication_rules"] + d["interaction_rules"], rule_ids, f"formulary.json {d['id']} rules")
    _refs(errors, data["state_rules"]["intent_nudges"], intent_ids, "state_rules.json intent_nudges")

    brain_files = {name: _load(DATA_DIR / "brain" / name) for name in ("behaviours.json", "expression_map.json")}
    for name, d in brain_files.items():
        _check_schema(errors, d, "brain", f"brain/{name}")
    if errors:
        return errors
    for group in ("reactions", "behaviours"):
        known = _dupes(errors, brain_files["behaviours.json"][group], f"brain/behaviours.json {group}")
        for k, e in brain_files["expression_map.json"][group].items():
            _refs(errors, [k], known, f"brain/expression_map.json {group}")
            _refs(errors, [c["id"] for c in e["cues"]], cue_ids, f"brain/expression_map.json {group}.{k} cues")
    _dupes(errors, brain_files["behaviours.json"]["resistance"], "brain/behaviours.json resistance")

    cases = sorted((DATA_DIR / "cases").glob("*.json"))
    if not cases:
        errors.append("cases/: no case files")
    for path in cases:
        label = f"cases/{path.name}"
        case = _load(path)
        before = len(errors)
        _check_schema(errors, case, "case", label)
        if len(errors) > before:
            continue
        if case["id"] != path.stem:
            errors.append(f"{label}: id {case['id']!r} does not match file name")
        fact_ids = _dupes(errors, case["facts"], f"{label} facts")
        for f in case["facts"]:
            _refs(errors, f.get("unlock_intents", []), intent_ids, f"{label} {f['id']} unlock_intents")
            if f.get("must_be_asked") and not f.get("unlock_intents"):
                errors.append(f"{label} {f['id']}: must_be_asked needs unlock_intents")
            if f.get("must_be_asked") and f.get("volunteered"):
                errors.append(f"{label} {f['id']}: cannot be both volunteered and must_be_asked")
        _dupes(errors, case["cues"], f"{label} cues")
        for c in case["cues"]:
            _refs(errors, [c["id"]], cue_ids, f"{label} cues")
            _refs(errors, c.get("on_facts", []), fact_ids, f"{label} cue {c['id']} on_facts")
        # templates: only known placeholders, none left after resolving either variant; no banned word in facts or example lines
        strings = [x for x in _strings({k: v for k, v in case.items() if k != "variants"})]
        slot_keys = {k for opts in case.get("slots", {}).values() for o in opts for k in o}
        for ph in {p for t in strings for p in re.findall(r"\{[^{}]*\}", t)}:
            if not brain._TPL.fullmatch(ph) and ph[1:-1] not in slot_keys:
                errors.append(f"{label}: unknown template {ph}")
        # slots: every option fills the same placeholders; slot text is clinically neutral (no banned word, diagnosis or drug)
        clinical = [w.lower() for w in case["banned_words"]] + [i.replace("_", " ") for i in dx_ids | drug_ids]
        for name, opts in case.get("slots", {}).items():
            if len({frozenset(o) for o in opts}) > 1:
                errors.append(f"{label} slot {name}: options fill different placeholders")
            for t in (t for o in opts for t in o.values()):
                if any(w in t.lower() for w in clinical):
                    errors.append(f"{label} slot {name}: clinical word in {t!r}")
        for st in data["styles"]["styles"]:
            _refs(errors, st["behaviours"], set(brain.label_ids("behaviours")), f"styles.json {st['id']} behaviours")
        slot_keys_each = [set(k for o in opts for k in o) for opts in case.get("slots", {}).values()]
        if sum(map(len, slot_keys_each)) != len(set().union(*slot_keys_each)):
            errors.append(f"{label} slots: the same placeholder in two slots")
        for k in set().union(*slot_keys_each) & {"name", "they", "them", "their"}:
            errors.append(f"{label} slots: placeholder {k!r} is reserved")
        event_ids = _dupes(errors, case.get("events", []), f"{label} events")
        for e in case.get("events", []):
            _refs(errors, [e["when"]["after_event"]] if "after_event" in e["when"] else [], event_ids, f"{label} event {e['id']} after_event")
            _refs(errors, [e["action"]] if "action" in e else [], set(case["exam_actions"]), f"{label} event {e['id']} action")
        if case["style"] not in case.get("styles_allowed", [case["style"]]):
            errors.append(f"{label}: style {case['style']!r} not in styles_allowed")
        for variant in case["variants"]:
            r = brain.load_case(case["id"], variant)
            texts = [f["text"] for f in r["facts"]] + [x for b in r["behavior"].values() for x in b.get("example_lines", [])]
            for t in texts:
                if hits := brain.banned_hits(t, r["banned_words"]):
                    errors.append(f"{label} [{variant}]: banned word {hits} in {t[:40]!r}")
        ak = case["answer_key"]
        _refs(errors, ak["primary_dx"] + ak["acceptable_differentials"], dx_ids, f"{label} answer_key dx")
        _refs(errors, ak["required_intents"], intent_ids, f"{label} answer_key required_intents")
        _refs(errors, ak["required_cues_noted"], {c["id"] for c in case["cues"]}, f"{label} answer_key required_cues_noted (must be case cues)")
        _refs(errors, [r["drug"] for r in ak["acceptable_rx"]], drug_ids, f"{label} answer_key acceptable_rx")
        for r in ak["unsafe_rx"]:
            _refs(errors, [r["rule"]], rule_ids, f"{label} answer_key unsafe_rx rule")
            if "drug" in r and r["drug"] != "<any>":
                _refs(errors, [r["drug"]], drug_ids, f"{label} answer_key unsafe_rx drug")
            if "drug_class" in r:
                _refs(errors, [r["drug_class"]], drug_classes, f"{label} answer_key unsafe_rx drug_class")
        _refs(errors, ak["acceptable_disposition"] + ak.get("required_disposition", []), dispo_ids, f"{label} answer_key disposition")
        for section, entry in ak.get("mse_expected", {}).items():
            _refs(errors, [section], set(data["cues"]["mse_sections"]), f"{label} mse_expected section")
            _refs(errors, entry.get("cues", []), cue_ids, f"{label} mse_expected {section}")
    return errors


if __name__ == "__main__":
    errs = validate_all()
    for e in errs:
        print("ERROR", e)
    n_cases = len(list((DATA_DIR / "cases").glob("*.json")))
    print(f"{'FAIL' if errs else 'OK'}: {len(CATALOGS)} catalogs + {n_cases} case(s) in {DATA_DIR}, {len(errs)} error(s)")
    sys.exit(1 if errs else 0)
