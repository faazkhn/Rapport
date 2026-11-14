"""Extra recall analyses on the test half for paper 3: where the correct memory ranks, similarity of correct pairs against
the best similarity on 'none' lines, and what a miss matched instead. Writes papers/analysis/recall_extra.json and a figure."""
import json
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPO / "server/patient-service"), str(REPO / "tools")]
import brain  # noqa: E402
import recall_bench as rb  # noqa: E402
import twin  # noqa: E402

cases = {c: brain.load_case(c) for c in ("mdd_01", "alc_01", "ward_01", "ward_02")}
kind = {(c, f["id"]): f.get("kind") for c, cs in cases.items() for f in cs["facts"]}
ranks, correct_sims, none_best, nonrisk_best_risk = [], [], [], []
miss = Counter()
for r in rb.rows("test"):
    case = cases[r["case"]]
    sims = twin.similarities(case, r["line"])
    order = sorted(sims, key=sims.get, reverse=True)
    if not r["expect"]:
        none_best.append(max(sims.values()))
    risk_sims = [v for f, v in sims.items() if kind.get((r["case"], f)) == "risk"]
    if not any(kind.get((r["case"], f)) == "risk" for f in r["expect"]) and risk_sims:
        nonrisk_best_risk.append(max(risk_sims))
    rec = twin.recall(case, 100, r["line"])
    got = set(rec["open"]) | set(rec["locked_hit"])
    for f in r["expect"]:
        ranks.append(order.index(f) + 1)
        correct_sims.append(sims[f])
        if kind.get((r["case"], f)) == "risk" and f not in got:
            miss["matched nothing" if not got else ("matched another risk memory" if any(kind.get((r["case"], g)) == "risk" for g in got)
                                                    else "matched a non-risk memory")] += 1
n = len(ranks)
out = {"pairs": n, "top1": round(sum(x == 1 for x in ranks) / n, 3), "top3": round(sum(x <= 3 for x in ranks) / n, 3),
       "top5": round(sum(x <= 5 for x in ranks) / n, 3), "median_rank": sorted(ranks)[n // 2],
       "correct_sim_median": round(sorted(correct_sims)[n // 2], 3), "none_best_median": round(sorted(none_best)[len(none_best) // 2], 3),
       "none_lines": len(none_best), "nonrisk_lines": len(nonrisk_best_risk),
       "nonrisk_best_risk_over_0.78": round(sum(x >= 0.78 for x in nonrisk_best_risk) / len(nonrisk_best_risk), 3),
       "risk_misses": dict(miss)}
(Path(__file__).parent / "recall_extra.json").write_text(json.dumps(out, indent=1))
print(json.dumps(out, indent=1))

import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
plt.rcParams.update({"font.family": "serif", "font.size": 7, "axes.spines.top": False, "axes.spines.right": False, "pdf.fonttype": 42})
fig, ax = plt.subplots(figsize=(3.4, 1.9))
bins = [0.55 + 0.01 * i for i in range(41)]
ax.hist(correct_sims, bins=bins, color="#1f6f8b", alpha=0.75, label="correct memory (asked about)")
ax.hist(nonrisk_best_risk, bins=bins, color="#c0392b", alpha=0.55, label="best risk memory, non-risk question")
for x, lab in ((0.76, "floor"), (0.78, "risk"), (0.83, "clear")):
    ax.axvline(x, color="k", lw=0.6, ls=":")
    ax.text(x - 0.002, 0.5, lab, rotation=90, va="bottom", ha="right", fontsize=5.5)
ax.set_xlabel("cosine similarity to the best probe")
ax.set_ylabel("count")
ax.legend(frameon=False, fontsize=6, loc="upper center", bbox_to_anchor=(0.5, 1.22), ncol=1)
fig.tight_layout(pad=0.3)
fig.savefig(REPO / "papers/figures/fig_recall_sims.pdf", bbox_inches="tight")
