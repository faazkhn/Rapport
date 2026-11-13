"""Re-tune the hybrid recall thresholds on the dev half of the paraphrase set (never the test half) and write them to
data/brain/recall.json, which twin.py reads. Rule: the highest risk recall on dev, then the fewest false and extra hits, then the
highest overall recall. Usage: server/patient-service/.venv/bin/python tools/brain/tune_recall.py
"""
import itertools
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "server/patient-service"))
sys.path.insert(0, str(REPO / "tools"))
import brain  # noqa: E402
import recall_bench as rb  # noqa: E402
import twin  # noqa: E402

twin._tuned["done"] = True  # the grid sets the thresholds itself
_embed, _seen = twin.embed, {}


def _cached(texts):  # each doctor line is embedded once for the whole grid
    if len(texts) != 1:
        return _embed(texts)
    if texts[0] not in _seen:
        _seen[texts[0]] = _embed(texts)
    return _seen[texts[0]]


twin.embed = _cached

KEYS = ("SIM_HIT", "SIM_RISK", "SIM_FLOOR", "SIM_NEAR", "RISK_NEAR", "RISK_MARGIN")
GRID = ([0.80, 0.83, 0.86], [0.72, 0.75, 0.78, 0.81], [0.72, 0.76, 0.80], [0.02, 0.04], [0.66, 0.70, 0.74], [0.04, 0.08])

res = []
for combo in itertools.product(*GRID):
    if combo[1] > combo[0]:
        continue
    for k, v in zip(KEYS, combo):
        setattr(twin, k, v)
    r = rb.run("dev")
    res.append((r["risk_recall"], -(r["none_false_hit"] + 0.3 * r["extra_per_line"]), r["fact_recall"], combo, r))
best_risk = max(x[0] for x in res)
pick = max((x for x in res if x[0] >= best_risk - 0.01), key=lambda x: (x[1], x[2]))
out = {"version": "0.1", "status": "draft", "note": "Hybrid recall thresholds tuned on the dev half of tests/recall/paraphrase_set.jsonl by tools/brain/tune_recall.py.",
       **{k.lower(): v for k, v in zip(KEYS, pick[3])},
       "dev": {k: pick[4][k] for k in ("fact_recall", "risk_recall", "none_false_hit", "extra_per_line")}}
(brain.DATA_DIR / "brain/recall.json").write_text(json.dumps(out, indent=1) + "\n")
print(json.dumps(out, indent=1))
