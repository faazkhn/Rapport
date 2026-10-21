"""Checkpoint 2: a blind A/B page, 10 held-out doctor lines, v0's reply vs the latest version's, sides shuffled. Static, local only.
Usage: server/patient-service/.venv/bin/python tools/learning/ab_page.py [--b <vid>] -> docs/ab/index.html
The owner fills it in; nothing here records or guesses a choice.
"""
import argparse
import html
import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import loop  # noqa: E402

OUT = loop.REPO / "docs/ab/index.html"


def pairs(a: str, b: str, n: int = 10, seed: int = 21) -> list[dict]:
    ea, eb = ({(c["conv"], t["turn"]): t for c in loop.load_eval(v) for t in c["turns"]} for v in (a, b))
    keys = [k for k in ea if k in eb and ea[k]["reply"]["utterance"].strip() and eb[k]["reply"]["utterance"].strip()
            and ea[k]["reply"]["utterance"] != eb[k]["reply"]["utterance"]]
    rnd = random.Random(seed)
    by_conv = {}
    for k in keys:
        by_conv.setdefault(k[0], []).append(k)
    picked = []
    while len(picked) < n and any(by_conv.values()):  # spread over conversations
        for conv in sorted(by_conv):
            if by_conv[conv] and len(picked) < n:
                picked.append(by_conv[conv].pop(rnd.randrange(len(by_conv[conv]))))
    out = []
    for k in picked:
        flip = rnd.random() < 0.5
        x, y = (eb[k], ea[k]) if flip else (ea[k], eb[k])
        out.append({"conv": k[0], "turn": k[1], "doctor": x["doctor"], "A": x["reply"]["utterance"], "B": y["reply"]["utterance"],
                    "key": {"A": b if flip else a, "B": a if flip else b}})
    return out


def page(ps: list[dict], a: str, b: str) -> str:
    rows = "".join(
        f'<tr><td>{i + 1}.</td><td class="doc">Doctor: {html.escape(p["doctor"])}<br><small>{html.escape(p["conv"])}, turn {p["turn"]}</small></td>'
        f'<td><label><input type="radio" name="q{i}" value="A"> <b>A</b></label><p>{html.escape(p["A"])}</p></td>'
        f'<td><label><input type="radio" name="q{i}" value="B"> <b>B</b></label><p>{html.escape(p["B"])}</p></td></tr>'
        for i, p in enumerate(ps))
    key = "\n".join(f"Pair {i + 1}: A = {p['key']['A']}, B = {p['key']['B']}" for i, p in enumerate(ps))
    return f"""<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Patient replies A/B</title>
<style>body{{font-family:system-ui;margin:24px;background:#fbfbf8;color:#1c2b2a;max-width:1100px}}td{{padding:8px;border-bottom:1px solid #ddd;vertical-align:top}}
td.doc{{width:32%;color:#444}}p{{margin:6px 0 0}}#tally{{font-weight:600;margin:16px 0}}</style>
<h1>Patient replies: blind A/B test (Checkpoint 2)</h1>
<p>Ten held-out doctor lines (never used for learning). For each, pick the reply that sounds more like a real, tired 24-year-old patient
in an Indian outpatient clinic. Sides are shuffled. Clinical content is draft. Nothing is saved or sent anywhere; write the tally down.</p>
<table>{rows}</table>
<button onclick="tally()">Count my choices</button><div id="tally"></div>
<details><summary>Answer key (open only after choosing)</summary><pre>{html.escape(key)}</pre></details>
<script>
const KEY={json.dumps([p["key"] for p in ps])};
function tally(){{let n={{}},done=0;KEY.forEach((k,i)=>{{const c=document.querySelector(`input[name=q${{i}}]:checked`);if(c){{done++;n[k[c.value]]=(n[k[c.value]]||0)+1}}}});
document.getElementById('tally').textContent=`${{done}}/10 answered. `+Object.entries(n).map(([v,c])=>`${{v}}: ${{c}}`).join(', ');}}
</script>"""


def main():
    import learning
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", default="v0")
    ap.add_argument("--b", default=None, help="default: the live version, or the newest evaluated one if v0 is still live")
    x = ap.parse_args()
    b = x.b or (learning.current()["id"] if learning.current()["id"] != x.a else [v for v in learning.versions() if v.get("scores")][-1]["id"])
    ps = pairs(x.a, b)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(page(ps, x.a, b))
    print(f"wrote {OUT}: {len(ps)} pairs, {x.a} vs {b}")


if __name__ == "__main__":
    main()
