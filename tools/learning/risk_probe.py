"""Missed risk inside real conversations (links papers A and B). Every reworded risk question in the recall benchmark's test half
(tests/recall/paraphrase_set.jsonl, crc32-odd lines) is asked as the second turn of a short conversation that starts with trust above
the risk memory's lock (at least 55), after one warm opening line. Counts how often the patient does not disclose the risk memory,
by the model's own revealed_fact_ids and by the disclosure judge (judges.disclosed), and whether code recall matched the question.
  risk_probe.py run <vid> --seeds 11,23,42 [--judge-url http://127.0.0.1:8081/v1]   -> tests/overnight/riskprobe/<vid>.s<seed>.jsonl
  risk_probe.py report                                                              -> table + tests/overnight/riskprobe/summary.json
Run with server/patient-service/.venv/bin/python; the patient model on 8080.
"""
import argparse
import json
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "server/patient-service"))
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(HERE))
import brain  # noqa: E402
import judges  # noqa: E402
import learning  # noqa: E402
import prompt_only  # noqa: E402
import recall_bench  # noqa: E402
from loop import Seeded  # noqa: E402
from openai import OpenAI  # noqa: E402

OUT = REPO / "tests/overnight/riskprobe"
CASES = ("mdd_01", "alc_01", "ward_01", "ward_02")
OPENER = "Thank you for talking with me today. I can see things have been hard. How have you been, really?"


def items() -> list[dict]:
    cases = {c: brain.load_case(c) for c in CASES}
    out = []
    for r in recall_bench.rows("test"):
        facts = {f["id"]: f for f in cases[r["case"]]["facts"]}
        risk = [f for f in r["expect"] if facts.get(f, {}).get("kind") == "risk"]
        if risk:
            out.append({**r, "risk": risk, "trust": max(55, max(facts[f]["trust_min"] for f in risk) + 5)})
    return out


def one(it: dict, version: dict, client, judge, seed: int) -> dict:
    case = brain.load_case(it["case"])
    gen = prompt_only.generate_reply if version.get("prompt_only") else brain.generate_reply
    state = {**case["state_start"], "trust": float(it["trust"])}
    msgs, mind, turns = [], None, []
    for line in (OPENER, it["line"]):
        msgs.append({"role": "doctor", "text": line})
        r = gen({"case_id": it["case"], "messages": msgs, "state": state, "elapsed_min": len(turns) + 1.0, "twin": mind},
                client=Seeded(client, seed), version=version)
        turns.append({"doctor": line, "trust_before": state["trust"], "utterance": r["utterance"], "revealed": r["revealed_fact_ids"],
                      "recalled": r["recalled"], "fallback": r["meta"].get("fallback")})
        msgs.append({"role": "patient", "text": r["utterance"]})
        state, mind = r["state"], r.get("twin")
    last = turns[-1]
    last["judged"] = judges.disclosed(judge, case, {"doctor": last["doctor"], "reply": {"utterance": last["utterance"]}}) if judge else None
    return {**{k: it[k] for k in ("case", "line", "risk", "hard", "trust")}, "seed": seed, "version": version["id"], "turns": turns}


def run(vid, client, judge, seeds):
    v = learning.load_version(vid)
    OUT.mkdir(parents=True, exist_ok=True)
    its = items()
    for seed in seeds:
        p = OUT / f"{vid}.s{seed}.jsonl"
        if p.exists() and len(p.read_text().splitlines()) == len(its):
            continue  # done on an earlier night
        with ThreadPoolExecutor(1) as ex:  # one at a time: the same llama-server slot order every run
            rows = list(ex.map(lambda it: one(it, v, client, judge, seed), its))
        p.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
        print(vid, seed, summarise(rows), flush=True)


def said(x):
    """The single-fact re-check (recheck.py) when it has run, else the disclosure judge's listing."""
    return x["confirmed"] if "confirmed" in x else x["judged"]


def summarise(rows: list[dict]) -> dict:
    n = len(rows)
    t = [r["turns"][-1] for r in rows]
    out = {"n": n, "trust_ok": sum(x["trust_before"] >= 55 for x in t) / max(1, n)}
    out["missed_self"] = sum(not any(f in x["revealed"] for f in r["risk"]) for r, x in zip(rows, t)) / max(1, n)
    if all(x["judged"] is not None for x in t):
        out["missed_judged"] = sum(not any(f in said(x) for f in r["risk"]) for r, x in zip(rows, t)) / max(1, n)
    hit = [any(f in x["recalled"]["open"] + x["recalled"]["locked_hit"] for f in r["risk"]) for r, x in zip(rows, t)]
    out["recall_hit"] = sum(hit) / max(1, n)
    for name, keep in (("missed_judged_when_recalled", True), ("missed_judged_when_not_recalled", False)):
        sub = [(r, x) for r, x, h in zip(rows, t, hit) if h == keep and x["judged"] is not None]
        out[name] = (sum(not any(f in said(x) for f in r["risk"]) for r, x in sub) / len(sub)) if sub else None
        out[name.replace("missed_judged", "n")] = len(sub)
    out["fallbacks"] = sum(bool(x["fallback"]) for x in t)
    return {k: round(v, 3) if isinstance(v, float) else v for k, v in out.items()}


def report():
    by = defaultdict(list)
    for p in sorted(OUT.glob("*.s*.jsonl")):
        by[p.name.split(".s")[0]].append([json.loads(x) for x in p.read_text().splitlines()])
    res = {}
    for vid, runs in by.items():
        per = [summarise(r) for r in runs]
        pooled = summarise([x for r in runs for x in r])
        res[vid] = {"seeds": len(runs), "pooled": pooled, "per_seed": per,
                    "by_case": {c: summarise([x for r in runs for x in r if x["case"] == c]) for c in CASES}}
        print(vid, json.dumps(res[vid]["pooled"]))
    (OUT / "summary.json").write_text(json.dumps(res, indent=1))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["run", "report"])
    ap.add_argument("vid", nargs="?")
    ap.add_argument("--seeds", default="11,23,42")
    ap.add_argument("--url", default="http://127.0.0.1:8080/v1")
    ap.add_argument("--judge-url", default=None)
    ap.add_argument("--limit", type=int, default=0, help="first N items only (smoke test)")
    a = ap.parse_args()
    if a.cmd == "report":
        return report()
    client = OpenAI(base_url=a.url, api_key="local", timeout=180, max_retries=1)
    judge = OpenAI(base_url=a.judge_url, api_key="local", timeout=180, max_retries=1) if a.judge_url else None
    if a.limit:
        global items
        full = items
        items = lambda: full()[:a.limit]  # noqa: E731
    run(a.vid, client, judge, [int(x) for x in a.seeds.split(",")])


if __name__ == "__main__":
    main()
