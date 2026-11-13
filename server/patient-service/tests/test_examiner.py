import json
from types import SimpleNamespace

import brain
import examiner

TURNS = [{"doctor": "Hello, I'm Dr. Faaz. What brings you in today?", "patient": "Just tired."},
         {"doctor": "Any suicidal ideation? Plans?", "patient": "What?"}]


def test_grounded_keeps_only_real_quotes():
    notes = [{"item": "opening", "quote": "Hello, I'm Dr. Faaz.", "comment": "Clear start."},
             {"item": "plain_language", "quote": "any suicidal ideation", "comment": "Jargon."},
             {"item": "empathy", "quote": "That sounds so hard for you", "comment": "invented"},
             {"item": "made_up_item", "quote": "What brings you in today?", "comment": "bad item"}]
    kept = examiner.grounded(notes, TURNS)
    assert [n["item"] for n in kept] == ["opening", "plain_language"]


def test_assess_drops_ungrounded_and_uses_temperature_zero():
    calls = []

    class Client:
        class chat:
            class completions:
                @staticmethod
                def create(**kw):
                    calls.append(kw)
                    body = {"strengths": [{"item": "opening", "quote": "What brings you in today?", "comment": "Open start."}],
                            "improvements": [{"item": "one_question", "quote": "Tell me everything now", "comment": "invented"}]}
                    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(body)))])

    out = examiner.assess(brain.load_case("alc_01", "male"), TURNS, client=Client, model="local")
    assert len(out["strengths"]) == 1 and out["improvements"] == [] and out["dropped_ungrounded"] == 1
    assert calls[0]["temperature"] == 0 and calls[0]["response_format"]["json_schema"]["name"] == "examiner_notes"
