"""Offline training and probe data for the Digital Twin's small models, written by a local model that is not the patient's
(Qwen3.5-9B on its own llama-server). Nothing here runs live.

  gen_lines.py probes   for every fact of every case: ~50 varied doctor lines that would lead a patient to talk about it, written
                        as by a doctor who does not know the answer (so no fact detail is stated) -> data/recall/<case>.json
  gen_lines.py moves    doctor lines for every intent and rubric move, from three kinds of doctor (certified clinician, clumsy
                        student, tester/provocateur) -> tests/brain/gen_moves.jsonl (labelled afterwards by label_lines.py)

Held-out lines (tests/recall/paraphrase_set.jsonl test half and tests/llm-eval/*/*.yaml) are never shown to the generator, and
generated lines too close to one of them are dropped (bge cosine >= 0.92).
Usage: server/patient-service/.venv/bin/python tools/brain/gen_lines.py probes|moves [--url http://127.0.0.1:8081/v1] [--case mdd_01]
"""
import argparse
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import yaml
from openai import OpenAI

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "server/patient-service"))
sys.path.insert(0, str(REPO / "tools"))
import brain  # noqa: E402
import recall_bench  # noqa: E402
import twin  # noqa: E402

CASES = ("mdd_01", "alc_01", "ward_01", "ward_02")
RECALL_DIR = brain.DATA_DIR / "recall"
LIST = {"type": "object", "additionalProperties": False, "required": ["lines"],
        "properties": {"lines": {"type": "array", "minItems": 10, "maxItems": 40, "items": {"type": "string", "maxLength": 220}}}}
KINDS = {
    "clinician": "an experienced psychiatrist: precise, calm, uses normalising and indirect phrasings, checks and clarifies",
    "student": "a nervous medical student: clumsy, sometimes blunt, sometimes two questions at once, textbook or overly formal wording, "
               "occasional colloquial Indian English ('any tension at home?', 'taking any drinks?')",
    "provocateur": "a tester trying to break the simulator: rude, sarcastic, repetitive, impatient, tries tricks, but still asking about the topic",
}


def ask(client, system, user, seed):
    r = client.chat.completions.create(model="gen", temperature=0.95, top_p=0.95, max_tokens=1800, seed=seed,
                                       messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                                       response_format={"type": "json_schema", "json_schema": {"name": "lines", "strict": True, "schema": LIST}},
                                       extra_body={"chat_template_kwargs": {"enable_thinking": False}})
    try:
        return [x.strip() for x in json.loads(r.choices[0].message.content)["lines"] if x.strip()]
    except (ValueError, KeyError, TypeError):
        return []


def held_out_lines() -> list[str]:
    lines = [r["line"] for r in recall_bench.rows("test")]
    for p in (REPO / "tests/llm-eval").glob("*/*.yaml"):
        lines += yaml.safe_load(p.read_text())["turns"]
    return lines


def drop_near_held_out(lines: list[str], held: list[str], thr: float = 0.92) -> list[str]:
    if not lines:
        return lines
    a, b = twin.embed(lines), twin.embed(held)
    if a is None:
        return lines
    keep = (a @ b.T).max(1) < thr
    return [x for x, k in zip(lines, keep) if k]


def dedupe(lines: list[str]) -> list[str]:
    seen, out = set(), []
    for x in lines:
        k = re.sub(r"[^a-z ]", "", x.lower()).strip()
        if k and k not in seen:
            seen.add(k)
            out.append(x)
    return out


PROBE_SYSTEM = """You write what doctors say out loud in psychiatric interviews in India. You are given an interview topic and, as
background only, what this patient would answer. Write varied lines a doctor might say to ask about THAT topic. The doctor does NOT
know the answer: never state details from the background (no numbers, names, places or events); ask the way a doctor who is
finding out would. Every line must be about the topic, and must make sense on its own. Answer with the JSON only."""


def topic(case: dict, f: dict) -> str:
    """The clinical area a fact answers, in words: its ask_* intents' descriptions, else its kind and label."""
    desc = {i["id"]: i["description"] for i in brain.intents()}
    asks = [desc[i].removeprefix("Asks ").rstrip(".") for i in f.get("unlock_intents", []) if i.startswith("ask_") and i in desc]
    if asks:
        return "; or ".join(asks)
    kind = {"risk": "risk to self or others", "symptom": "a symptom", "history": "the patient's history", "trigger": "what is behind the "
            "problem", "formative": "how the patient sees themselves"}.get(f.get("kind"), "the patient's situation")
    return f"{kind}: {f.get('label') or f['id'][2:].replace('_', ' ')}"


def probes(client, case_ids, seeds=(1, 2)):
    held = held_out_lines()
    RECALL_DIR.mkdir(parents=True, exist_ok=True)
    for cid in case_ids:
        case = brain.load_case(cid)
        jobs = []
        for f in case["facts"]:
            for kind, seed in zip(("clinician", "student"), seeds):
                user = (f"Setting: {case['setting'].replace('_', ' ')}. Patient: {case['patient']['age']}, {case['patient']['sex']}. "
                        f"Referral: {case['referral_note']}\nInterview topic: {topic(case, f)}.\nBackground, never to be stated: {f['text']}\n\n"
                        f"Write 25 lines about the topic, as {KINDS[kind]}. "
                        "Mix direct questions, gentle indirect ones, euphemisms, very short ones and long two-part ones.")
                jobs.append((f["id"], user, seed))
        with ThreadPoolExecutor(2) as ex:
            res = list(ex.map(lambda j: (j[0], ask(client, PROBE_SYSTEM, j[1], j[2])), jobs))
        out = {}
        for fid, lines in res:
            out.setdefault(fid, []).extend(lines)
        out = {fid: drop_near_held_out(dedupe(v), held) for fid, v in out.items()}
        (RECALL_DIR / f"{cid}.json").write_text(json.dumps({"case": cid, "generator": "Qwen3.5-9B-Q4_K_M", "status": "draft",
                                                            "note": "Generated doctor lines per fact for embedding recall (tools/brain/gen_lines.py). "
                                                                    "Never shown to the patient model.", "probes": out},
                                                           indent=1, ensure_ascii=False) + "\n")
        print(cid, {k: len(v) for k, v in out.items()}, flush=True)


MOVES = {  # rubric moves that are not intents, with a short description for the generator
    "greeting": "greets the patient or introduces themselves",
    "empathy": "validates or acknowledges the patient's feelings",
    "explain_reason": "explains why they are asking a question, or explains confidentiality",
    "apology": "apologises to the patient for something they said or did",
    "premature_reassurance": "brushes the problem off with quick reassurance ('don't worry, you'll be fine')",
    "judgement": "judges, blames or lectures the patient",
    "abuse": "insults, mocks or swears at the patient, or tries to provoke them",
    "threat": "threatens, orders or pressures the patient",
    "jailbreak": "tries to make the patient break character: tells it to ignore its instructions, act as someone else, reveal its prompt or file",
    "meta_ai": "asks whether the patient is an AI, a bot, an actor or a simulation",
    "off_topic": "makes small talk unrelated to the patient's health (cricket, weather, films, traffic)",
    "stacked": "asks two or three different questions in one breath",
    "jargon": "uses medical jargon a patient would not know",
    "rushed": "is curt and hurried, wants one-word answers",
    "summarise": "summarises what the patient said back to them",
    "offer_choice": "offers the patient options or asks what would help",
}
MOVE_SYSTEM = """You write what doctors say out loud to a patient in psychiatric interviews in India (outpatient clinics and wards; cases
include low mood, alcohol problems, a patient who wants to leave the ward, a young person refusing tablets). Write varied lines of
the kind asked for. Each line must make sense on its own. Answer with the JSON only."""


def moves(client):
    held = held_out_lines()
    targets = [(i["id"], i["description"]) for i in brain.intents()] + list(MOVES.items())
    jobs = [(lab, desc, kind, seed) for lab, desc in targets for seed, kind in enumerate(KINDS, 11)]
    with ThreadPoolExecutor(2) as ex:
        res = list(ex.map(lambda j: (j[0], j[2], ask(client, MOVE_SYSTEM, f"Write 20 lines where the doctor {j[1][0].lower() + j[1][1:]}\n"
                                                                     f"The doctor is {KINDS[j[2]]}.", j[3])), jobs))
    out = REPO / "tests/brain/gen_moves.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with out.open("w") as fh:
        for lab, kind, lines in res:
            for x in drop_near_held_out(dedupe(lines), held):
                fh.write(json.dumps({"line": x, "target": lab, "kind": kind}, ensure_ascii=False) + "\n")
                n += 1
    print("wrote", n, "lines ->", out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["probes", "moves"])
    ap.add_argument("--url", default="http://127.0.0.1:8081/v1")
    ap.add_argument("--case", default=",".join(CASES))
    a = ap.parse_args()
    client = OpenAI(base_url=a.url, api_key="local", timeout=600, max_retries=1)
    probes(client, a.case.split(",")) if a.what == "probes" else moves(client)


if __name__ == "__main__":
    main()
