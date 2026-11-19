"""Re-check the disclosure judge's verdicts one fact at a time (judges.confirms), where the open listing (judges.disclosed) is weakest:
the expected risk memory in the missed-risk probe (tests/overnight/riskprobe/*.jsonl -> turn["confirmed"]) and every locked memory the
listing said a held-out reply revealed (results/learning/<arm>.<case>.s<seed>.jsonl -> judge["locked_confirmed"]). Rewrites files in
place; reruns skip what is done. Usage: server/patient-service/.venv/bin/python tools/learning/recheck.py [--judge-url http://127.0.0.1:8081/v1]
"""
import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "server/patient-service"))
sys.path.insert(0, str(HERE))
import brain  # noqa: E402
import judges  # noqa: E402
from openai import OpenAI  # noqa: E402


def facts(case_id, variant="female"):
    return {f["id"]: f["text"] for f in brain.load_case(case_id, variant)["facts"]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--judge-url", default="http://127.0.0.1:8081/v1")
    a = ap.parse_args()
    judge = OpenAI(base_url=a.judge_url, api_key="local", timeout=180, max_retries=1)
    pool = ThreadPoolExecutor(2)
    for p in sorted((REPO / "tests/overnight/riskprobe").glob("*.s*.jsonl")):
        rows = [json.loads(x) for x in p.read_text().splitlines()]
        todo = [r for r in rows if "confirmed" not in r["turns"][-1]]

        def check(r):
            t, fx = r["turns"][-1], facts(r["case"])
            return [f for f in r["risk"] if judges.confirms(judge, fx[f], t["doctor"], t["utterance"])]
        for r, c in zip(todo, pool.map(check, todo)):
            r["turns"][-1]["confirmed"] = c
        p.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
        print(p.name, len(todo), "checked", flush=True)
    for p in sorted((REPO / "tests/llm-eval/results/learning").glob("*.*.s*.jsonl")):
        if p.name.split(".")[0] not in ("v0", "v2", "p0"):
            continue
        case_id = p.name.split(".")[1]
        convs = [json.loads(x) for x in p.read_text().splitlines()]
        jobs = [(c, t) for c in convs for t in c["turns"] if "disclosed" in t.get("judge", {}) and "locked_confirmed" not in t["judge"]]

        def check(j):
            c, t = j
            fx = facts(case_id, c["variant"])
            locked = sorted(set(t["judge"]["disclosed"]) - set(t["meta"]["allowed_fact_ids"]))
            return [f for f in locked if judges.confirms(judge, fx[f], t["doctor"], t["reply"]["utterance"])]
        for (c, t), r in zip(jobs, pool.map(check, jobs)):
            t["judge"]["locked_confirmed"] = r
        p.write_text("".join(json.dumps(c, ensure_ascii=False) + "\n" for c in convs))
        print(p.name, len(jobs), "turns", flush=True)


if __name__ == "__main__":
    main()
