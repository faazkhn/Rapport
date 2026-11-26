"""Dev-half and classifier figures paper B reports that no earlier script saved, recomputed from the committed code and data.

Prints one JSON object on stdout (no timings, so a rerun prints the same). Regenerate with:
  osaudit run --input tests/recall/paraphrase_set.jsonl --input tests/brain/train_labelled.jsonl \
      --input unity/PsychSim/Assets/StreamingAssets/data -o papers/paper/extra.json \
      -- server/patient-service/.venv/bin/python papers/paper/extra.py
"""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPO / "server/patient-service"), str(REPO / "tools"), str(REPO / "tools/brain")]
import brain  # noqa: E402
import hand_weights  # noqa: E402
import recall_baselines as rbl  # noqa: E402
import recall_bench as rb  # noqa: E402
import twin  # noqa: E402

CASES = {c: brain.load_case(c) for c in ("mdd_01", "alc_01", "ward_01", "ward_02")}
DEV = rb.rows("dev")


def top_k(encoder, probes_of, k):
    """Share of dev-half (line, expected memory) pairs whose memory ranks within the top k, each memory scored by its best probe."""
    hits = n = 0
    for cid, case in CASES.items():
        pr = [(f["id"], p) for f in case["facts"] for p in probes_of(f)]
        rows = [r for r in DEV if r["case"] == cid and r["expect"]]
        for r, sims in zip(rows, rbl.by_max(case, pr, encoder([p for _, p in pr]), encoder([r["line"] for r in rows]))):
            order = sorted(sims, key=sims.get, reverse=True)
            hits += sum(order.index(f) < k for f in r["expect"])
            n += len(r["expect"])
    return hits / n


def hand_written(f):
    """The probes written by hand for a memory (no generated ones), with its tags and its own text, as twin-0.2 embedded them."""
    return twin._probes(f, {})


PROBE_SETS = {  # supplement Table S2 (dev half): what each memory is represented by
    "memory_text": lambda f: [f["text"]],
    "text_label_tags": lambda f: [f["text"], *([f["label"]] if f.get("label") else []), *(t for t in f.get("activation_tags", []) if "{" not in t)],
    "hand_written_questions": lambda f: f.get("recall_probes", []) or [f["text"]],
    "questions_tags_text": hand_written,
}


def probe_counts():
    """Hand-written and generated probes per memory, over the four cases."""
    hand, gen = [], []
    for cid, case in CASES.items():
        g = twin.generated_probes(cid)
        hand += [len(f.get("recall_probes", [])) for f in case["facts"]]
        gen += [len(g.get(f["id"], [])) for f in case["facts"]]
    return {"hand_written": {"min": min(hand), "max": max(hand)},
            "generated": {"min": min(gen), "max": max(gen), "median": sorted(gen)[len(gen) // 2]}}


def main():
    twin._load_tuned()
    enc = {"minilm": rbl.encoder("minilm"), "bge_small": rbl.encoder("bge-small")}
    rows_of = {"minilm": list(PROBE_SETS), "bge_small": ["hand_written_questions", "questions_tags_text"]}
    ablation = {m: {p: {"top1": top_k(enc[m], PROBE_SETS[p], 1), "top3": top_k(enc[m], PROBE_SETS[p], 3)} for p in ps} for m, ps in rows_of.items()}
    heads = {k: v for k, v in rb.run("dev", hand=True).items() if k in ("risk_recall", "risk_false_hit")}
    rows = [json.loads(x) for x in (REPO / "tests/brain/train_labelled.jsonl").read_text().splitlines() if x.strip()]
    tester = [r for r in rows if r.get("source") == "gen:provocateur"]
    print(json.dumps({
        "dev_rank_ablation": ablation,
        "heads_dev": heads,
        "heads_threshold": twin.topic_weights()["thresholds"],
        "head_examples": {k: len(v) for k, v in hand_weights.PROTOTYPES.items()},
        "probes_per_memory": probe_counts(),
        "tester_lines": len(tester),
        "tester_judge_agrees": sum(r["target"] in (r.get("labels") or []) for r in tester) / len(tester),
    }, indent=1))


if __name__ == "__main__":
    main()
