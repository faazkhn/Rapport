"""The learning loop (Phase E). Everything runs against the local llama-server; nothing leaves the Mac.
  loop.py heldout <vid> [--seeds 7,11,23] [--case mdd_01] [--judge-url http://127.0.0.1:8081/v1]
                              held-out evaluation of a version (scripted lines, fixed seeds) + judges -> version scores (seed 7 on
                              mdd_01 is the version's stored score; other seeds and cases are saved under scores_by_run)
  loop.py round [--turns 8] [--budget 40]
                              self-play with the live version -> gate + invented-fact judge -> library (L1) -> GEPA over the realism
                              rules (L3) -> new version -> held-out eval -> promoted only if better and safety-clean
  loop.py rescore             recompute every version's scores from its saved eval (after hand-reviewing judge flags)
  loop.py decide <vid>        apply the promotion rule to <vid> against the live version
  loop.py report              metrics table (markdown) + docs/learning/curves.svg
Run with server/patient-service/.venv/bin/python. Rollback: server/patient-service/learning.py rollback <vid>.
"""
import argparse
import json
import random
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import yaml
from openai import OpenAI

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "server/patient-service"))
sys.path.insert(0, str(HERE))
import brain  # noqa: E402
import judges  # noqa: E402
import learning  # noqa: E402
import metrics  # noqa: E402
import prompt_only  # noqa: E402
import selfplay  # noqa: E402
import twin  # noqa: E402

CASE = "mdd_01"
SEED = 7
RESULTS = REPO / "tests/llm-eval/results/learning"
REVIEWED = HERE / "reviewed_flags.json"


class Seeded:
    """Same sampling seed for every version, so held-out differences come from the version, not the dice."""
    def __init__(self, client, seed=SEED):
        self.client, self.seed = client, seed
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, **kw):
        kw["extra_body"] = {**kw.get("extra_body", {}), "seed": self.seed}
        return self.client.chat.completions.create(**kw)


def reviewed() -> dict:
    d = json.loads(REVIEWED.read_text()) if REVIEWED.exists() else {}
    return {u: v["verdict"] for u, v in d.items()}


def judge_turn(client, case, t):
    j = judges.invented(client, case, t)
    j["resistance_ok"] = judges.resistance(client, case, t)
    j["principles_ok"] = judges.principles(client, case.get("principles", []), t)
    j["disclosed"] = judges.disclosed(client, case, t)
    return j


def evaluate(version: dict, client, judge=None, seed=SEED) -> dict:
    """judge: a client for a different local model than the patient's (a model rates its own lines too kindly); default the same."""
    seeded, judge = Seeded(client, seed), judge or client
    gen = prompt_only.generate_reply if version.get("prompt_only") else brain.generate_reply
    convs = []
    for p in sorted((REPO / "tests/llm-eval" / CASE).glob("*.yaml")):
        conv = yaml.safe_load(p.read_text())
        case = brain.load_case(CASE, conv["variant"])
        state = {**case["state_start"], **conv.get("start_state", {})}
        msgs, turns, mind = [], [], None
        for i, line in enumerate(conv["turns"], 1):
            msgs.append({"role": "doctor", "text": line})
            t0 = time.perf_counter()
            r = gen({"case_id": CASE, "variant": conv["variant"], "messages": msgs, "state": state, "elapsed_min": i * 1.0,
                                      "twin": mind}, client=seeded, version=version)
            new, mind = r["state"], r["twin"]  # one brain: the same trust step, mood, memory and events as a live session
            turns.append({"turn": i, "doctor": line, "state_before": state, "state_after": new, "recalled": r["recalled"],
                          "recalled_ref": twin.recall(case, state["trust"], line),  # common reference (hybrid recall) for every version
                          "reply": {k: v for k, v in r.items() if k not in ("meta", "twin")}, "meta": r["meta"],
                          "wall_ms": round((time.perf_counter() - t0) * 1000)})
            if r["utterance"]:
                msgs.append({"role": "patient", "text": r["utterance"]})
            state = new
        convs.append({"kind": "conv", "conv": p.stem, "type": conv["type"], "variant": conv["variant"], "run": 0,
                      "expect": conv.get("expect", {}), "turns": turns})
        print(f"  {version['id']} {p.stem}: {len(turns)} turns", flush=True)
    out = RESULTS / f"{version['id']}{run_tag(seed)}.jsonl"
    RESULTS.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(json.dumps(c, ensure_ascii=False) + "\n" for c in convs))  # saved before judging: a judge failure never loses a run
    jobs = [(c, t) for c in convs for t in c["turns"]]
    with ThreadPoolExecutor(2) as ex:
        verdicts = list(ex.map(lambda j: judge_turn(judge, brain.load_case(CASE, j[0]["variant"]), j[1]), jobs))
    for (c, t), v in zip(jobs, verdicts):
        t["judge"] = v
    out.write_text("".join(json.dumps(c, ensure_ascii=False) + "\n" for c in convs))
    return metrics.compute(convs, reviewed())


def run_tag(seed) -> str:
    """File suffix of a held-out run; the original run (mdd_01, seed 7) has none."""
    return "" if (CASE, seed) == ("mdd_01", SEED) else f".{CASE}.s{seed}"


def load_eval(vid: str) -> list[dict]:
    return [json.loads(x) for x in (RESULTS / f"{vid}.jsonl").read_text().splitlines()]


def cmd_eval(vid, client, judge=None, seeds=(SEED,)):
    v = learning.load_version(vid)
    for seed in seeds:
        s = evaluate(v, client, judge, seed)
        v.setdefault("scores_by_run", {})[f"{CASE}.s{seed}"] = s
        if not run_tag(seed):
            v["scores"] = s
        learning.save_version(v)
        print(seed, json.dumps(s, indent=1), flush=True)


def scores_of(vid, client):
    v = learning.load_version(vid)
    if not v.get("scores"):
        cmd_eval(vid, client)
        v = learning.load_version(vid)
    return v["scores"]


def cmd_round(client, turns, budget, judge=None):
    import optimize  # gepa only needed here
    cur = learning.current()
    n = max(int(v["id"].lstrip("v")) for v in learning.versions() if v["id"].lstrip("v").isdigit()) + 1
    print(f"round -> v{n} (live {cur['id']})", flush=True)
    held = selfplay.held_out_lines(CASE)
    sessions = [selfplay.run(cur, p, client, turns, CASE, ("female", "male")[i % 2], held) for i, p in enumerate(selfplay.PERSONAS)]
    added = passed = 0
    for s in sessions:
        for t in s:
            case = brain.load_case(CASE, t["variant"])
            history = [m["text"] for m in t["messages"] if m["role"] == "patient"]
            if learning.gate(t["reply"]["utterance"], t["meta"], case, t["state_before"], history):
                continue
            passed += 1
            j = judges.invented(judge or client, case, t)
            if j["unsupported_claims"] or j["broke_character"]:
                continue
            learning.add_experience(CASE, {"doctor": t["doctor"], "utterance": t["reply"]["utterance"], "engagement": t["state_before"]["engagement"],
                                           "trust": t["state_before"]["trust"], "behaviour": t["reply"]["behaviour"], "source": "self_play",
                                           "judged": True, "persona": t["persona"], "variant": t["variant"], "from_version": cur["id"]},
                                    consent=False)
            added += 1
    n_turns = sum(len(s) for s in sessions)
    upto = len(learning.library(CASE))
    print(f"  self-play {n_turns} turns, gate passed {passed}, added {added}, library {upto}", flush=True)
    ctx = [{"messages": t["messages"], "state": t["state_before"], "variant": t["variant"], "recalled": t["recalled"], "twin": t.get("twin")}
           for s in sessions for t in s]
    random.Random(n).shuffle(ctx)
    base = {**{k: v for k, v in cur.items() if k not in ("scores", "scores_by_run", "decision", "status")}, "examples_k": 2, "library_upto": upto}
    best, info = optimize.propose(base, ctx, client, budget, seed=n, judge=judge)
    print(f"  GEPA {info}", flush=True)
    doc = {**base, "id": f"v{n}", "parent": cur["id"], "created": time.strftime("%Y-%m-%d %H:%M"), "status": "candidate",
           "realism_rules": None if best == brain.REALISM_RULES else best, "scores": {},
           "selfplay": {"turns": n_turns, "gate_passed": passed, "added": added, "personas": list(selfplay.PERSONAS)}, "gepa": info,
           "notes": f"Round {n}: library {upto} entries (+{added}), examples_k 2, realism rules " + ("rewritten by GEPA" if info["changed"] else "unchanged")}
    learning.save_version(doc)
    decide(f"v{n}", client, judge)


SEEDS = (11, 23, 42)


def runs_of(vid, client, judge) -> list[dict]:
    """Held-out scores for each seed in SEEDS (cached in the version file)."""
    v = learning.load_version(vid)
    by = v.setdefault("scores_by_run", {})
    for seed in SEEDS:
        if f"{CASE}.s{seed}" not in by:
            by[f"{CASE}.s{seed}"] = evaluate(v, client, judge, seed)
            learning.save_version(v)
    return [by[f"{CASE}.s{seed}"] for seed in SEEDS]


def decide(vid, client, judge=None):
    """Promote only if the candidate passes every safety gate on every seed and beats the live version on the held-out set
    across three seeds (higher mean composite and higher on at least two seeds)."""
    v = learning.load_version(vid)
    cur = learning.current()
    ok, why = metrics.promote_seeds(runs_of(vid, client, judge), runs_of(cur["id"], client, judge))
    v = learning.load_version(vid)
    v["status"], v["decision"] = ("live" if ok else "rejected"), why
    learning.save_version(v)
    if ok:
        prev = learning.load_version(cur["id"])
        learning.save_version({**prev, "status": "superseded"})
        learning.set_current(vid)
    print(f"  {vid}: {'PROMOTED' if ok else 'rejected'} ({why})", flush=True)
    return ok


def cmd_rescore():
    rv = reviewed()
    for v in learning.versions():
        if (RESULTS / f"{v['id']}.jsonl").exists():
            v["scores"] = metrics.compute(load_eval(v["id"]), rv)
            learning.save_version(v)
            print(v["id"], {k: v["scores"][k] for k in ("composite", "invented", "jailbreak_fails", "portrayal_fails")})


COLS = [("fidelity", "Unmentioned-symptom fidelity ↑"), ("banned_rate", "Banned-word rate ↓"), ("repetition", "Repetition ↓"),
        ("length_fit", "Length fits state ↑"), ("resistance_ok", "Resistance appropriate ↑"), ("composite", "Composite ↑")]
SAFETY = [("invented", "Invented facts"), ("jailbreak_fails", "Jailbreak fails"), ("portrayal_fails", "Portrayal fails")]


def cmd_report():
    vs = [v for v in learning.versions() if v.get("scores")]
    print("| Version | Status | Library | " + " | ".join(c[1] for c in COLS + SAFETY) + " | Mean words | Fallbacks |")
    print("|---|---|---|" + "---|" * (len(COLS) + len(SAFETY) + 2))
    for v in vs:
        s = v["scores"]
        cells = [f"{s[k]:.3f}" if s.get(k) is not None else "–" for k, _ in COLS] + [str(s[k]) for k, _ in SAFETY]
        print(f"| {v['id']} | {v.get('status')} | {v.get('library_upto') or 0} | " + " | ".join(cells)
              + f" | {s['mean_words']:.1f} | {s['fallbacks']} |")
    out = REPO / "docs/learning/curves.svg"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(svg(vs))
    print(f"\nwrote {out}")


def svg(vs) -> str:
    """Small multiples, one per metric, versions on x, 0..1 on y; live versions as filled dots."""
    w, h, pad, cols = 220, 150, 30, 3
    rows = -(-len(COLS + SAFETY) // cols)
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{cols * w}" height="{rows * h}" font-family="system-ui,sans-serif" font-size="11">',
             f'<rect width="100%" height="100%" fill="#fbfbf8"/>']
    for n, (k, label) in enumerate(COLS + SAFETY):
        ox, oy = (n % cols) * w, (n // cols) * h
        vals = [v["scores"].get(k) for v in vs]
        top = 1.0 if k not in dict(SAFETY) else max(1, *(x or 0 for x in vals))
        x = lambda i: ox + pad + i * (w - 2 * pad) / max(1, len(vs) - 1)  # noqa: E731
        y = lambda val: oy + h - pad - (val / top) * (h - 2 * pad - 10)  # noqa: E731
        parts.append(f'<text x="{ox + pad}" y="{oy + 16}" fill="#1c2b2a" font-weight="600">{label}</text>')
        parts.append(f'<line x1="{ox + pad}" y1="{y(0)}" x2="{ox + w - pad}" y2="{y(0)}" stroke="#ccc"/>')
        parts.append(f'<text x="{ox + 4}" y="{y(top) + 4}" fill="#888">{top:g}</text><text x="{ox + 4}" y="{y(0) + 4}" fill="#888">0</text>')
        pts = [(x(i), y(val)) for i, val in enumerate(vals) if val is not None]
        if len(pts) > 1:
            parts.append('<polyline fill="none" stroke="#2a6f6a" stroke-width="2" points="' + " ".join(f"{a:.1f},{b:.1f}" for a, b in pts) + '"/>')
        for i, v in enumerate(vs):
            if vals[i] is None:
                continue
            live = v.get("status") in ("live", "superseded") or v["id"] == "v0"
            parts.append(f'<circle cx="{x(i):.1f}" cy="{y(vals[i]):.1f}" r="3.5" fill="{"#2a6f6a" if live else "#fbfbf8"}" stroke="#2a6f6a"/>')
            parts.append(f'<text x="{x(i) - 6:.1f}" y="{oy + h - 10}" fill="#555">{v["id"]}</text>')
    parts.append("</svg>")
    return "\n".join(parts)


def main():
    global CASE
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["heldout", "round", "rescore", "decide", "report"])
    ap.add_argument("vid", nargs="?")
    ap.add_argument("--turns", type=int, default=8)
    ap.add_argument("--budget", type=int, default=40)
    ap.add_argument("--url", default="http://127.0.0.1:8080/v1")
    ap.add_argument("--judge-url", default=None, help="llama-server with a different model for the judges")
    ap.add_argument("--seeds", default=str(SEED))
    ap.add_argument("--case", default=CASE)
    a = ap.parse_args()
    CASE = a.case
    client = OpenAI(base_url=a.url, api_key="local", timeout=180, max_retries=1)
    judge = OpenAI(base_url=a.judge_url, api_key="local", timeout=180, max_retries=1) if a.judge_url else None
    {"heldout": lambda: cmd_eval(a.vid, client, judge, [int(x) for x in a.seeds.split(",")]), "round": lambda: cmd_round(client, a.turns, a.budget, judge), "rescore": cmd_rescore,
     "decide": lambda: decide(a.vid, client, judge), "report": cmd_report}[a.cmd]()


if __name__ == "__main__":
    main()
