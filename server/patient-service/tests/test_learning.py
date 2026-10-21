"""Phase E learning: versions, gate, experience library, principles. No models loaded."""
import shutil

import pytest

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
