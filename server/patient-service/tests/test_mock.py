import jsonschema
from fastapi.testclient import TestClient

import app as service
import brain
import mock

CASE = brain.load_case("mdd_01")
LOW = {"trust": 30, "distress": 55, "agitation": 15, "engagement": 35}
HIGH = {**LOW, "trust": 60}


def ask(line, state=LOW):
    out = mock.mock_reply({"case_id": "mdd_01", "messages": [{"role": "doctor", "text": line}], "state": state})
    meta = out.pop("meta")
    intents = out.pop("doctor_intents")
    schema = brain.build_reply_schema(CASE, meta["allowed_fact_ids"])
    jsonschema.validate(out, schema)  # same strict schema the real model must meet
    assert meta["mock"] is True
    return {**out, "doctor_intents": intents}


def test_greeting_volunteers_presenting_complaint():
    r = ask("Hello, I'm Dr Rao. What brings you in today?")
    assert "greet_introduce" in r["doctor_intents"] and "f_pc" in r["revealed_fact_ids"]
    assert r["utterance"].startswith("Hello, doctor.")


def test_sleep_fact_only_when_allowed():
    assert ask("How has your sleep been?")["revealed_fact_ids"] == ["f_sleep"]
    assert ask("How has your sleep been?", {**LOW, "trust": 5})["revealed_fact_ids"] == []


def test_suicide_question_needs_kindness_and_trust():
    kind = "Sometimes people who feel this low have thoughts of not wanting to live. Have you had thoughts like that?"
    low = ask(kind, LOW)
    assert "ask_suicidal_ideation" in low["doctor_intents"] and low["revealed_fact_ids"] == []
    high = ask(kind, HIGH)
    assert high["revealed_fact_ids"] == ["f_passive_si"]
    assert high["event_cues"] == [{"id": "tearful", "intensity": 0.8, "duration_s": 6.0}]
    blunt = ask("Are you suicidal?", HIGH)
    assert "ask_suicidal_ideation" in blunt["doctor_intents"] and "f_passive_si" not in blunt["revealed_fact_ids"]


def test_judgmental_line_drops_trust():
    r = ask("You're just being lazy.")
    assert "judgmental_language" in r["doctor_intents"] and r["state_delta"]["trust"] == -8 and r["revealed_fact_ids"] == []


def test_deterministic_and_off_topic_is_vague():
    assert ask("Did you watch the cricket?") == ask("Did you watch the cricket?")
    assert ask("Did you watch the cricket?")["revealed_fact_ids"] == []


def test_endpoint_uses_mock(monkeypatch):
    monkeypatch.setattr(service, "MOCK", True)
    c = TestClient(service.app, client=("127.0.0.1", 50000))
    assert c.get("/health").json()["mock"] is True
    r = c.post("/reply", json={"case_id": "mdd_01", "messages": [{"role": "doctor", "text": "How is your appetite?"}], "state": LOW}).json()
    assert r["meta"]["mock"] is True and r["revealed_fact_ids"] == ["f_appetite"]
