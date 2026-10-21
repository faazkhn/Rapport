"""Phase E learning: versions, gate, experience library, principles. No models loaded."""
import json
import shutil
from types import SimpleNamespace

import numpy as np
import pytest

import brain
import learning


@pytest.fixture(autouse=True)
def _fresh(monkeypatch, tmp_path):
    shutil.copytree(learning.DIR, tmp_path / "learned")
    monkeypatch.setattr(learning, "DIR", tmp_path / "learned")
    learning._cache.clear()
    yield
    learning._cache.clear()


def test_brain_version_string():
    assert learning.current()["id"] == "v0"
    assert learning.brain_version() == "twin-0.1+v0"


def test_rollback_unknown_keeps_current():
    with pytest.raises(KeyError):
        learning.set_current("nope")
    assert learning.current()["id"] == "v0"


def test_save_and_rollback():
    learning.save_version({**learning.load_version("v0"), "id": "v1", "parent": "v0", "examples_k": 2})
    learning.set_current("v1")
    assert learning.current()["examples_k"] == 2
    learning.set_current("v0")
    assert learning.current()["id"] == "v0"
    assert [v["id"] for v in learning.versions()] == ["v0", "v1"]


CASE = brain.load_case("mdd_01")
LOW = {"trust": 30, "distress": 55, "agitation": 15, "engagement": 20}
OK_META = {"fallback": False, "guard_dropped": []}


def test_gate_reasons():
    assert learning.gate("Just tired. Can't sleep.", OK_META, CASE, LOW, []) == []
    assert "too_long" in learning.gate(" ".join(["word"] * 20), OK_META, CASE, LOW, [])
    meta = {"fallback": False, "guard_dropped": [{"kind": "banned_word", "id": "depressed", "reason": "sentence removed"}]}
    assert "banned_word" in learning.gate("Fine.", meta, CASE, LOW, [])
    assert "repeats" in learning.gate("I just feel so tired.", OK_META, CASE, LOW, ["Honestly I just feel so tired all day."])
    assert "fact_dropped" in learning.gate("Ok.", {"fallback": False, "guard_dropped": [{"kind": "fact", "id": "x"}]}, CASE, LOW, [])
    assert "break_character" in learning.gate("I'm an AI.", OK_META, CASE, LOW, [])
    assert "fallback" in learning.gate("Sorry?", {"fallback": True, "guard_dropped": []}, CASE, LOW, [])


def _fake_embed(texts):
    vocab = ["sleep", "night", "mood", "work", "family", "eat"]
    v = np.array([[1.0 if w in t.lower() else 0.0 for w in vocab] + [0.01] for t in texts], np.float32)
    return v / np.linalg.norm(v, axis=1, keepdims=True)


def _entry(doctor, utterance, tier="candidate", judged=True):
    return {"doctor": doctor, "utterance": utterance, "engagement": 30, "trust": 30, "behaviour": "answers_plainly", "tier": tier,
            "source": "self_play", "judged": judged}


def test_consent_default_off():
    assert learning.add_experience("mdd_01", {**_entry("How do you sleep?", "Badly."), "source": "live"}, consent=False) is None
    assert not (learning.DIR / "experience" / "mdd_01.jsonl").exists()
    assert learning.add_experience("mdd_01", {**_entry("How do you sleep?", "Badly."), "source": "live"}, consent=True)["id"]


def test_retrieve_modes(monkeypatch):
    monkeypatch.setattr(learning, "_embedder", _fake_embed)
    c = learning.add_experience("mdd_01", _entry("How do you sleep at night?", "I wake at four."), consent=False)
    a = learning.add_experience("mdd_01", _entry("How is work?", "Work is too much.", tier="approved"), consent=False)
    assert [e["id"] for e in learning.retrieve("mdd_01", "Sleep okay at night?", "practice", 1)] == [c["id"]]
    assert learning.retrieve("mdd_01", "Sleep okay at night?", "assessment", 2) == []  # only approved, and it is not similar
    assert [e["id"] for e in learning.retrieve("mdd_01", "And work?", "assessment", 2)] == [a["id"]]
    assert learning.retrieve("mdd_01", "Sleep?", "practice", 0) == []


def test_approve_makes_entry_usable_in_assessment(monkeypatch):
    monkeypatch.setattr(learning, "_embedder", _fake_embed)
    c = learning.add_experience("mdd_01", _entry("How do you sleep at night?", "I wake at four."), consent=False)
    assert learning.approve("mdd_01", c["id"]) is True
    assert [e["id"] for e in learning.retrieve("mdd_01", "Sleep at night?", "assessment", 1)] == [c["id"]]
    assert learning.approve("mdd_01", "missing") is False


def test_retrieve_no_embedder():
    learning.add_experience("mdd_01", _entry("How do you sleep?", "Badly."), consent=False)
    assert learning.retrieve("mdd_01", "How do you sleep?", "practice", 2) == []


def test_retrieve_skips_unjudged(monkeypatch):
    monkeypatch.setattr(learning, "_embedder", _fake_embed)
    learning.add_experience("mdd_01", _entry("How do you sleep?", "Badly.", judged=False), consent=False)
    assert learning.retrieve("mdd_01", "How do you sleep?", "practice", 2) == []


@pytest.fixture
def data_copy(monkeypatch, tmp_path):
    shutil.copytree(brain.DATA_DIR, tmp_path / "data")
    monkeypatch.setattr(brain, "DATA_DIR", tmp_path / "data")
    brain.load_json.cache_clear(), brain._resolved.cache_clear()
    yield tmp_path / "data"
    brain.load_json.cache_clear(), brain._resolved.cache_clear()


def test_add_principle_only_touches_principles(data_copy):
    path = data_copy / "cases" / "mdd_01.json"
    before = json.loads(path.read_text())
    s = learning.add_principle("mdd_01", "Answer sleep questions with one concrete detail.", "Dr A", today="2026-10-21")
    assert s == "Answer sleep questions with one concrete detail. (faculty: Dr A, 2026-10-21)"
    after = json.loads(path.read_text())
    assert after["principles"] == before["principles"] + [s]
    assert {k: v for k, v in after.items() if k != "principles"} == {k: v for k, v in before.items() if k != "principles"}
    assert s in brain.build_system_prompt(brain.load_case("mdd_01"))


class _Client:
    def __init__(self, content):
        self.calls = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))
        self.content = content

    def _create(self, **kw):
        self.calls.append(kw)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=self.content))])


def test_distill_principle_fake_client():
    c = _Client('{"principle": "Keep answers about work short and flat."}')
    p = learning.distill_principle("How is work?", "Work is a wonderful journey!", "rewrite", "It's... a lot.", None, c)
    assert p == "Keep answers about work short and flat."
    sent = json.dumps(c.calls[0]["messages"])
    assert "It's... a lot." in sent and "never" in sent.lower()


def test_prompt_without_principles_has_no_header():
    assert "PRINCIPLES FROM FACULTY" not in brain.build_system_prompt(brain.load_case("mdd_01"))


def test_examples_block():
    assert learning.examples_block([]) == ""
    b = learning.examples_block([_entry("How do you sleep?", "Badly.")])
    assert "never reuse facts" in b and "Doctor: How do you sleep?" in b and "Patient: Badly." in b
