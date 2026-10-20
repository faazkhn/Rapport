"""Reply realism numbers for a run_eval results file: hesitation rate, length, behaviour variety, phrase repetition.

Usage: python3 tools/llm_eval/reply_stats.py tests/llm-eval/results/<label>.jsonl [--selftest]
Repetition = share of replies that reuse a 3-word phrase from an earlier reply in the same conversation.
"""
import json
import re
import sys
from collections import Counter, defaultdict


def trigrams(text: str) -> set:
    w = re.findall(r"[a-z']+", text.lower())
    return {tuple(w[i:i + 3]) for i in range(len(w) - 2)}


def stats(rows: list[dict]) -> dict:
    by_conv = defaultdict(list)
    for r in rows:
        by_conv[(r.get("conv"), r.get("run"))].append(r)
    reps = 0
    for turns in by_conv.values():
        seen = set()
        for r in sorted(turns, key=lambda r: r["turn"]):
            g = trigrams(r["reply"]["utterance"])
            reps += bool(g & seen)
            seen |= g
    utts = [r["reply"]["utterance"] for r in rows]
    n = len(utts) or 1
    return {"replies": len(utts), "ellipsis_rate": round(sum("..." in u or "…" in u for u in utts) / n, 3),
            "mean_words": round(sum(len(u.split()) for u in utts) / n, 1),
            "behaviours": dict(Counter(r["reply"].get("behaviour", "?") for r in rows).most_common()),
            "repetition_rate": round(reps / n, 3)}


def _selftest():
    rows = [{"conv": "a", "run": 0, "turn": 1, "reply": {"utterance": "I am just tired...", "behaviour": "minimises"}},
            {"conv": "a", "run": 0, "turn": 2, "reply": {"utterance": "I am just tired, really.", "behaviour": "minimises"}},
            {"conv": "b", "run": 0, "turn": 1, "reply": {"utterance": "I am just tired.", "behaviour": "answers_plainly"}}]
    s = stats(rows)
    assert s["ellipsis_rate"] == 0.333 and s["repetition_rate"] == 0.333 and s["behaviours"] == {"minimises": 2, "answers_plainly": 1}
    print("selftest ok")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        _selftest()
    else:
        convs = [json.loads(line) for line in open(sys.argv[1], encoding="utf-8") if line.strip()]
        rows = [{**t, "conv": c["conv"], "run": c["run"]} for c in convs if c.get("kind") == "conv" for t in c["turns"]]
        print(json.dumps(stats(rows), indent=1))
