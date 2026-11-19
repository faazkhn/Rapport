"""Markdown tables for docs/GATES_v0.3.md from the result files: held-out per version, case and seed (plus means), paraphrase recall,
and latency. Usage: server/patient-service/.venv/bin/python tools/overnight/gates_tables.py [--versions v0,v2]
"""
import argparse
import json
import statistics as st
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
V = REPO / "server/patient-service/learned/versions"
OUT = REPO / "tests/overnight"
KEYS = [("composite", "Composite"), ("fidelity", "Fidelity"), ("resistance_ok", "Resistance ok"), ("invented", "Invented flags*"),
        ("jailbreak_fails", "Jailbreak"), ("portrayal_fails", "Portrayal"), ("si_fidelity_fails", "SI not disclosed"),
        ("behaviours_used", "Behaviours"), ("top2_share", "Top-2 share"), ("behaviour_entropy", "Entropy"), ("trigram_repeat", "Trigram rep."),
        ("mean_words", "Words")]


def fmt(x):
    return "–" if x is None else f"{x:.3f}" if isinstance(x, float) else str(x)


def heldout(vids):
    print("| Version | Case | Seed | " + " | ".join(k[1] for k in KEYS) + " |")
    print("|---|---|---|" + "---|" * len(KEYS))
    means = {}
    for vid in vids:
        runs = json.loads((V / f"{vid}.json").read_text()).get("scores_by_run", {})
        for run, s in sorted(runs.items()):
            case, seed = run.rsplit(".s", 1)
            print(f"| {vid} | {case} | {seed} | " + " | ".join(fmt(s.get(k)) for k, _ in KEYS) + " |")
            means.setdefault((vid, case), []).append(s)
    print("\nMeans over seeds:\n")
    print("| Version | Case | " + " | ".join(k[1] for k in KEYS) + " |")
    print("|---|---|" + "---|" * len(KEYS))
    for (vid, case), ss in sorted(means.items(), key=lambda x: (x[0][1], x[0][0])):
        cells = []
        for k, _ in KEYS:
            xs = [s.get(k) for s in ss if s.get(k) is not None]
            summed = k in ("invented", "jailbreak_fails", "portrayal_fails", "si_fidelity_fails")
            cells.append("–" if not xs else fmt(sum(xs)) if summed else fmt(float(st.mean(xs))))
        print(f"| {vid} | {case} | " + " | ".join(cells) + " |")
    print("\n*Invented-fact, jailbreak and portrayal counts are sums over seeds in the means table; judge flags are before hand review.")


def recall():
    for name, p in (("v0 (tags)", OUT / "recall_test_lexical.json"), ("v2 (hybrid)", OUT / "rerun/recall_test.json")):
        if p.exists():
            d = json.loads(p.read_text())
            print(f"| {name} | {d['fact_recall']:.1%} | {d['risk_recall']:.1%} | {d.get('risk_false_hit', float('nan')):.1%} | "
                  f"{d['none_false_hit']:.1%} | {d['ms_p50']} ms |")


def latency():
    for name in ("v0", "v2"):
        p = OUT / f"rerun/latency_{name}.json"
        if not p.exists():
            print(f"| {name} | (missing) |")
            continue
        d = json.loads(p.read_text())
        t = [x for x in d.get("turns", []) if x.get("audio_start_ms") is not None]
        pct = lambda k, q: round(sorted(x[k] for x in t if x.get(k) is not None)[int(q * (len(t) - 1))]) if t else None  # noqa: E731
        print(f"| {name} | {len(t)} | {pct('audio_start_ms', .5)} | {pct('audio_start_ms', .9)} | {pct('client_lag_ms', .5)} | "
              f"{pct('llm_ttft_ms', .5)} | {pct('llm_first_sentence_ms', .5)} | {pct('tts_first_chunk_ms', .5)} | {len(d.get('early_endpoint', []))} |")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--versions", default="v0,v2")
    a = ap.parse_args()
    print("## Held-out\n")
    heldout(a.versions.split(","))
    print("\n## Recall (test half)\n\n| Brain | All facts | Risk facts | Risk false hits | 'None' lines hit | Time |\n|---|---|---|---|---|---|")
    recall()
    print("\n## Latency\n\n| Brain | Turns | Audio ready p50 | p90 | Client lag p50 | LLM first token p50 | First sentence p50 | TTS first chunk p50 | Early endpoints |\n|---|---|---|---|---|---|---|---|---|")
    latency()
