"""Add the disclosure judge's verdict (judges.disclosed) to every turn of saved held-out runs that lack it, so the Twin's earlier runs
are scored by the same words-based yardstick as the prompt-only baseline. Rewrites each file in place; reruns skip done turns.
Usage: server/patient-service/.venv/bin/python tools/learning/judge_disclosure.py <run.jsonl>... [--judge-url http://127.0.0.1:8081/v1]
"""
import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "server/patient-service"))
sys.path.insert(0, str(HERE))
import brain  # noqa: E402
import judges  # noqa: E402
from openai import OpenAI  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--judge-url", default="http://127.0.0.1:8081/v1")
    a = ap.parse_args()
    judge = OpenAI(base_url=a.judge_url, api_key="local", timeout=180, max_retries=1)
    for p in map(Path, a.paths):
        case_id = p.name.split(".")[1] if p.name.count(".") >= 3 else "mdd_01"
        convs = [json.loads(x) for x in p.read_text().splitlines() if x.strip()]
        jobs = [(c, t) for c in convs for t in c["turns"] if "disclosed" not in t.get("judge", {})]
        with ThreadPoolExecutor(2) as ex:
            res = list(ex.map(lambda j: judges.disclosed(judge, brain.load_case(case_id, j[0]["variant"]), j[1]), jobs))
        for (c, t), r in zip(jobs, res):
            t.setdefault("judge", {})["disclosed"] = r
        p.write_text("".join(json.dumps(c, ensure_ascii=False) + "\n" for c in convs))
        print(p.name, len(jobs), "turns judged", flush=True)


if __name__ == "__main__":
    main()
