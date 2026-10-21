"""Run the scripted learner conversations (tests/llm-eval/<case>/*.yaml) against the patient LLM through brain.generate_reply,
N runs each, and write every turn to JSONL for judge.py and score.py. Also probes TTFT and tokens/s by streaming.
Usage: server/patient-service/.venv/bin/python tools/llm_eval/run_eval.py --label gemma-4-E4B [--runs 5] [--url http://127.0.0.1:8080/v1]
"""
import argparse
import json
import sys
import time
from pathlib import Path

import httpx
import yaml

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "server/patient-service"))
import brain  # noqa: E402
from openai import OpenAI  # noqa: E402


def run_conv(conv, case_id, client, model):
    case = brain.load_case(case_id, conv["variant"])
    state = {**case["state_start"], **conv.get("start_state", {})}
    msgs, out = [], []
    for i, line in enumerate(conv["turns"], 1):
        msgs.append({"role": "doctor", "text": line})
        t = time.perf_counter()
        r = brain.generate_reply({"case_id": case_id, "variant": conv["variant"], "messages": msgs, "state": state,
                                  "elapsed_min": i * 1.0, "model": model}, client=client)
        dt = round((time.perf_counter() - t) * 1000)
        new = brain.apply_turn(state, r)
        out.append({"turn": i, "doctor": line, "state_before": state, "state_after": new, "reply": {k: v for k, v in r.items() if k != "meta"},
                    "meta": r["meta"], "wall_ms": dt})
        if r["utterance"]:
            msgs.append({"role": "patient", "text": r["utterance"]})
        state = new
    return out


def probe(url, n=8):
    """Stream n real patient prompts; TTFT = first content token, tok/s from llama-server timings."""
    case = brain.load_case("mdd_01", "female")
    st = case["state_start"]
    lines = ["Hello, I'm Dr. Faaz. What brings you in today?", "How have you been sleeping?", "How is your mood?",
             "Do you still enjoy things?", "How is work?", "Any alcohol?", "How's your appetite?", "Tell me about your family."]
    ttft, tps = [], []
    for line in lines[:n]:
        allowed = [f["id"] for f in brain.allowed_facts(case, st["trust"])]
        kw = brain.llm_kwargs("local", brain.build_messages(case, st, [{"role": "doctor", "text": line}]),
                              brain.build_reply_schema(case, allowed, brain.allowed_actions(case, st["trust"])), "patient_reply", 0)
        body = {k: v for k, v in kw.items() if k != "extra_body"} | kw["extra_body"] | {"stream": True}
        t0, first, timings = time.perf_counter(), None, None
        with httpx.stream("POST", url + "/chat/completions", json=body, timeout=120) as r:
            for ln in r.iter_lines():
                if not ln.startswith("data: ") or ln == "data: [DONE]":
                    continue
                ch = json.loads(ln[6:])
                if first is None and ch.get("choices") and ch["choices"][0]["delta"].get("content"):
                    first = time.perf_counter()
                timings = ch.get("timings") or timings
        ttft.append((first - t0) * 1000)
        if timings:
            tps.append(timings["predicted_per_second"])
    return {"ttft_ms_median": round(sorted(ttft)[len(ttft) // 2]), "tok_s_median": round(sorted(tps)[len(tps) // 2], 1) if tps else None}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", required=True)
    ap.add_argument("--runs", type=int, default=5)
    ap.add_argument("--case", default="mdd_01")
    ap.add_argument("--url", default="http://127.0.0.1:8080/v1")
    ap.add_argument("--only", default="", help="comma list of yaml stems")
    ap.add_argument("--no-probe", action="store_true", help="skip the speed probe (meaningless on a shared llama-server)")
    ap.add_argument("--timeout", type=float, default=120, help="seconds per request; raise it when llama-server is shared")
    a = ap.parse_args()
    client = OpenAI(base_url=a.url, api_key="local", timeout=a.timeout, max_retries=0)
    out_dir = REPO / "tests/llm-eval/results"
    out_dir.mkdir(parents=True, exist_ok=True)
    perf = {} if a.no_probe else probe(a.url)
    print("probe", perf, flush=True)
    convs = sorted((REPO / "tests/llm-eval" / a.case).glob("*.yaml"))
    if a.only:
        convs = [c for c in convs if c.stem in a.only.split(",")]
    path = out_dir / f"{a.label}.jsonl"
    with path.open("w") as f:
        f.write(json.dumps({"kind": "perf", "label": a.label, **perf}) + "\n")
        for c in convs:
            conv = yaml.safe_load(c.read_text())
            for run in range(a.runs):
                t = time.perf_counter()
                turns = run_conv(conv, a.case, client, "local")
                f.write(json.dumps({"kind": "conv", "label": a.label, "conv": c.stem, "type": conv["type"], "variant": conv["variant"],
                                    "run": run, "expect": conv.get("expect", {}), "turns": turns}) + "\n")
                f.flush()
                print(f"{c.stem} run {run}: {len(turns)} turns {time.perf_counter() - t:.0f}s "
                      f"final trust {turns[-1]['state_after']['trust']:.0f} fallbacks {sum(x['meta']['fallback'] for x in turns)}", flush=True)
    print("wrote", path)


if __name__ == "__main__":
    main()
