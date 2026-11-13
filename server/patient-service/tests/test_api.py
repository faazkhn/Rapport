import os
import struct

import pytest
from fastapi.testclient import TestClient

import app as service

STATE = {"trust": 30, "distress": 55, "agitation": 15, "engagement": 35}


def test_health_and_bad_requests():
    c = TestClient(service.app, client=("127.0.0.1", 50000))  # no context manager: lifespan (TTS load) is skipped
    assert c.get("/health").json()["ok"] is True
    assert c.post("/reply", json={"case_id": "nope", "messages": [{"role": "doctor", "text": "hi"}], "state": STATE}).status_code == 404
    assert c.post("/reply", json={"case_id": "../cases/mdd_01", "messages": [{"role": "doctor", "text": "hi"}], "state": STATE}).status_code == 404
    assert c.post("/reply", json={"case_id": "mdd_01", "messages": [], "state": STATE}).status_code == 422


@pytest.fixture(scope="module")
def tts_client():
    with TestClient(service.app, client=("127.0.0.1", 50000)) as c:
        if not c.get("/health").json()["tts_loaded"]:
            pytest.skip("KittenTTS model could not load")
        yield c


@pytest.mark.tts
def test_tts_returns_wav(tts_client):
    r = tts_client.post("/tts", json={"text": "I don't know, doctor. I'm just tired.", "voice": "Bella", "speed": 0.9})
    assert r.status_code == 200 and r.headers["content-type"] == "audio/wav"
    b = r.content
    assert b[:4] == b"RIFF" and b[8:12] == b"WAVE"
    channels, rate = struct.unpack("<HI", b[22:28])
    bits = struct.unpack("<H", b[34:36])[0]
    assert (channels, rate, bits) == (1, 24000, 16)
    assert len(b) > 44 + 24000  # more than half a second of 16-bit audio
    assert tts_client.post("/tts", json={"text": "hi", "voice": "Siri"}).status_code == 422


@pytest.mark.live
def test_live_reply_greeting():
    c = TestClient(service.app, client=("127.0.0.1", 50000))
    r = c.post("/reply", json={"case_id": "mdd_01", "messages": [{"role": "doctor", "text": "Hello, I'm Dr Rao. What brings you in today?"}], "state": STATE})
    out = r.json()
    assert r.status_code == 200
    assert out["meta"]["fallback"] is False, out["meta"]
    assert out["utterance"].strip()
    assert set(out["revealed_fact_ids"]) <= set(out["meta"]["allowed_fact_ids"])
    assert "f_passive_si" not in out["revealed_fact_ids"]
    assert "greet_introduce" in out["doctor_intents"]


def test_twin_ws_replays_history():
    import twin_bus
    twin_bus.publish({"type": "init", "t": 0.0})
    twin_bus.publish({"type": "doctor_end", "turn": 1, "t": 1.0})
    c = TestClient(service.app, client=("127.0.0.1", 50000))
    with c.websocket_connect("/twin/ws") as ws:
        assert ws.receive_json()["type"] == "init"
        assert ws.receive_json() == {"type": "doctor_end", "turn": 1, "t": 1.0}


def test_feedback_endpoint(monkeypatch, tmp_path):
    import shutil

    import brain
    import learning
    shutil.copytree(learning.DIR, tmp_path / "learned", ignore=shutil.ignore_patterns("experience"))  # tests start with an empty library
    shutil.copytree(brain.DATA_DIR, tmp_path / "data")
    monkeypatch.setattr(learning, "DIR", tmp_path / "learned")
    monkeypatch.setattr(brain, "DATA_DIR", tmp_path / "data")
    brain.load_json.cache_clear(), brain._resolved.cache_clear()
    monkeypatch.setattr(learning, "distill_principle", lambda *a, **k: "Keep it short.")
    c = TestClient(service.app, client=("127.0.0.1", 50000))
    body = {"case_id": "mdd_01", "doctor": "How do you sleep?", "utterance": "Badly.", "rating": "up", "author": "Dr A"}
    r = c.post("/learning/feedback", json=body).json()
    assert r["principle"].startswith("Keep it short. (faculty: Dr A, ")
    [e] = learning.library("mdd_01")
    assert e["id"] == r["entry_id"] and e["tier"] == "approved" and e["judged"] is True and e["source"] == "faculty"
    assert r["principle"] in brain.load_case("mdd_01")["principles"]
    r2 = c.post("/learning/feedback", json={**body, "rating": "down"}).json()
    assert r2.get("entry_id") is None and len(learning.library("mdd_01")) == 1
    assert c.post("/learning/feedback", json={**body, "rating": "meh"}).status_code == 422
    assert c.post("/learning/feedback", json={**body, "case_id": "../x"}).status_code == 404
    assert c.post("/learning/approve", json={"case_id": "mdd_01", "entry_id": "nope"}).status_code == 404
    brain.load_json.cache_clear(), brain._resolved.cache_clear()
    learning._cache.clear()


def test_patient_endpoint_previews_a_seeded_patient():
    c = TestClient(service.app, client=("127.0.0.1", 50000))
    a = c.get("/patient", params={"case_id": "mdd_01", "variant": "male", "seed": 11}).json()
    assert a == c.get("/patient", params={"case_id": "mdd_01", "variant": "male", "seed": 11}).json()
    assert a["name"] == "Arjun Rao" and set(a["slots"]) == {"hobby", "hobby_short", "sibling", "hometown"}
    base = c.get("/patient", params={"case_id": "mdd_01"}).json()
    assert base["slots"] == {} and base["style"] == "plain"
    assert c.get("/patient", params={"case_id": "mdd_01", "seed": 11, "mode": "assessment"}).json()["style"] == "plain"
    assert c.get("/patient", params={"case_id": "nope"}).status_code == 404
    assert c.get("/patient", params={"case_id": "mdd_01", "seed": -1}).status_code == 422


def test_network_clients_see_only_the_twin():
    lan = TestClient(service.app, client=("192.168.1.20", 50000))
    assert lan.get("/twin/").status_code == 200
    assert lan.get("/health").status_code == 200
    assert lan.post("/reply", json={"case_id": "nope", "messages": [{"role": "doctor", "text": "hi"}], "state": STATE}).status_code == 403
    assert lan.get("/patient?case_id=mdd_01").status_code == 403
    with pytest.raises(Exception):
        with lan.websocket_connect("/session"):
            pass
