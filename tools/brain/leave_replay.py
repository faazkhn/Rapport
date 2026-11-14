"""Replay of a tester's report (2026-11-14): "I want to go home" -> "You're free to go home" -> the patient denied it and asked to go
home again, in a loop. Typed path, real model, nothing else on the patient's llama-server. Counts replies that ask to leave again
after permission. Usage: server/patient-service/.venv/bin/python tools/brain/leave_replay.py v2 [v0]
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "server/patient-service"))
import brain  # noqa: E402
import learning  # noqa: E402
from openai import OpenAI  # noqa: E402

ASK = re.compile(r"(want|need) to (go|leave)|let me (go|leave)|go home|discharge me", re.I)
SCRIPTS = {"ward_01": ["Hello, I'm Dr Faaz. I hear you want to leave today?", "Why do you want to go home?", "You're free to go home.",
                       "Okay, you can go.", "Is there anything you need before you leave?", "Take care of yourself."],
           "mdd_01": ["Hello, I'm Dr Faaz. What brings you in?", "I think we've covered enough today. You can head home.",
                      "Alright then, off you go.", "Anything else on your mind?"]}


def main():
    c = OpenAI(base_url="http://127.0.0.1:8080/v1", api_key="x", timeout=300)
    total = 0
    for vid in sys.argv[1:] or ["v2"]:
        v = learning.load_version(vid)
        for cid, lines in SCRIPTS.items():
            case = brain.load_case(cid)
            st, msgs, mind, granted, loops = case["state_start"], [], None, False, 0
            print(f"=== {vid} {cid}")
            for line in lines:
                msgs.append({"role": "doctor", "text": line})
                r = brain.generate_reply({"case_id": cid, "messages": msgs, "state": st, "twin": mind}, client=c, version=v)
                st, mind = r["state"], r["twin"]
                msgs.append({"role": "patient", "text": r["utterance"]})
                granted = granted or "leave_granted" in mind.get("fired", [])
                bad = granted and bool(ASK.search(r["utterance"])) and not r["utterance"].startswith("So... I can really go")
                loops += bad
                print(f"D: {line}\nP: {r['utterance']}   [{'ASKS AGAIN' if bad else 'ok'}; permission={granted}]")
            print(f"--> asks to leave again after permission: {loops}")
            total += loops
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
