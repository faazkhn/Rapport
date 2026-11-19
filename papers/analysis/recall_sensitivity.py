"""Test-half sensitivity of recall to the risk cut-off, the overnight recall-only tune against the shipped setting, and the
per-memory similarity bars for the worked example in paper 3. Report only: nothing here chooses a setting."""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPO / "server/patient-service"), str(REPO / "tools")]
import brain  # noqa: E402
import recall_bench as rb  # noqa: E402
import twin  # noqa: E402

twin._load_tuned()
NAMES = ("SIM_HIT", "SIM_RISK", "SIM_FLOOR", "SIM_NEAR", "RISK_NEAR", "RISK_MARGIN")
shipped = {k: getattr(twin, k) for k in NAMES}


def at(**kw):
    for k, v in {**shipped, **kw}.items():
        setattr(twin, k, v)
    out = {}
    for split in ("dev", "test"):
        r = rb.run(split)
        out[split] = {k: r[k] for k in ("fact_recall", "risk_recall", "risk_false_hit", "none_false_hit", "extra_per_line")}
    return out


res = {"shipped": {**at(), "settings": shipped}}
res["overnight_recall_only_tune"] = at(SIM_HIT=0.86, SIM_RISK=0.72, SIM_FLOOR=0.76, SIM_NEAR=0.04, RISK_NEAR=0.74, RISK_MARGIN=0.04)
res["risk_cutoff_sweep"] = {f"{x:.2f}": at(SIM_RISK=x) for x in (0.72, 0.74, 0.76, 0.78, 0.80, 0.82, 0.84)}
at()
case = brain.load_case("mdd_01")
line = "Have you ever felt like you'd be better off not being around?"
sims = twin.similarities(case, line)
label = {f["id"]: f.get("label") or f["id"] for f in case["facts"]}
res["worked_example"] = {"line": line, "sims": dict(sorted(sims.items(), key=lambda kv: -kv[1]))}
(Path(__file__).parent / "recall_sensitivity.json").write_text(json.dumps(res, indent=1))
print(json.dumps({k: v for k, v in res.items() if k != "worked_example"}, indent=0))
print([(k, round(v, 3), label[k]) for k, v in list(res["worked_example"]["sims"].items())[:12]])

import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
plt.rcParams.update({"font.family": "serif", "font.size": 6.5, "axes.spines.top": False, "axes.spines.right": False, "pdf.fonttype": 42})
items = list(res["worked_example"]["sims"].items())[:12][::-1]
kinds = {f["id"]: f.get("kind") for f in case["facts"]}
fig, ax = plt.subplots(figsize=(3.4, 2.3))
ax.barh([label[k][:38] for k, _ in items], [v for _, v in items], color=["#c0392b" if kinds[k] == "risk" else "#8a8f98" for k, _ in items])
for x, lab in ((0.76, "floor"), (0.78, "risk"), (0.83, "clearly asked")):
    ax.axvline(x, color="k", lw=0.6, ls=":")
    ax.text(x + 0.002, -0.9, lab, fontsize=5.5, rotation=90, va="bottom")
ax.set_xlim(0.6, 0.85)
ax.set_xlabel("best probe similarity")
fig.tight_layout(pad=0.3)
fig.savefig(REPO / "papers/figures/fig_recall_example.pdf", bbox_inches="tight")
