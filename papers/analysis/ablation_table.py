"""Feature ablation of brain v2 (depression held-out scripts, seeds 11 and 23): one row per version, same metrics as the held-out tables,
plus per-conversation composite with a paired bootstrap difference against v2 on the same script and seed."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from analyses import RES, boot_ci, convs, per_conv_metrics  # noqa: E402
import metrics  # noqa: E402

SEEDS = {11, 23}
rows = {}
base = {(c["conv"], c["seed"]): c for c in convs("v2", "mdd_01") if c["seed"] in SEEDS}
for vid, name in (("v0", "previous Twin (v0)"), ("v2", "v2, all features"), ("v2nr", "no decision rubric"), ("v2nc", "no sentence checks"),
                  ("v2nm", "no conversation memory"), ("v2nh", "keyword-only recall")):
    cs = [c for c in convs(vid, "mdd_01") if c["seed"] in SEEDS]
    if not cs:
        continue
    m = metrics.compute(cs)
    keys = sorted(set(base) & {(c["conv"], c["seed"]) for c in cs})
    by = {(c["conv"], c["seed"]): c for c in cs}
    diff = [(metrics.compute([by[k]])["composite"] or 0) - (metrics.compute([base[k]])["composite"] or 0) for k in keys]
    rows[vid] = {"name": name, "runs": len(cs), "turns": m["turns"], "composite": round(m["composite"], 3), "fidelity": round(m["fidelity"], 3),
                 "top2": round(m["top2_share"], 3), "portrayal_fails": m["portrayal_fails"], "jailbreak_fails": m["jailbreak_fails"],
                 "si_fidelity_fails": m["si_fidelity_fails"], "invented": m["invented"],
                 "resistance_ok": round(m["resistance_ok"], 3), "fallbacks": m["fallbacks"],
                 "words": round(sum(per_conv_metrics(c)["words"] for c in cs) / len(cs), 1),
                 "diff_vs_v2": boot_ci(diff) if vid != "v2" else None}
(Path(__file__).parent / "ablation.json").write_text(json.dumps(rows, indent=1))
for r in rows.values():
    print(r)
