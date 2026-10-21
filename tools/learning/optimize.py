"""L3: GEPA (gepa-ai/gepa, MIT) evolves the realism-rules text of the patient prompt, reflecting with the local model on why self-play
replies failed the automatic checks. HARD_RULES, facts and the answer key are not components and never change.
"""
import sys
from pathlib import Path

import gepa
from gepa import EvaluationBatch

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "server/patient-service"))
import brain  # noqa: E402
import learning  # noqa: E402

MAX_CHARS = 2000
WHY = {"too_long": "too long for how little energy the patient has", "repeats": "repeats words from an earlier reply",
       "robotic": "sounds like an assistant or uses clinical jargon", "break_character": "broke character",
       "banned_word": "used a banned clinical word", "fact_dropped": "claimed a fact it may not share yet",
       "fallback": "invalid output", "empty": "said nothing",
       "did_not_answer": "the doctor asked about something the patient can share, but the reply did not answer it",
       "volunteered": "brought up something the doctor did not ask about"}
GUARD = ("Constraints for the new instruction: it is only about HOW the patient talks (tone, length, wording, hesitation, what to hold "
         "back). Never add clinical facts, symptoms, history, names or events. Keep it under 1500 characters.\n\n")


def check(ctx: dict, out: dict, case: dict) -> list[str]:
    history = [m["text"] for m in ctx["messages"] if m["role"] == "patient"]
    reasons = learning.gate(out["utterance"], out["meta"], case, ctx["state"], history)
    opened, said = set(ctx["recalled"]["open"]), set(out["revealed_fact_ids"])
    volunteered = {f["id"] for f in case["facts"] if f.get("volunteered")}
    if opened and not said & opened:
        reasons.append("did_not_answer")
    if said - opened - volunteered:
        reasons.append("volunteered")
    return reasons


class RulesAdapter:
    propose_new_texts = None  # GEPA's default reflective proposer

    def __init__(self, base: dict, client, case_id: str = "mdd_01"):
        self.base, self.client, self.case_id = base, client, case_id

    def evaluate(self, batch, candidate, capture_traces=False):
        outs, scores, traces = [], [], []
        rules = candidate["realism_rules"]
        for ctx in batch:
            case = brain.load_case(self.case_id, ctx["variant"])
            if len(rules) > MAX_CHARS:
                out, reasons = {"utterance": ""}, ["rules longer than 2000 characters"]
            else:
                out = brain.generate_reply({"case_id": self.case_id, "variant": ctx["variant"], "messages": ctx["messages"],
                                            "state": ctx["state"]}, client=self.client, version={**self.base, "realism_rules": rules})
                reasons = [WHY.get(r, r) for r in check(ctx, out, case)]
            outs.append(out["utterance"])
            scores.append(max(0.0, 1 - 0.34 * len(reasons)))
            traces.append({"doctor": ctx["messages"][-1]["text"], "state": brain.describe_state(ctx["state"]),
                           "utterance": out["utterance"], "reasons": reasons})
        return EvaluationBatch(outputs=outs, scores=scores, trajectories=traces if capture_traces else None)

    def make_reflective_dataset(self, candidate, eval_batch, components_to_update):
        return {c: [{"Inputs": {"doctor_line": t["doctor"], "patient_state": t["state"]}, "Generated Outputs": t["utterance"],
                     "Feedback": ("Problems: " + "; ".join(t["reasons"])) if t["reasons"] else "Good: passed every check."}
                    for t in eval_batch.trajectories] for c in components_to_update}


def reflection_lm(client):
    def call(prompt: str) -> str:
        r = client.chat.completions.create(model="local", temperature=0.7, max_tokens=1200, messages=[{"role": "user", "content": GUARD + prompt}],
                                           extra_body={"id_slot": 1, "chat_template_kwargs": {"enable_thinking": False}})
        return r.choices[0].message.content or ""
    return call


def propose(base: dict, contexts: list[dict], client, budget: int, seed: int = 0) -> tuple[str, dict]:
    """GEPA over `realism_rules`, seeded with the base version's text. Returns (best text, info)."""
    seed_text = base.get("realism_rules") or brain.REALISM_RULES
    val, train = contexts[:6], contexts[6:] or contexts
    res = gepa.optimize(seed_candidate={"realism_rules": seed_text}, trainset=train, valset=val, adapter=RulesAdapter(base, client),
                        reflection_lm=reflection_lm(client), max_metric_calls=budget, reflection_minibatch_size=3, seed=seed,
                        raise_on_exception=False, display_progress_bar=False)
    best = res.best_candidate["realism_rules"]
    return best, {"gepa_candidates": len(res.candidates), "gepa_val_scores": [round(s, 3) for s in res.val_aggregate_scores],
                  "changed": best != seed_text}
