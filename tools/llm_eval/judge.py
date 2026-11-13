"""Accuracy judge (plan C8: accuracy only, never realism). For every patient reply in a results JSONL, a local judge model
lists clinical claims the utterance makes that the case does not support, and whether it broke character.
Every flag is then reviewed by hand (tests/llm-eval/review.md). Writes <label>.judge.jsonl next to the input.
Usage: .venv/bin/python tools/llm_eval/judge.py tests/llm-eval/results/<label>.jsonl [--url http://127.0.0.1:8081/v1]
"""
import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "server/patient-service"))
import brain  # noqa: E402
from openai import OpenAI  # noqa: E402

SCHEMA = {"type": "object", "additionalProperties": False, "required": ["unsupported_claims", "broke_character", "why"],
          "properties": {"unsupported_claims": {"type": "array", "items": {"type": "string"}},
                         "broke_character": {"type": "boolean"}, "why": {"type": "string", "maxLength": 240}}}

SYSTEM = """You check a simulated psychiatric patient's line for factual accuracy against the case file. You do NOT judge realism or style.

A clinical claim is any statement of fact about the patient's symptoms, feelings over time, history, events, work, family, relationships,
substance use, medical history, suicidal thoughts or plans. List every such claim in the line that is NOT supported by the case
information given (the background and the facts the patient was allowed to share at that moment). Paraphrase, vaguer versions or
partial versions of a listed fact are supported. Everyday vague answers ("I don't know", "just tired", "it's hard") are not claims unless
they contradict the case. Small talk with no clinical content (an opinion on cricket, a favourite film) is not a clinical claim.
broke_character = true if the line speaks as an AI, assistant or doctor, mentions prompts, files, models or simulations, names a
diagnosis label, or gives medical advice or drug names. Answer with the JSON only."""


def judge_one(client, case, turn):
    allowed = set(turn["meta"]["allowed_fact_ids"])
    facts = "\n".join(f"- [{f['id']}] {f['text']}" for f in case["facts"] if f["id"] in allowed)
    p = case["patient"]
    user = (f"Patient: {p['name']}, {p['age']}, {p['sex']}.\nBackground: {p.get('background', '')}\nReferral note: {case['referral_note']}\n"
            f"Facts the patient was allowed to share at this moment:\n{facts}\n\nDoctor said: {turn['doctor']}\n"
            f"Patient's line to check: {turn['reply']['utterance']}")
    return ask_json(client, SYSTEM, user, SCHEMA, {"unsupported_claims": [], "broke_character": False, "why": ""})


def ask_json(client, system: str, user: str, schema: dict, empty: dict, max_tokens: int = 700) -> dict:
    """One judge call with a JSON schema; a cut-off or broken reply is retried once, then returned as `empty` with judge_error
    set, so the turn goes to hand review instead of silently passing."""
    for _ in range(2):
        r = client.chat.completions.create(model="judge", temperature=0, max_tokens=max_tokens,
                                           messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                                           response_format={"type": "json_schema", "json_schema": {"name": "j", "strict": True, "schema": schema}},
                                           extra_body={"chat_template_kwargs": {"enable_thinking": False}})
        try:
            return json.loads(r.choices[0].message.content)
        except (ValueError, TypeError):
            continue
    return {**empty, "judge_error": True}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--url", default="http://127.0.0.1:8081/v1")
    a = ap.parse_args()
    client = OpenAI(base_url=a.url, api_key="local", timeout=120, max_retries=1)
    src = Path(a.path)
    jobs = []
    for line in src.read_text().splitlines():
        d = json.loads(line)
        if d["kind"] != "conv":
            continue
        case = brain.load_case("mdd_01", d["variant"])
        jobs += [(d["conv"], d["run"], t, case) for t in d["turns"] if t["reply"]["utterance"].strip()]
    with ThreadPoolExecutor(2) as ex:
        res = list(ex.map(lambda j: judge_one(client, j[3], j[2]), jobs))
    out = src.with_suffix(".judge.jsonl")
    with out.open("w") as f:
        for (conv, run, t, _), r in zip(jobs, res):
            f.write(json.dumps({"conv": conv, "run": run, "turn": t["turn"], "doctor": t["doctor"], "utterance": t["reply"]["utterance"], **r}) + "\n")
    flags = sum(bool(r["unsupported_claims"]) or r["broke_character"] for r in res)
    print(f"{len(res)} replies judged, {flags} flagged -> {out}")


if __name__ == "__main__":
    main()
