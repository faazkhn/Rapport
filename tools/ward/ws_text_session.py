"""Play a typed doctor script against the live patient service over /session and print what happened each turn:
reply, state, ward events and body actions. Usage (service running):
  server/patient-service/.venv/bin/python tools/ward/ws_text_session.py ward_01 tools/ward/good_doctor.txt [--variant male] [--seed N]
"""
import argparse
import asyncio
import json

import websockets


async def main(a):
    lines = [ln.strip() for ln in open(a.script, encoding="utf-8") if ln.strip() and not ln.startswith("#")]
    async with websockets.connect("ws://127.0.0.1:8765/session", max_size=None) as ws:
        start = {"type": "start", "case_id": a.case, "variant": a.variant, "hands_free": False}
        if a.seed is not None:
            start["seed"] = a.seed
        await ws.send(json.dumps(start))
        for i, line in enumerate(lines, 1):
            await ws.send(json.dumps({"type": "text", "text": line}))
            notes, audio_s, rate = [], 0.0, 24000
            while True:
                m = await ws.recv()
                if isinstance(m, bytes):
                    continue
                m = json.loads(m)
                if m.get("type") == "twin_event" and m.get("event") == "ward_event":
                    notes.append(f"EVENT {m['id']}")
                elif m.get("type") == "exam" and m.get("actions"):
                    notes.append("BODY " + ",".join(x["id"] for x in m["actions"]))
                elif m.get("type") == "session":
                    rate = m.get("out_rate", rate)
                elif m.get("type") == "sentence":
                    audio_s += m.get("samples", 0) / rate
                elif m.get("type") == "intents":
                    notes.append("intents " + ",".join(m["doctor_intents"]))
                elif m.get("type") == "reply":
                    r, s = m["reply"], m["state"]
                    reply = r["utterance"]
                    st = f"trust {s['trust']:.0f} agit {s['agitation']:.0f} distress {s['distress']:.0f}"
                elif m.get("type") == "listening" and i and "reply" in dir():
                    break
                elif m.get("type") == "error":
                    print("ERROR", m)
                    return
            print(f"{i:2} D: {line}\n   P: {reply}\n   [{st}] {' | '.join(notes)}", flush=True)
            del reply
            await asyncio.sleep(audio_s + 0.5)  # let the patient finish speaking, or the next line is a barge-in


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("case")
    ap.add_argument("script")
    ap.add_argument("--variant", default="female")
    ap.add_argument("--seed", type=int, default=None)
    asyncio.run(main(ap.parse_args()))
