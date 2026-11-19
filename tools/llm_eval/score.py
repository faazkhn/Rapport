"""Score bake-off results: rule-based checks per conversation + E2 metrics + A6 proxies + judge flags. No LLM rates realism (C8).
Usage: .venv/bin/python tools/llm_eval/score.py tests/llm-eval/results/<label>.jsonl [...]  -> prints a markdown table + per-check detail
"""
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

BREAK = re.compile(r"\b(AI|A\.I\.|artificial intelligence|language model|chatbot|chat bot|system prompt|prompt|instructions|simulation|"
                   r"case file|my file|JSON|algorithm|as your doctor|I am a doctor|I'm a doctor|prescribe)\b", re.I)
ROBOT = re.compile(r"(great question|thank you for asking|thanks for asking|I understand your concern|I appreciate|certainly|absolutely|"
                   r"I'm here to help|happy to help|how can I help|feel free|rest assured|in summary|to summari[sz]e|"
                   r"depress|anhedoni|ideation|psychomotor|dysphori|SSRI|serotonin|diagnos|DSM|symptom)", re.I)
SI = re.compile(r"(not wake up|wake up in the morning|end (it|my life)|kill (my)?self|suicid|\bdie\b|\bdying\b|not be here|"
                r"better off (dead|without me)|disappear|no point (in )?living|life (isn't|is not) worth)", re.I)
COLLOQUIAL = re.compile(r"\b(tired|down|low|empty|heavy|numb|exhausted|nothing (feels|matters)|can't be bothered|don't know|blank|flat|drained)\b", re.I)


def words(s):
    return re.findall(r"[A-Za-z']+", s)


def max_words(eng):
    return 15 if eng < 30 else 30 if eng < 60 else 45 if eng < 80 else 60


def styled(t):
    u = t["reply"]["utterance"]
    return len(words(u)) <= max_words(t["state_before"]["engagement"]) and not ROBOT.search(u)


def score(path):
    rows = [json.loads(l) for l in Path(path).read_text().splitlines()]
    perf = next((r for r in rows if r["kind"] == "perf"), {})
    convs = [r for r in rows if r["kind"] == "conv"]
    jp = Path(path).with_suffix(".judge.jsonl")
    judge = [json.loads(l) for l in jp.read_text().splitlines()] if jp.exists() else None
    fails = defaultdict(list)
    turns = [t for c in convs for t in c["turns"]]
    n = len(turns)
    schema_ok = sum(not t["meta"]["fallback"] and t["meta"].get("attempts", 1) == 1 for t in turns)
    guard_facts = sum(any(d["kind"] == "fact" for d in t["meta"]["guard_dropped"]) for t in turns)
    banned = sum(any(d["kind"] == "banned_word" for d in t["meta"]["guard_dropped"]) for t in turns)
    for c in convs:
        e, key = c["expect"], f"{c['conv']}#{c['run']}"
        revealed = {f for t in c["turns"] for f in t["reply"]["revealed_fact_ids"]}
        final = c["turns"][-1]["state_after"]
        for f in e.get("must_not_reveal", []):
            if f in revealed:
                fails["leak"].append(f"{key} revealed {f}")
        for f in e.get("must_reveal_all", []):
            if f not in revealed:
                fails["must_reveal"].append(f"{key} missing {f}")
        if e.get("must_reveal_any") and not revealed & set(e["must_reveal_any"]):
            fails["must_reveal"].append(f"{key} none of {e['must_reveal_any']}")
        if "final_trust_min" in e and final["trust"] < e["final_trust_min"]:
            fails["trust"].append(f"{key} final trust {final['trust']:.0f} < {e['final_trust_min']}")
        if "final_trust_max" in e and final["trust"] > e["final_trust_max"]:
            fails["trust"].append(f"{key} final trust {final['trust']:.0f} > {e['final_trust_max']}")
        tagged = {i for t in c["turns"] for i in t["reply"]["doctor_intents"]}
        for i in e.get("required_intent_any", []):
            if i not in tagged:
                fails["intent"].append(f"{key} never tagged {i}")
        for ti, act in (e.get("exam_action_turns") or {}).items():
            if c["turns"][int(ti) - 1]["reply"]["exam_action"] != act:
                fails["exam_action"].append(f"{key} turn {ti} expected {act}, got {c['turns'][int(ti) - 1]['reply']['exam_action']}")
        for ti, act in (e.get("no_exam_action_turns") or {}).items():
            if c["turns"][int(ti) - 1]["reply"]["exam_action"] == act:
                fails["exam_action"].append(f"{key} turn {ti} did {act} below trust")
        for t in c["turns"]:
            u = t["reply"]["utterance"]
            si_ok = "f_passive_si" in t["meta"]["allowed_fact_ids"] and "ask_suicidal_ideation" in t["reply"]["doctor_intents"]
            if SI.search(u) and not si_ok and c["type"] != "risk_disclosure":
                fails["si_unprompted"].append(f"{key} t{t['turn']}: {u}")
            if BREAK.search(u):
                fails["break_character"].append(f"{key} t{t['turn']}: {u}")
    # judge flags (accuracy only)
    jflags = [j for j in judge or [] if j["unsupported_claims"]]
    jbreak = [j for j in judge or [] if j["broke_character"]]
    # E2 metrics
    utts = [t["reply"]["utterance"] for t in turns]
    toks = [w.lower() for u in utts for w in words(u)]
    distinct1 = len(set(toks)) / max(1, len(toks))
    robot = sum(bool(ROBOT.search(u)) for u in utts) / max(1, n)
    decay = [c for c in convs if c["type"] == "instruction_decay"]
    early = [styled(t) for c in decay for t in c["turns"][:5]]
    late = [styled(t) for c in decay for t in c["turns"][19:25]]
    gold = [c for c in convs if c["type"].startswith("gold")]
    unmentioned = []
    for c in gold:  # resistance: share of facts allowed by the end that never came out
        allowed = set(c["turns"][-1]["meta"]["allowed_fact_ids"])
        rev = {f for t in c["turns"] for f in t["reply"]["revealed_fact_ids"]}
        unmentioned.append(len(allowed - rev) / max(1, len(allowed)))
    low_eng = [len(words(t["reply"]["utterance"])) for t in turns if t["state_before"]["engagement"] < 30]
    a6 = {
        "colloquial_mood_words": sum(bool(COLLOQUIAL.search(u)) for u in utts) / max(1, n),
        "mean_words_low_engagement": sum(low_eng) / len(low_eng) if low_eng else None,
        "si_only_when_asked": not fails["si_unprompted"],
        "si_disclosed_when_asked_kindly": not any("f_passive_si" in x for x in fails["must_reveal"]),
        "no_dsm_words_after_guard": not any(re.search(r"depress|ideation|anhedoni|DSM", u, re.I) for u in utts),
    }
    return {
        "label": convs[0]["label"] if convs else path, **perf, "turns": n, "schema_valid": schema_ok / max(1, n),
        "guard_fact_drops": guard_facts, "banned_word_sentences": banned,
        "judge_flags": len(jflags) if judge is not None else None, "judge_breaks": len(jbreak) if judge is not None else None,
        "wrong_symptom_ratio": len(jflags) / max(1, n) if judge is not None else None,
        "unmentioned_symptom_ratio": sum(unmentioned) / max(1, len(unmentioned)), "robot_ratio": robot, "distinct1": distinct1,
        "style_early": sum(early) / max(1, len(early)), "style_late": sum(late) / max(1, len(late)),
        "a6": a6, "fails": {k: v for k, v in fails.items()}, "judge_flagged": jflags, "judge_broke": jbreak,
    }


def main():
    res = [score(p) for p in sys.argv[1:]]
    print("| Model | Size | tok/s | TTFT ms | Schema valid | Judge flags | Rule fails | Break char | Robot ratio | Distinct-1 | Style t1-5 → t20-25 |")
    print("|---|---|---|---|---|---|---|---|---|---|---|")
    for r in res:
        rule = sum(len(v) for k, v in r["fails"].items() if k != "break_character")
        print(f"| {r['label']} | | {r.get('tok_s_median')} | {r.get('ttft_ms_median')} | {r['schema_valid']:.1%} | {r['judge_flags']} | {rule} | "
              f"{len(r['fails'].get('break_character', []))}+{r['judge_breaks']} | {r['robot_ratio']:.1%} | {r['distinct1']:.2f} | "
              f"{r['style_early']:.0%} → {r['style_late']:.0%} |")
    for r in res:
        print(f"\n## {r['label']}\nA6: {json.dumps(r['a6'])}\nunmentioned-symptom ratio (gold): {r['unmentioned_symptom_ratio']:.2f}; "
              f"guard fact drops {r['guard_fact_drops']}, banned-word sentences {r['banned_word_sentences']}")
        for k, v in r["fails"].items():
            print(f"- {k} ({len(v)}): " + "; ".join(v[:6]))
        for j in r["judge_flagged"][:40]:
            print(f"  JUDGE {j['conv']}#{j['run']} t{j['turn']}: {j['utterance']!r} -> {j['unsupported_claims']}")
        for j in r["judge_broke"][:20]:
            print(f"  BREAK {j['conv']}#{j['run']} t{j['turn']}: {j['utterance']!r} ({j['why']})")


if __name__ == "__main__":
    main()
