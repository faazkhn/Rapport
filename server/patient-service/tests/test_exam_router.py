"""Exam action router: rules on the doctor's words, no models."""
import sys

import exam_router
from brain import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT / "tools"))
import exam_router_eval  # noqa: E402


def ids(text):
    return [a["id"] for a in exam_router.route(text)["actions"]]


def test_hands_with_slots():
    assert exam_router.route("Kindly hold out both your hands, palms down")["actions"] == [
        {"id": "hold_out_hands", "slots": {"which": "both", "palms": "down"}}]


def test_singular_hand_asks_back():
    r = exam_router.route("Hold out your hand")
    assert r["ask_back"] == "Which hand?" and r["actions"] == []


def test_several_commands_in_order():
    assert ids("Stand up and walk a few steps for me") == ["stand_up", "walk_few_steps"]


def test_history_questions_are_not_commands():
    for q in ("Do your hands shake?", "Have you had trouble standing up?"):
        r = exam_router.route(q)
        assert r["actions"] == [] and not r["relax"]


def test_relax():
    assert exam_router.route("Okay, you can relax now")["relax"] is True


def test_tongue():
    assert ids("Show me your tongue") == ["stick_out_tongue"]


def test_eval_set_meets_gate():
    r = exam_router_eval.evaluate(REPO_ROOT / "tests/exam-router/utterances.yaml")
    assert r["n"] >= 300 and r["negatives"] >= 20
    assert r["accuracy"] >= 0.95, r["misses"][:10]
    assert r["false_trigger_rate"] <= 0.01 and r["max_ms"] <= 30
