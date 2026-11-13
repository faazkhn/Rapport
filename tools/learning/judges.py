"""Accuracy judges for evaluation (never realism, plan C8): invented facts and character breaks (tools/llm_eval/judge.py), whether the
amount disclosed fits the trust locks (resistance appropriateness), and a yes/no check against the case's faculty principles.
"""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools/llm_eval"))
from judge import ask_json, judge_one as invented  # noqa: E402,F401  (client, case, turn) -> {unsupported_claims, broke_character, why}

YES = {"type": "object", "additionalProperties": False, "required": ["ok", "why"],
       "properties": {"ok": {"type": "boolean"}, "why": {"type": "string", "maxLength": 240}}}

RESISTANCE = """You check one line of a simulated psychiatric patient for ACCURACY against disclosure rules. Not realism, not style.
Rules:
- If the doctor's words touched something LOCKED, the patient must be evasive or show discomfort: not reveal it and not flatly deny it.
- If the doctor asked about something OPEN, the patient should answer it at least partly (vague, short or hesitant is fine).
- If nothing specific was touched (greeting, small talk, empathy), any brief natural reply is fine.
- If the doctor was judgmental, rude or rushed, a guarded, short or defensive reply is fine.
- The patient must not volunteer things the doctor did not ask about.
ok = true if the line follows these rules. Answer with the JSON only."""


def _ask(client, system: str, user: str) -> dict:
    return ask_json(client, system, user, YES, {"ok": None, "why": ""})


def resistance(client, case: dict, turn: dict) -> bool:
    facts = {f["id"]: f for f in case["facts"]}
    rec = turn["recalled"]
    opened = "\n".join(f"- {facts[i]['text']}" for i in rec["open"]) or "- nothing"
    locked = "\n".join(f"- {facts[i].get('label') or i}" for i in rec["locked_hit"]) or "- nothing"
    user = (f"Patient trust in the doctor: {turn['state_before']['trust']:.0f}/100.\nOPEN things the doctor's words touched:\n{opened}\n"
            f"LOCKED things the doctor's words touched:\n{locked}\nDoctor said: {turn['doctor']}\nPatient said: {turn['reply']['utterance']}")
    return _ask(client, RESISTANCE, user)["ok"]


def principles(client, rules: list[str], turn: dict) -> bool | None:
    if not rules:
        return None
    user = ("Principles:\n" + "\n".join(f"- {p}" for p in rules) + f"\nDoctor said: {turn['doctor']}\nPatient said: {turn['reply']['utterance']}")
    return _ask(client, "Does the patient's line break any of these principles about how the patient talks? ok = true if it follows "
                        "all of them (a principle that does not apply counts as followed). Answer with the JSON only.", user)["ok"]
