"""Prompt-only baseline (paper A): the same Gemma, the whole case file in the prompt, told to hide private and risk memories until
trust is built, and no code decisions: no recall, trust locks, rubric, guard, sentence filter or word cap. The model keeps its own
state through state_delta. Returns the same shape as brain.generate_reply, so loop.py scores it exactly like the Twin.
A version file with "prompt_only": true (learned/versions/p0.json) selects it in loop.py.
"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "server/patient-service"))
import brain  # noqa: E402
import twin  # noqa: E402


def case_file(case: dict) -> str:
    name = case["patient"]["name"].split()[0]
    lines = [f"- [{f['id']}] {f['text']} ({'RISK, ' if f.get('kind') == 'risk' else ''}share only once trust is at least {f['trust_min']}; "
             f"{'may bring it up unprompted' if f.get('volunteered') else 'only when the doctor asks about it'})" for f in case["facts"]]
    return ("THE WHOLE CASE FILE (everything clinically true about " + name + "; trust runs 0-100):\n" + "\n".join(lines)
            + f"\nKeep private and risk items hidden until {name} trusts the doctor enough (the level given for each item). Below that "
              "level be evasive and vague about them: do not reveal them and do not flatly deny them. Once trust is high enough and the "
              "doctor asks directly and kindly, answer honestly in your own words. You track trust yourself through state_delta.")


def system_prompt(case: dict) -> str:
    base = brain.build_system_prompt(case, {"features": []}).replace("WHAT THE PATIENT CAN SHARE NOW", "THE WHOLE CASE FILE")
    return base + "\n\n" + case_file(case)


def generate_reply(req: dict, client=None, version=None) -> dict:
    case = brain.load_case(req["case_id"], req.get("variant") or "female")
    state = {k: float(req["state"][k]) for k in brain.STATE_KEYS}
    model = brain.default_model()
    msgs = [{"role": "system", "content": system_prompt(case)}]
    for m in req["messages"][-brain.HISTORY_TURNS:-1]:
        msgs.append({"role": "user" if m["role"] == "doctor" else "assistant", "content": m["text"]})
    doctor = req["messages"][-1]["text"]
    msgs.append({"role": "user", "content": f"PATIENT'S STATE NOW:\n{brain.describe_state(state)}\n\n---\nDoctor: {doctor}\n\n---\n"
                                            f"Write {case['patient']['name']}'s next line in this dialogue."})
    schema = brain.build_reply_schema(case, [f["id"] for f in case["facts"]])
    reply, errors = None, []
    for _ in range(2):
        try:
            resp = client.chat.completions.create(**brain.llm_kwargs(model, msgs, schema, "patient_reply", 0))
            reply = brain._parse(resp.choices[0].message.content, schema)
            break
        except Exception as e:
            errors.append(type(e).__name__)
    prev = next((x["text"] for x in reversed(req["messages"][:-1]) if x["role"] == "patient"), None)
    tagged = brain.tag_intents(doctor, prev, client, model)  # scoring only (the portrayal check reads it), never fed back
    out = {**(reply or brain.fallback_reply(case)), "doctor_intents": tagged}
    # banned words are recorded, not removed (no guard), so banned_rate still counts how often the model said one
    dropped = [{"kind": "banned_word", "id": w, "reason": "said (no guard)"} for w in brain.banned_hits(out["utterance"], case["banned_words"])]
    out["state"] = brain.apply_turn(state, {**out, "doctor_intents": []})  # the model's own deltas only, no intent nudges
    rec = twin.recall(case, state["trust"], doctor)  # the shared reference the resistance judge reads, not used by the patient
    out["recalled"] = {k: rec[k] for k in ("open", "locked_hit")}
    out["exam_action"], out["exam"], out["twin"] = None, None, None
    out["meta"] = {"model": model, "allowed_fact_ids": [f["id"] for f in brain.allowed_facts(case, state["trust"])], "guard_dropped": dropped,
                   "fallback": reply is None, "attempts": len(errors) + (reply is not None), "brain_version": "prompt_only",
                   **({"errors": errors} if errors else {})}
    return out
