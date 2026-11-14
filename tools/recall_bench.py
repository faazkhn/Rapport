"""Paraphrase recall benchmark for the Digital Twin (tests/recall/paraphrase_set.jsonl, written from each fact's clinical meaning
by a writer who never saw the activation tags). A line counts as recalled for a fact when the fact is in recall's open list
(trust 100, so the top-3 cap applies) or its locked hits. Split: dev (crc32 even) for tuning, test (odd) for reported numbers.
Usage: server/patient-service/.venv/bin/python tools/recall_bench.py [--split test|dev|all] [--lexical] [--misses] [--json out.json]
"""
import argparse
import json
import sys
import time
import zlib
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "server/patient-service"))
import brain  # noqa: E402
import twin  # noqa: E402

SET = REPO / "tests/recall/paraphrase_set.jsonl"


def split_of(line: str) -> str:
    return "dev" if zlib.crc32(line.encode()) % 2 == 0 else "test"


def rows(split: str) -> list[dict]:
    out = [json.loads(x) for x in SET.read_text(encoding="utf-8").splitlines() if x.strip()]
    return out if split == "all" else [r for r in out if split_of(r["line"]) == split]


def run(split="test", lexical=False) -> dict:
    cases = {c: brain.load_case(c) for c in ("mdd_01", "alc_01", "ward_01", "ward_02")}
    kind = {(c, f["id"]): f.get("kind") for c, case in cases.items() for f in case["facts"]}
    got = defaultdict(lambda: [0, 0])  # (case, fact) -> [hit, total]
    none_fp = none_n = extra = hits_n = risk_fp = nonrisk_n = 0
    ms, misses = [], []
    for r in rows(split):
        case = cases[r["case"]]
        t = time.perf_counter()
        rec = twin.recall(case, 100, r["line"], lexical=lexical)
        ms.append((time.perf_counter() - t) * 1000)
        hit = set(rec["open"]) | set(rec["locked_hit"])
        if not r["expect"]:
            none_n += 1
            none_fp += bool(hit)
            continue
        hits_n += len(hit)
        extra += len(hit - set(r["expect"]))
        if not any(kind.get((r["case"], f)) == "risk" for f in r["expect"]):
            nonrisk_n += 1
            risk_fp += any(kind.get((r["case"], f)) == "risk" for f in hit)
        for f in r["expect"]:
            g = got[(r["case"], f)]
            g[1] += 1
            g[0] += f in hit
            if f not in hit:
                misses.append((r["case"], f, r["line"], sorted(hit)))
    tot = lambda keys: (sum(got[k][0] for k in keys), sum(got[k][1] for k in keys))  # noqa: E731
    risk = [k for k in got if kind.get(k) == "risk"]
    a, n = tot(list(got))
    ra, rn = tot(risk)
    ms.sort()
    return {"split": split, "lexical_only": lexical, "fact_recall": round(a / max(1, n), 3), "n": n,
            "risk_recall": round(ra / max(1, rn), 3), "risk_n": rn,
            "risk_by_fact": {f"{c}/{f}": f"{got[(c, f)][0]}/{got[(c, f)][1]}" for c, f in sorted(risk)},
            "none_false_hit": round(none_fp / max(1, none_n), 3), "none_n": none_n,
            "risk_false_hit": round(risk_fp / max(1, nonrisk_n), 3), "nonrisk_n": nonrisk_n,
            "extra_per_line": round(extra / max(1, len(rows(split)) - none_n), 2),
            "ms_p50": round(ms[len(ms) // 2], 2), "ms_max": round(ms[-1], 2), "misses": misses}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="test", choices=["test", "dev", "all"])
    ap.add_argument("--lexical", action="store_true", help="tags only (brain v0)")
    ap.add_argument("--misses", action="store_true")
    ap.add_argument("--json")
    a = ap.parse_args()
    r = run(a.split, a.lexical)
    if a.misses:
        for c, f, line, hit in r["misses"]:
            print(f"MISS {c} {f}: {line!r} -> {hit}")
    print(json.dumps({k: v for k, v in r.items() if k != "misses"}, indent=1))
    if a.json:
        Path(a.json).write_text(json.dumps(r, indent=1))


if __name__ == "__main__":
    main()
