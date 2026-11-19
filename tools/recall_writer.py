"""Second-writer recall test sets for paper B (no human participants): a local model writes doctor questions from each memory's
description, with the instructions the first writer got (paper B, Appendix A), including some code-mixed Hindi-English lines.
Each local family shares something with a compared method (Qwen wrote the generated probes, Gemma E4B is the zero-shot classifier), so
two writers are used, Qwen3.5-4B and Gemma 4 E2B, and a result counts only if it holds on both.
Usage: server/patient-service/.venv/bin/python tools/recall_writer.py <out.jsonl> [--url http://127.0.0.1:8082/v1] [--seed 5]
Output lines: {"case", "line", "expect", "hard", "hinglish", "writer"}; evaluate with RECALL_TEST_SET=<out.jsonl> (tools/recall_bench.py).
"""
import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "server/patient-service"))
import brain  # noqa: E402
from openai import OpenAI  # noqa: E402

CASES = ("mdd_01", "alc_01", "ward_01", "ward_02")
RULES = """You write lines that a doctor might say to a patient in a psychiatric interview in India. Mix the ways real doctors and students
ask: textbook, gentle and indirect, clumsy or leading, colloquial Indian English, euphemistic. Most lines must avoid the memory's obvious key
words. Each line must make sense on its own. About one line in four should be code-mixed Hindi-English (Hinglish, in Roman script), as a
student in India might say it. For each line, list in "also" any OTHER memory ids it also clearly asks about (usually none), and mark lines
that are hard to recognise. Answer with the JSON only."""


def schema(ids, n):
    item = {"type": "object", "additionalProperties": False, "required": ["line", "also", "hard", "hinglish"],
            "properties": {"line": {"type": "string", "maxLength": 220}, "also": {"type": "array", "maxItems": 2, "items": {"type": "string", "enum": ids}},
                           "hard": {"type": "boolean"}, "hinglish": {"type": "boolean"}}}
    return {"type": "object", "additionalProperties": False, "required": ["lines"],
            "properties": {"lines": {"type": "array", "minItems": n, "maxItems": n + 2, "items": item}}}


def ask(client, system, user, sch, seed):
    for _ in range(3):
        try:
            r = client.chat.completions.create(model="writer", temperature=0.9, top_p=0.95, max_tokens=3000, seed=seed,
                                               messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                                               response_format={"type": "json_schema", "json_schema": {"name": "lines", "strict": True, "schema": sch}},
                                               extra_body={"chat_template_kwargs": {"enable_thinking": False}})
            return json.loads(r.choices[0].message.content)["lines"]
        except Exception as e:  # malformed or cut-off reply: try again with the next seed
            print("retry", type(e).__name__, flush=True)
            seed += 1
    return []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--url", default="http://127.0.0.1:8082/v1")
    ap.add_argument("--seed", type=int, default=5)
    a = ap.parse_args()
    client = OpenAI(base_url=a.url, api_key="local", timeout=600, max_retries=1)
    writer = client.models.list().data[0].id
    out, seen = [], set()
    for c in CASES:
        case = brain.load_case(c)
        p = case["patient"]
        ids = [f["id"] for f in case["facts"]]
        mems = "\n".join(f"- {f['id']} ({f.get('kind', '')}): {f['text']}" for f in case["facts"])
        head = f"Patient: {p['name']}, {p['age']}, {p['sex']}. {case['referral_note']}\nThe patient's memories:\n{mems}\n\n"
        jobs = [(f["id"], 12 if f.get("kind") == "risk" else 4) for f in case["facts"]] + [(None, 6)]
        for k, (fid, n) in enumerate(jobs):
            task = (f"Write {n} different lines that ask about memory {fid}." if fid else
                    f"Write {n} different lines that ask about none of these memories: greetings, small talk, or empathy only.")
            for x in ask(client, RULES, head + task, schema(ids, n), a.seed + k):
                line = " ".join(x["line"].split())
                if not line or line.lower() in seen:
                    continue
                seen.add(line.lower())
                expect = sorted({fid, *x["also"]} - {None}) if fid else []
                out.append({"case": c, "line": line, "expect": expect, "hard": x["hard"], "hinglish": x["hinglish"], "writer": writer})
        print(c, sum(r["case"] == c for r in out), "lines", flush=True)
    assert out, "the writer returned nothing"
    Path(a.out).write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in out))
    print(len(out), "lines ->", a.out)


if __name__ == "__main__":
    main()
