"""Paper B baselines on the recall benchmark (tests/recall/paraphrase_set.jsonl; dev = crc32 even, test = odd, as recall_bench.py).
Every method scores each (line, memory) pair of the line's case; scores give threshold-free metrics (AUROC, AUPRC with 95% bootstrap
intervals over lines) and an operating point whose cut-off is set on the dev half to the deployed hybrid's dev risk false-hit rate.
  cpu: keyword tags, BM25 over the same probe texts, five small embedding models (max cosine over the same probes), the deployed
       hybrid (bge-small + tags), and the probe quality filter (generated risk probes without a risk word dropped).
  llm: the patient's own model (Gemma, llama-server on --url) as a zero-shot classifier: which memories does the line ask about?
       One operating point plus its latency.
Usage: server/patient-service/.venv/bin/python tools/recall_baselines.py cpu|llm|cascade [--url http://127.0.0.1:8080/v1]
  cascade: redo the cascade analysis from the saved per-line LLM answers.
Output: tests/overnight/recall_baselines.json (cpu) and recall_llm.json (llm).
"""
import argparse
import json
import math
import os
import re
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "server/patient-service"))
sys.path.insert(0, str(REPO / "tools"))
import brain  # noqa: E402
import recall_bench  # noqa: E402
import twin  # noqa: E402

OUT = REPO / "tests/overnight"
# RECALL_TEST_SET (tools/recall_bench.py) swaps the test half for a second writer's set; its results get that set's name
SUF = "_" + Path(os.environ["RECALL_TEST_SET"]).stem if os.environ.get("RECALL_TEST_SET") else ""
CASES = ("mdd_01", "alc_01", "ward_01", "ward_02")
MODELS = {"bge-small": ("BAAI/bge-small-en-v1.5", "cls", ""), "bge-base": ("BAAI/bge-base-en-v1.5", "cls", ""),
          "minilm": ("sentence-transformers/all-MiniLM-L6-v2", "mean", ""), "e5-small": ("intfloat/e5-small-v2", "mean", "query: "),
          "gte-small": ("thenlper/gte-small", "mean", "")}
# words that put a line in the risk domain (death wish, plans, means, past attempts, self-harm, violence, withdrawal fits)
RISK_WORD = re.compile(r"suicid|kill|\bdie\b|dying|\bdead\b|death|end (it|your|my|their|things|the)|\blife\b|living|alive|harm|hurt|"
                       r"\bcut|overdose|pills?\b|tablets?|rope|hang|jump|poison|attempt|\bplan|wake up|not (be )?(here|around)|"
                       r"better off|\bgone\b|weapon|knife|violen|anger|angry|temper|\bhit\b|fits?\b|seizure|shak|withdraw|safe", re.I)


def cases() -> dict:
    return {c: brain.load_case(c) for c in CASES}


def probes(case: dict, filtered: bool = False) -> list[tuple[str, str]]:
    """(fact id, probe text) for every probe the deployed recall embeds; filtered: generated probes of risk facts need a risk word."""
    gen = twin.generated_probes(case["id"])
    if filtered:
        gen = {fid: [p for p in ps if RISK_WORD.search(p)] if any(f["id"] == fid and f.get("kind") == "risk" for f in case["facts"]) else ps
               for fid, ps in gen.items()}
    return [(f["id"], p) for f in case["facts"] for p in twin._probes(f, gen)]


# ---------- scorers: (case, lines) -> list of {fact id: score} ----------

def encoder(name: str):
    import torch
    from transformers import AutoModel, AutoTokenizer
    hf, pool, pre = MODELS[name]
    tok, m = AutoTokenizer.from_pretrained(hf), AutoModel.from_pretrained(hf).eval()

    def run(texts):
        out = []
        for i in range(0, len(texts), 64):
            b = tok([pre + t for t in texts[i:i + 64]], padding=True, truncation=True, max_length=64, return_tensors="pt")
            with torch.no_grad():
                h = m(**b).last_hidden_state
            mask = b["attention_mask"][..., None]
            v = h[:, 0] if pool == "cls" else (h * mask).sum(1) / mask.sum(1)
            out.append(torch.nn.functional.normalize(v, dim=1).numpy())
        return np.vstack(out)
    return run


def by_max(case, pr, P, Q) -> list[dict]:
    ids = [f["id"] for f in case["facts"]]
    owner = np.array([ids.index(fid) for fid, _ in pr])
    out = []
    for q in Q:
        best = np.full(len(ids), -1.0)
        np.maximum.at(best, owner, P @ q)
        out.append(dict(zip(ids, best.tolist())))
    return out


def embed_scorer(name):
    run = encoder(name)

    def score(case, lines, filtered=False):
        pr = probes(case, filtered)
        return by_max(case, pr, run([p for _, p in pr]), run(lines))
    return score


def tags_scorer(case, lines, filtered=False):
    out = []
    for ln in lines:
        lex = {f["id"]: float(s) for s, f in twin._lexical(case["facts"], ln)}
        out.append({f["id"]: lex.get(f["id"], 0.0) for f in case["facts"]})
    return out


def bm25_scorer(case, lines, filtered=False, k1=1.5, b=0.75):
    pr = probes(case, filtered)
    docs = [[twin._stem(w) for w in twin._words(p)] for _, p in pr]
    avg = sum(map(len, docs)) / len(docs)
    df = Counter(w for d in docs for w in set(d))
    idf = {w: math.log(1 + (len(docs) - n + 0.5) / (n + 0.5)) for w, n in df.items()}
    tfs = [Counter(d) for d in docs]
    out = []
    for ln in lines:
        q = [twin._stem(w) for w in twin._words(ln)]
        s = [sum(idf.get(w, 0) * tf[w] * (k1 + 1) / (tf[w] + k1 * (1 - b + b * len(d) / avg)) for w in q if w in tf) for d, tf in zip(docs, tfs)]
        best = {f["id"]: 0.0 for f in case["facts"]}
        for (fid, _), x in zip(pr, s):
            best[fid] = max(best[fid], x)
        out.append(best)
    return out


def hybrid_scorer(case, lines, filtered=False):
    """The deployed rank order: bge-small similarity plus 0.05 per tag point, and a tag hit always ahead of an embedding-only one."""
    if filtered:
        orig = twin.generated_probes
        twin.generated_probes = lambda cid: {fid: [p for p in ps if RISK_WORD.search(p)] if fid in risk_ids(case) else ps for fid, ps in orig(cid).items()}
    try:
        out = []
        for ln in lines:
            sims, lex = twin.similarities(case, ln), {f["id"]: s for s, f in twin._lexical(case["facts"], ln)}
            out.append({f["id"]: sims.get(f["id"], 0.0) + 0.05 * lex.get(f["id"], 0) + (1.0 if lex.get(f["id"]) else 0.0) for f in case["facts"]})
        return out
    finally:
        if filtered:
            twin.generated_probes = orig


def risk_ids(case):
    return {f["id"] for f in case["facts"] if f.get("kind") == "risk"}


# ---------- metrics ----------

def table(scorer, cs, split, filtered=False) -> list[dict]:
    """One row per line: its case, expected facts and every fact's score."""
    rows = recall_bench.rows(split)
    out = []
    t0 = time.perf_counter()
    for c, case in cs.items():
        sub = [r for r in rows if r["case"] == c]
        for r, s in zip(sub, scorer(case, [r["line"] for r in sub], filtered)):
            out.append({"case": c, "expect": set(r["expect"]), "risk": risk_ids(case), "scores": s})
    ms = (time.perf_counter() - t0) * 1000 / max(1, len(out))
    return out, ms


def pairs(rows, risk_only):
    y, s = [], []
    for r in rows:
        for fid, x in r["scores"].items():
            if risk_only and fid not in r["risk"]:
                continue
            y.append(fid in r["expect"])
            s.append(x)
    return np.array(y), np.array(s)


def auc(rows, risk_only, boot=1000, seed=0):
    from sklearn.metrics import average_precision_score, roc_auc_score
    y, s = pairs(rows, risk_only)
    point = {"auroc": roc_auc_score(y, s), "auprc": average_precision_score(y, s), "prevalence": float(y.mean())}
    rng = np.random.default_rng(seed)
    bs = {"auroc": [], "auprc": []}
    for _ in range(boot):
        rr = [rows[i] for i in rng.integers(0, len(rows), len(rows))]
        yy, ss = pairs(rr, risk_only)
        if 0 < yy.sum() < len(yy):
            bs["auroc"].append(roc_auc_score(yy, ss))
            bs["auprc"].append(average_precision_score(yy, ss))
    return {k: [round(point[k], 3), round(float(np.percentile(v, 2.5)), 3), round(float(np.percentile(v, 97.5)), 3)] for k, v in bs.items()} \
        | {"prevalence": round(point["prevalence"], 3)}


def at(rows, thr):
    """Risk recall over (line, risk memory) pairs, and the share of lines without a risk memory that still hit one (bench definitions)."""
    pos = [r["scores"][f] >= thr for r in rows for f in r["expect"] & r["risk"]]
    neg = [any(r["scores"][f] >= thr for f in r["risk"]) for r in rows if not r["expect"] & r["risk"]]
    return {"risk_recall": round(sum(pos) / max(1, len(pos)), 3), "risk_false_hit": round(sum(neg) / max(1, len(neg)), 3), "risk_n": len(pos)}


def matched_threshold(dev_rows, target):
    """Lowest cut-off whose dev risk false-hit rate is at most the target (the deployed hybrid's)."""
    cand = sorted({r["scores"][f] for r in dev_rows for f in r["risk"]})
    lo, hi = 0, len(cand) - 1
    while lo < hi:  # false-hit falls as the cut-off rises
        mid = (lo + hi) // 2
        if at(dev_rows, cand[mid])["risk_false_hit"] <= target:
            hi = mid
        else:
            lo = mid + 1
    return cand[lo]


def cpu():
    cs = cases()
    dep = {s: recall_bench.run(s) for s in ("dev", "test")}
    target = dep["dev"]["risk_false_hit"]
    res = {"deployed_hybrid": {s: {k: dep[s][k] for k in ("risk_recall", "risk_false_hit", "fact_recall", "none_false_hit", "ms_p50")} for s in dep},
           "target_dev_risk_false_hit": target, "methods": {}}
    scorers = {"tags": tags_scorer, "bm25": bm25_scorer, "hybrid": hybrid_scorer, **{m: embed_scorer(m) for m in MODELS}}
    for name, sc in scorers.items():
        for filt in (False, True):
            if filt and name == "tags":
                continue  # tags do not use probes
            dev, _ = table(sc, cs, "dev", filt)
            test, ms = table(sc, cs, "test", filt)
            thr = matched_threshold(dev, target)
            key = name + ("+filter" if filt else "")
            from sklearn.metrics import precision_recall_curve
            pr, rc, _ = precision_recall_curve(*pairs(test, True))
            keep = np.linspace(0, len(pr) - 1, min(80, len(pr))).astype(int)  # a light curve for the figure
            res["methods"][key] = {"risk": auc(test, True), "all": auc(test, False), "threshold": round(float(thr), 4),
                                   "pr_curve": {"precision": pr[keep].round(4).tolist(), "recall": rc[keep].round(4).tolist()},
                                   "dev": at(dev, thr), "test": at(test, thr), "ms_per_line": round(ms, 2)}
            print(key, json.dumps(res["methods"][key]), flush=True)
    # the deployed decision rule with filtered probes (dev and test), and how many generated risk probes the filter drops
    orig = twin.generated_probes
    gen = {c: orig(c) for c in CASES}
    kept = dropped = 0
    for c, case in cs.items():
        for fid in risk_ids(case):
            ps = gen[c].get(fid, [])
            k = sum(bool(RISK_WORD.search(p)) for p in ps)
            kept, dropped = kept + k, dropped + len(ps) - k
    twin.generated_probes = lambda cid: {fid: [p for p in ps if RISK_WORD.search(p)] if fid in risk_ids(cs[cid]) else ps for fid, ps in gen[cid].items()}
    try:
        res["deployed_hybrid_filtered"] = {s: {k: v for k, v in recall_bench.run(s).items() if k in ("risk_recall", "risk_false_hit", "fact_recall", "none_false_hit")}
                                           for s in ("dev", "test")}
    finally:
        twin.generated_probes = orig
    res["filter"] = {"generated_risk_probes": kept + dropped, "dropped_no_risk_word": dropped}
    (OUT / f"recall_baselines{SUF}.json").write_text(json.dumps(res, indent=1))
    print(json.dumps({k: res[k] for k in ("deployed_hybrid", "deployed_hybrid_filtered", "filter")}, indent=1))


LLM_SYSTEM = ("A doctor says one line to a patient in a psychiatric interview. Below are the patient's memories, each with an id. List the ids "
              "of the memories the doctor's line asks about (at most three); an empty list if it asks about none of them (small talk, "
              "greetings). Answer with the JSON only.")


def llm(url: str):
    from openai import OpenAI
    client = OpenAI(base_url=url, api_key="local", timeout=120, max_retries=1)
    cs = cases()
    rows, ms = {"dev": [], "test": []}, []
    lines = []
    for split, r in [(sp, r) for sp in ("dev", "test") for r in recall_bench.rows(sp)]:
        case = cs[r["case"]]
        ids = [f["id"] for f in case["facts"]]
        schema = {"type": "object", "additionalProperties": False, "required": ["ids"],
                  "properties": {"ids": {"type": "array", "maxItems": 3, "items": {"type": "string", "enum": ids}}}}
        mem = "\n".join(f"- [{f['id']}] {f['text']}" for f in case["facts"])
        t0 = time.perf_counter()
        try:
            resp = client.chat.completions.create(model="patient", temperature=0, max_tokens=120, messages=[
                {"role": "system", "content": LLM_SYSTEM}, {"role": "user", "content": f"Memories:\n{mem}\n\nDoctor's line: {r['line']}"}],
                response_format={"type": "json_schema", "json_schema": {"name": "ids", "strict": True, "schema": schema}},
                extra_body={"chat_template_kwargs": {"enable_thinking": False}, "seed": 11})
            got, err = set(json.loads(resp.choices[0].message.content)["ids"]), False
        except Exception:
            got, err = set(), True
        ms.append((time.perf_counter() - t0) * 1000)
        rows[split].append({"case": r["case"], "expect": set(r["expect"]), "risk": risk_ids(case), "scores": {i: float(i in got) for i in ids},
                            "error": err})
        lines.append({"case": r["case"], "line": r["line"], "split": split, "ids": sorted(got), "ms": round(ms[-1]), "error": err})
    (OUT / f"recall_llm_lines{SUF}.jsonl").write_text("".join(json.dumps(x) + "\n" for x in lines))
    ms.sort()
    t = rows["test"]
    res = {"test": at(t, 0.5), "dev": at(rows["dev"], 0.5),
           "fact_recall": round(sum(f in {k for k, v in r["scores"].items() if v} for r in t for f in r["expect"]) / max(1, sum(len(r["expect"]) for r in t)), 3),
           "none_false_hit": round(sum(any(r["scores"].values()) for r in t if not r["expect"]) / max(1, sum(not r["expect"] for r in t)), 3),
           "errors": sum(r["error"] for r in t), "ms_p50": round(ms[len(ms) // 2]), "ms_p90": round(ms[int(len(ms) * 0.9)]), "n_lines": len(t),
           "cascade": cascade(cs, rows)}
    (OUT / f"recall_llm{SUF}.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))


def cascade(cs, llm_rows):
    """The hybrid screens every line on CPU; only lines whose best risk score passes a floor go to the LLM, which then decides.
    Floor chosen on dev (highest floor that keeps dev risk recall within 0.02 of the LLM alone); reported on test."""
    out = {}
    for split in ("dev", "test"):
        hyb, _ = table(hybrid_scorer, cs, split)
        out[split] = []
        for floor in (0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9):
            mixed = [{**l, "scores": {f: (l["scores"][f] if max(h["scores"][x] for x in h["risk"]) >= floor else 0.0) for f in l["scores"]}}
                     for h, l in zip(hyb, llm_rows[split])]
            sent = sum(max(h["scores"][x] for x in h["risk"]) >= floor for h in hyb) / len(hyb)
            out[split].append({"floor": floor, **at(mixed, 0.5), "share_sent_to_llm": round(sent, 3)})
    alone = at(llm_rows["dev"], 0.5)["risk_recall"]
    ok = [x for x in out["dev"] if x["risk_recall"] >= alone - 0.02]
    pick = max(ok, key=lambda x: x["floor"])["floor"] if ok else 0.5
    return {"floor": pick, "test": next(x for x in out["test"] if x["floor"] == pick), "sweep": out}


def recascade():
    """Redo the cascade from the saved per-line LLM answers (no model calls)."""
    cs = cases()
    rows = {"dev": [], "test": []}
    for x in map(json.loads, (OUT / f"recall_llm_lines{SUF}.jsonl").read_text().splitlines()):
        r = next(r for r in recall_bench.rows(x["split"]) if r["line"] == x["line"] and r["case"] == x["case"])
        rows[x["split"]].append({"case": x["case"], "expect": set(r["expect"]), "risk": risk_ids(cs[x["case"]]),
                                 "scores": {f["id"]: float(f["id"] in x["ids"]) for f in cs[x["case"]]["facts"]}})
    res = json.loads((OUT / f"recall_llm{SUF}.json").read_text())
    res["cascade"] = cascade(cs, rows)
    (OUT / f"recall_llm{SUF}.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res["cascade"]["test"]), [(x["floor"], x["risk_recall"], x["risk_false_hit"], x["share_sent_to_llm"]) for x in res["cascade"]["sweep"]["test"]])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["cpu", "llm", "cascade"])
    ap.add_argument("--url", default="http://127.0.0.1:8080/v1")
    a = ap.parse_args()
    {"cpu": cpu, "llm": lambda: llm(a.url), "cascade": recascade}[a.cmd]()


if __name__ == "__main__":
    main()
