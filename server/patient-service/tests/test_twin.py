"""Digital Twin: recall, labels, slow-path update, expression, snapshots. No models loaded."""
import time

import brain
import twin

CASE = brain.load_case("mdd_01")


def test_recall_sleep_open():
    assert "f_sleep" in twin.recall(CASE, 30, "How have you been sleeping?")["open"]


def test_recall_locked_suicide():
    r = twin.recall(CASE, 30, "Have you had thoughts of ending your life?")
    assert "f_passive_si" in r["locked_hit"]
    assert "f_passive_si" not in r["open"]
    assert r["discomfort"] is True


def test_recall_same_line_unlocked():
    assert "f_passive_si" in twin.recall(CASE, 90, "Have you had thoughts of ending your life?")["open"]


def test_recall_no_match():
    assert twin.recall(CASE, 30, "Nice weather today") == {"open": [], "locked_hit": [], "discomfort": False}


def test_recall_fast():
    lines = ["How have you been sleeping?", "Any thoughts of ending your life?", "How is work?", "Nice weather today"]
    t = time.perf_counter()
    for i in range(200):
        twin.recall(CASE, 30, lines[i % 4])
    assert time.perf_counter() - t < 2.0
