import os
import struct

import pytest
from fastapi.testclient import TestClient

import app as service

STATE = {"trust": 30, "distress": 55, "agitation": 15, "engagement": 35}


def test_health_and_bad_requests():
    c = TestClient(service.app)  # no context manager: lifespan (TTS load) is skipped
    assert c.get("/health").json()["ok"] is True
    assert c.post("/reply", json={"case_id": "nope", "messages": [{"role": "doctor", "text": "hi"}], "state": STATE}).status_code == 404
    assert c.post("/reply", json={"case_id": "../cases/mdd_01", "messages": [{"role": "doctor", "text": "hi"}], "state": STATE}).status_code == 404
    assert c.post("/reply", json={"case_id": "mdd_01", "messages": [], "state": STATE}).status_code == 422


@pytest.fixture(scope="module")
def tts_client():
    with TestClient(service.app) as c:
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
    c = TestClient(service.app)
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
    c = TestClient(service.app)
    with c.websocket_connect("/twin/ws") as ws:
        assert ws.receive_json()["type"] == "init"
        assert ws.receive_json() == {"type": "doctor_end", "turn": 1, "t": 1.0}
