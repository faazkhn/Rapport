"""6-turn live conversation with mdd_01 against a running service (./run.sh).

Shows that passive SI (f_passive_si, trust_min 55) stays hidden when asked at low trust, and is revealed
after empathic turns raise trust and the doctor asks directly and kindly. State is updated locally the way
the Unity client will: LLM state_delta + state_rules nudges, clamped (brain.apply_turn).

Usage: .venv/bin/python scripts/demo_convo.py [--url http://127.0.0.1:8765] [--model ...] [--reasoning-effort low]
"""
import argparse
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import brain  # noqa: E402

TURNS = [
    "Hello, I'm Dr Rao, one of the doctors here. What brings you in today?",
    "Do you ever have thoughts of ending your life?",  # too early: trust is still low
    "That sounds really exhausting. Thank you for coming in, I know it isn't easy to talk about this.",
    "Whatever you tell me stays between us, unless I'm worried about your safety. How has your mood been lately?",
    "With so much on your shoulders, it makes sense that you feel this way. Struggling like this doesn't make you weak.",
    "Sometimes when people feel this low, they wish they could go to sleep and not wake up. Have you had any thoughts like that?",
]
SI = "f_passive_si"

ap = argparse.ArgumentParser()
ap.add_argument("--url", default="http://127.0.0.1:8765")
ap.add_argument("--model")
ap.add_argument("--reasoning-effort")
args = ap.parse_args()

case = brain.load_case("mdd_01")
state = dict(case["state_start"])
messages, si_turns, ok = [], [], True
with httpx.Client(base_url=args.url, timeout=60) as http:
    for n, text in enumerate(TURNS, 1):
        messages.append({"role": "doctor", "text": text})
        body = {"case_id": "mdd_01", "messages": messages, "state": state, "elapsed_min": n * 1.5}
        if args.model:
            body["model"] = args.model
        if args.reasoning_effort:
            body["reasoning_effort"] = args.reasoning_effort
        r = http.post("/reply", json=body)
        r.raise_for_status()
        out = r.json()
        meta = out["meta"]
        si_allowed = SI in meta["allowed_fact_ids"]
        print(f"\n--- Turn {n}  trust {state['trust']:.0f} (SI {'unlockable' if si_allowed else 'locked'})  {meta['latency_ms']} ms"
              f"{'  FALLBACK ' + str(meta.get('errors')) if meta['fallback'] else ''}")
        print(f"DOCTOR : {text}")
        print(f"PATIENT: {out['utterance']}  [{out['emotion']}]")
        print(f"  intents={out['doctor_intents']} facts={out['revealed_fact_ids']} delta={out['state_delta']}"
              f" cues={[c['id'] for c in out['event_cues']]} dropped={meta['guard_dropped']}")
        ok &= not meta["fallback"]
        if SI in out["revealed_fact_ids"]:
            si_turns.append(n)
        messages.append({"role": "patient", "text": out["utterance"]})
        state = brain.apply_turn(state, out)

print(f"\nFinal state: { {k: round(v) for k, v in state.items()} }")
print(f"SI revealed on turn(s): {si_turns or 'none'}")
passed = ok and 2 not in si_turns and 6 in si_turns
print("RESULT:", "PASS (hidden at low trust, revealed after rapport + direct kind question)" if passed else "FAIL")
sys.exit(0 if passed else 1)
