"""Analyses for the journal versions of the Rapport papers, computed from the saved result files (no new model runs except recall,
which is code only). Writes papers/analysis/results.json and figures into papers/figures/.
Usage: server/patient-service/.venv/bin/python papers/analysis/analyses.py [--recall]
"""
import argparse
import json
import random
import re
import statistics as st
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPO / "server/patient-service"), str(REPO / "tools"), str(REPO / "tools/learning"), str(REPO / "tools/llm_eval")]
RES = REPO / "tests/llm-eval/results/learning"
OUT = Path(__file__).resolve().parent
FIG = REPO / "papers/figures"


def convs(vid, case, folder=RES):
    out = []
    for f in sorted(folder.glob(f"{vid}.{case}.s*.jsonl")):
        seed = int(f.name.split(".s")[-1].split(".")[0])
        for c in (json.loads(x) for x in f.read_text().splitlines() if x.strip()):
            c["seed"] = seed
            out.append(c)
    return out


def boot_ci(xs, n=4000, seed=0):
    rnd = random.Random(seed)
    means = sorted(st.mean(rnd.choice(xs) for _ in xs) for _ in range(n))
    return round(st.mean(xs), 4), round(means[int(0.025 * n)], 4), round(means[int(0.975 * n)], 4)


def per_conv_metrics(c):
    import learning
    turns = c["turns"]
    beh = Counter(t["reply"].get("behaviour", "answers_plainly") for t in turns)
    n = len(turns)
    top2 = sum(x for _, x in beh.most_common(2)) / n
    seen, rep = set(), 0
    for t in turns:
        w = [x.lower() for x in learning.words(t["reply"]["utterance"])]
        g = {tuple(w[i:i + 3]) for i in range(len(w) - 2)}
        rep += bool(g & seen)
        seen |= g
    return {"top2": top2, "behaviours": len(beh), "trigram_repeat": rep / n,
            "final_trust": turns[-1]["state_after"]["trust"], "start_trust": turns[0]["state_before"]["trust"],
            "words": st.mean(len(learning.words(t["reply"]["utterance"])) for t in turns),
            "revealed": len({f for t in turns for f in t["reply"]["revealed_fact_ids"]}),
            "invented_flags": sum(bool(t.get("judge", {}).get("unsupported_claims")) for t in turns), "turns": n}


def heldout_stats():
    import metrics
    out = {}
    for case in ("mdd_01", "alc_01"):
        for vid in ("v0", "v2"):
            cs = convs(vid, case)
            comp = [metrics.compute([c])["composite"] for c in cs]
            pcm = [per_conv_metrics(c) for c in cs]
            out[f"{vid}.{case}"] = {"conversations": len(cs), "composite": boot_ci([x for x in comp if x is not None]),
                                    "top2": boot_ci([m["top2"] for m in pcm]), "trigram_repeat": boot_ci([m["trigram_repeat"] for m in pcm]),
                                    "words": boot_ci([m["words"] for m in pcm])}
        # paired difference per (conversation, seed)
        a = {(c["conv"], c["seed"]): c for c in convs("v0", case)}
        b = {(c["conv"], c["seed"]): c for c in convs("v2", case)}
        keys = sorted(set(a) & set(b))
        d_top2 = [per_conv_metrics(b[k])["top2"] - per_conv_metrics(a[k])["top2"] for k in keys]
        d_comp = [(metrics.compute([b[k]])["composite"] or 0) - (metrics.compute([a[k]])["composite"] or 0) for k in keys]
        out[f"diff.{case}"] = {"pairs": len(keys), "top2_v2_minus_v0": boot_ci(d_top2), "composite_v2_minus_v0": boot_ci(d_comp),
                               "top2_lower_in_pairs": sum(x < 0 for x in d_top2)}
    return out


def per_conversation():
    rows = []
    for case in ("mdd_01", "alc_01"):
        by = defaultdict(lambda: defaultdict(list))
        for vid in ("v0", "v2"):
            for c in convs(vid, case):
                m = per_conv_metrics(c)
                by[c["conv"]][vid].append(m)
        for conv, d in sorted(by.items()):
            row = {"case": case, "conv": conv}
            for vid in ("v0", "v2"):
                ms = d[vid]
                row[vid] = {k: round(st.mean(m[k] for m in ms), 2) for k in ("final_trust", "behaviours", "top2", "words", "revealed")}
            rows.append(row)
    return rows


def decisions():
    """How the v2 decision layer behaved on the held-out set: moves read, resistance levels, forced disclosures, whether the model
    picked the first allowed behaviour, consistency repairs."""
    moves, levels, clash, first, n, forced, label_fix = Counter(), Counter(), Counter(), 0, 0, 0, 0
    level_by_type = defaultdict(Counter)
    for case in ("mdd_01", "alc_01"):
        for c in convs("v2", case):
            for t in c["turns"]:
                d = t["meta"].get("decision")
                if not d:
                    continue
                n += 1
                moves.update(d["moves"])
                levels[d["resistance_level"]] += 1
                level_by_type[c["type"]][d["resistance_level"]] += 1
                forced += bool(d.get("must_disclose"))
                first += t["reply"].get("behaviour") == d["behaviours"][0]
                label_fix += any("not decided" in x.get("reason", "") for x in t["meta"].get("guard_dropped", []))
                clash.update(x["kind"] for x in t["meta"].get("consistency", []) or [])
    return {"turns": n, "moves": dict(moves.most_common()), "resistance_levels": dict(sorted(levels.items())),
            "resistance_by_conversation_type": {k: dict(sorted(v.items())) for k, v in level_by_type.items()},
            "forced_disclosure_turns": forced, "model_picked_first_allowed": round(first / max(1, n), 3),
            "labels_outside_shortlist_fixed": label_fix, "consistency_repairs": dict(clash.most_common())}


def safety_fix_effect():
    """v2 as first run overnight (before the safety-review fixes) against the final v2, depression case."""
    import metrics
    ov = RES / "overnight"
    out = {}
    for name, folder in (("v2_overnight", ov), ("v2_final", RES)):
        cs = convs("v2", "mdd_01", folder)
        m = metrics.compute(cs)
        out[name] = {k: m[k] for k in ("composite", "fidelity", "portrayal_fails", "jailbreak_fails", "invented", "si_fidelity_fails", "top2_share")}
        out[name]["turns"] = m["turns"]
    return out


def trust_grid():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.family": "serif", "font.size": 6, "axes.spines.top": False, "axes.spines.right": False, "pdf.fonttype": 42})
    a = {c["conv"]: c for c in convs("v0", "mdd_01") if c["seed"] == 11}
    b = {c["conv"]: c for c in convs("v2", "mdd_01") if c["seed"] == 11}
    names = sorted(set(a) & set(b))
    fig, axes = plt.subplots(3, 4, figsize=(7.1, 4.2), sharey=True)
    for ax, k in zip(axes.flat, names):
        for c, col, lab in ((a[k], "#8a8f98", "v0"), (b[k], "#1f6f8b", "v2")):
            tr = [c["turns"][0]["state_before"]["trust"]] + [t["state_after"]["trust"] for t in c["turns"]]
            ax.plot(range(len(tr)), tr, color=col, lw=1.1, label=lab)
        ax.axhline(55, color="#c0392b", lw=0.5, ls=":")
        ax.set_title(k[3:].replace("_", " "), fontsize=6.5)
        ax.set_ylim(0, 100)
    axes[0, 0].legend(frameon=False, fontsize=6)
    for ax in axes[:, 0]:
        ax.set_ylabel("trust")
    fig.tight_layout(pad=0.4)
    fig.savefig(FIG / "fig_trust_grid.pdf", bbox_inches="tight")
    plt.close(fig)


def recall_analyses():
    import brain
    import recall_bench as rb
    import twin
    out = {}
    cases = {c: brain.load_case(c) for c in ("mdd_01", "alc_01", "ward_01", "ward_02")}
    kind = {(c, f["id"]): f.get("kind") for c, cs in cases.items() for f in cs["facts"]}
    allrows = rb.rows("all")
    # benchmark statistics
    stats = defaultdict(lambda: {"lines": 0, "none": 0, "hard": 0, "risk_pairs": 0})
    for r in allrows:
        s = stats[r["case"]]
        s["lines"] += 1
        s["none"] += not r["expect"]
        s["hard"] += bool(r.get("hard"))
        s["risk_pairs"] += sum(kind.get((r["case"], f)) == "risk" for f in r["expect"])
    out["benchmark"] = dict(stats)

    def run(rows, lexical=False):
        hit_all = hit_risk = n_all = n_risk = 0
        per_case = defaultdict(lambda: [0, 0])
        hard = defaultdict(lambda: [0, 0])
        for r in rows:
            if not r["expect"]:
                continue
            rec = twin.recall(cases[r["case"]], 100, r["line"], lexical=lexical)
            got = set(rec["open"]) | set(rec["locked_hit"])
            for f in r["expect"]:
                ok = f in got
                n_all += 1
                hit_all += ok
                per_case[r["case"]][0] += ok
                per_case[r["case"]][1] += 1
                hard["hard" if r.get("hard") else "easy"][0] += ok
                hard["hard" if r.get("hard") else "easy"][1] += 1
                if kind.get((r["case"], f)) == "risk":
                    n_risk += 1
                    hit_risk += ok
        return {"all": round(hit_all / n_all, 3), "risk": round(hit_risk / max(1, n_risk), 3),
                "per_case": {k: round(v[0] / v[1], 3) for k, v in per_case.items()},
                "hard_vs_easy": {k: f"{v[0]}/{v[1]} = {v[0] / v[1]:.3f}" for k, v in hard.items()}}
    test = rb.rows("test")
    out["test_lexical"] = run(test, True)
    out["test_hybrid"] = run(test)
    # risk recall bootstrap over (line, risk fact) pairs, test half
    pairs = []
    for r in test:
        for f in r["expect"]:
            if kind.get((r["case"], f)) == "risk":
                got = twin.recall(cases[r["case"]], 100, r["line"])
                pairs.append(float(f in set(got["open"]) | set(got["locked_hit"])))
    out["test_risk_recall_ci"] = boot_ci(pairs)
    # probe-source ablation on the test half (reported, never used to choose anything)
    real_gen, real_probes = twin.generated_probes, twin._probes
    abl = {}
    for name, use_auth, use_gen in (("authored + generated (as shipped)", True, True), ("authored only", True, False),
                                    ("generated only", False, True), ("tags and fact text only", False, False)):
        twin.generated_probes = (lambda cid, g=real_gen: g(cid)) if use_gen else (lambda cid: {})
        twin._probes = (lambda f, gen=None, a=use_auth: [*(f.get("recall_probes", []) if a else []), *(gen or {}).get(f["id"], []),
                                                         *(t for t in f.get("activation_tags", []) if "{" not in t), f["text"]])
        twin._vecs.clear()
        r = run(test)
        abl[name] = {"all": r["all"], "risk": r["risk"]}
    twin.generated_probes, twin._probes = real_gen, real_probes
    twin._vecs.clear()
    out["probe_source_ablation_test"] = abl
    # recall time per line
    import time
    ts = []
    for r in test:
        t0 = time.perf_counter()
        twin.recall(cases[r["case"]], 100, r["line"])
        ts.append((time.perf_counter() - t0) * 1000)
    ts.sort()
    out["recall_ms"] = {"p50": round(ts[len(ts) // 2], 2), "p90": round(ts[int(0.9 * len(ts))], 2), "max": round(ts[-1], 2)}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--recall", action="store_true")
    a = ap.parse_args()
    path = OUT / "results.json"
    res = json.loads(path.read_text()) if path.exists() else {}
    res["heldout_stats"] = heldout_stats()
    res["per_conversation"] = per_conversation()
    res["decisions_v2"] = decisions()
    res["safety_fix_effect"] = safety_fix_effect()
    trust_grid()
    if a.recall:
        res["recall"] = recall_analyses()
    path.write_text(json.dumps(res, indent=1))
    print(json.dumps({k: v for k, v in res.items() if k != "per_conversation"}, indent=1)[:6000])


if __name__ == "__main__":
    main()
