"""Every value paper B prints, collected from the committed results, as one JSON object on stdout for osaudit.

Only the values the paper reports are kept (no PR curves, no paper A results), so a printed number matches its own value and not one
of thousands of neighbours. Regenerate with:
  osaudit run $(for f in $(python papers/paperB_jhir/values.py --inputs); do echo --input $f; done) \
      -o papers/paperB_jhir/values.json -- python papers/paperB_jhir/values.py
"""
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OV = "tests/overnight/"
INPUTS = [OV + "recall_baselines.json", OV + "recall_llm.json", OV + "recall_test_lexical.json", OV + "rerun/recall_test_hand.json",
          OV + "riskprobe/summary.json", OV + "moves_label.log", "papers/analysis/results.json", "papers/analysis/recall_extra.json",
          "papers/analysis/recall_sensitivity.json", "papers/analysis/new_results.json", "tests/brain/eval_moves-v1.json",
          "tests/brain/gen_moves.log"] + [OV + f"recall_{k}_writer_{w}.json" for w in ("qwen4b", "gemma2b") for k in ("baselines", "llm")]


def load(p):
    return json.loads((REPO / p).read_text())


def frac(s):
    """'76/114 = 0.667' -> 76 / 114."""
    a, b = s.split(" = ")[0].split("/")
    return int(a) / int(b)


def method(m):
    return {"risk_auroc": m["risk"]["auroc"], "risk_auprc": m["risk"]["auprc"], "all_auroc": m["all"]["auroc"][0],
            "prevalence": m["risk"]["prevalence"], "test": m["test"], "dev_risk_false_hit": m["dev"]["risk_false_hit"],
            "ms_per_line": m["ms_per_line"]}


def baselines(b):
    return {"risk_pairs": {h: b["methods"]["hybrid"][h]["risk_n"] for h in ("dev", "test")}, "methods": {k: method(m) for k, m in b["methods"].items()}, "deployed": b["deployed_hybrid"],
            "deployed_filtered": b.get("deployed_hybrid_filtered")}


def llm(x):
    return {"test": x["test"], "ms_p50": x["ms_p50"], "ms_p90": x["ms_p90"], "cascade_floor": x["cascade"]["floor"],
            "cascade_test": x["cascade"]["test"], "cascade_sweep_test": x["cascade"]["sweep"]["test"]}


def main():
    res = load("papers/analysis/results.json")["recall"]
    new = load("papers/analysis/new_results.json")
    sens = load("papers/analysis/recall_sensitivity.json")
    label = re.search(r"labelled (\d+)/\d+ lines \((\d+) from logs\); judge agrees with the generator's target on ([\d.]+)%",
                      (REPO / OV / "moves_label.log").read_text())
    out = {
        "benchmark": res["benchmark"],
        "keywords_test": {k: v for k, v in load(OV + "recall_test_lexical.json").items() if k in
                          ("fact_recall", "risk_recall", "risk_false_hit", "none_false_hit", "risk_n")},
        "hybrid_test": {"all": res["test_hybrid"]["all"], "per_case": res["test_hybrid"]["per_case"], "risk_ci": res["test_risk_recall_ci"],
                        "easy": frac(res["test_hybrid"]["hard_vs_easy"]["easy"]), "hard": frac(res["test_hybrid"]["hard_vs_easy"]["hard"]),
                        "keywords_easy": frac(res["test_lexical"]["hard_vs_easy"]["easy"]),
                        "keywords_hard": frac(res["test_lexical"]["hard_vs_easy"]["hard"])},
        "hands_test": {k: v for k, v in load(OV + "rerun/recall_test_hand.json").items() if k in
                       ("fact_recall", "risk_recall", "risk_false_hit", "none_false_hit")},
        "deployed": {"dev": sens["shipped"]["dev"], "test": sens["shipped"]["test"], "settings": sens["shipped"]["settings"]},
        "cutoff_sweep": [{"cutoff": float(k), **v} for k, v in sorted(sens["risk_cutoff_sweep"].items(), key=lambda kv: float(kv[0]))],
        "recall_only_tune": sens["overnight_recall_only_tune"],
        "ranks": load("papers/analysis/recall_extra.json"),
        "baselines": baselines(load(OV + "recall_baselines.json")),
        "filter": load(OV + "recall_baselines.json")["filter"],
        "llm": llm(load(OV + "recall_llm.json")),
        "writers": {w: {"baselines": baselines(load(OV + f"recall_baselines_writer_{w}.json")),
                        "llm": llm(load(OV + f"recall_llm_writer_{w}.json")),
                        "hinglish": new[f"B.writer.{w}"]["hinglish"]} for w in ("qwen4b", "gemma2b")},
        "riskprobe_v2": load(OV + "riskprobe/summary.json")["v2"]["pooled"],
        "classifier": {"generated_lines": int(re.search(r"wrote (\d+) lines", (REPO / "tests/brain/gen_moves.log").read_text())[1]),
                       "labelled_lines": int(label[1]), "log_lines": int(label[2]), "judge_agrees": float(label[3]) / 100,
                       "micro_f1": {k: v["micro_f1"] for k, v in load("tests/brain/eval_moves-v1.json").items() if isinstance(v, dict)}},
    }
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    print("\n".join(INPUTS)) if sys.argv[1:] == ["--inputs"] else main()
