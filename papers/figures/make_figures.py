"""Figures for the four Rapport papers, drawn only from measured results in the repo (and the local stills and service logs).
Usage: server/patient-service/.venv/bin/python papers/figures/make_figures.py  -> papers/figures/*.pdf
"""
import json
import re
import statistics as st
from collections import Counter
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
V = REPO / "server/patient-service/learned/versions"
RES = REPO / "tests/llm-eval/results/learning"
C0, C2 = "#8a8f98", "#1f6f8b"  # v0 grey, v2 teal
plt.rcParams.update({"font.family": "serif", "font.size": 8, "axes.titlesize": 8, "axes.labelsize": 8, "legend.fontsize": 7,
                     "xtick.labelsize": 7, "ytick.labelsize": 7, "axes.spines.top": False, "axes.spines.right": False,
                     "pdf.fonttype": 42, "savefig.bbox": "tight", "savefig.pad_inches": 0.02})
W1 = 3.45  # IEEE single column, inches


def runs(vid):
    return json.loads((V / f"{vid}.json").read_text())["scores_by_run"]


def heldout():
    metrics = [("composite", "Composite"), ("resistance_ok", "Resistance\nok"), ("top2_share", "Top-2 share\n(lower: varied)"),
               ("behaviour_entropy", "Behaviour\nentropy")]
    fig, axes = plt.subplots(1, 2, figsize=(7.1, 2.0), sharey=True)
    for ax, case, title in zip(axes, ("mdd_01", "alc_01"), ("Depression (mdd_01)", "Alcohol withdrawal (alc_01)")):
        x = np.arange(len(metrics))
        for off, vid, col in ((-0.18, "v0", C0), (0.18, "v2", C2)):
            r = [s for k, s in runs(vid).items() if k.startswith(case)]
            vals = [[s[m] for s in r] for m, _ in metrics]
            ax.bar(x + off, [st.mean(v) for v in vals], 0.34, color=col, label=vid if case == "mdd_01" else None)
            for i, v in enumerate(vals):
                ax.scatter([x[i] + off] * len(v), v, s=6, color="black", zorder=3, linewidths=0)
        ax.set_xticks(x, [m[1] for m in metrics])
        ax.set_title(title)
        ax.set_ylim(0, 1.05)
    axes[0].set_ylabel("Score (mean of 3 seeds; dots = seeds)")
    axes[0].legend(frameon=False, loc="upper right")
    fig.savefig(OUT / "fig_heldout.pdf")
    plt.close(fig)


def turns_of(vid, case):
    for f in sorted(RES.glob(f"{vid}.{case}.s*.jsonl")):
        for c in (json.loads(x) for x in f.read_text().splitlines() if x.strip()):
            yield f, c


def behaviours():
    order = ["answers_plainly", "guarded_short", "minimises", "deflects", "vague_timeline", "asks_back", "tearful_disclosure",
             "answers_different_question", "hostile", "complies", "complies_without_engaging", "denies", "tangential"]
    fig, ax = plt.subplots(figsize=(W1, 1.9))
    cmap = plt.get_cmap("tab20")
    for row, (vid, case) in enumerate([("v0", "mdd_01"), ("v2", "mdd_01"), ("v0", "alc_01"), ("v2", "alc_01")]):
        cnt = Counter(t["reply"].get("behaviour", "answers_plainly") for _, c in turns_of(vid, case) for t in c["turns"])
        n, left = sum(cnt.values()), 0
        for i, b in enumerate(order):
            w = cnt.get(b, 0) / n
            ax.barh(row, w, left=left, color=cmap(i), label=b.replace("_", " ") if row == 0 else None, height=0.7)
            left += w
    ax.set_yticks(range(4), ["v0 depression", "v2 depression", "v0 alcohol", "v2 alcohol"])
    ax.invert_yaxis()
    ax.set_xlabel("Share of held-out turns (3 seeds)")
    ax.set_xlim(0, 1)
    ax.legend(ncol=3, frameon=False, bbox_to_anchor=(0.5, -0.32), loc="upper center", fontsize=6)
    fig.savefig(OUT / "fig_behaviours.pdf")
    plt.close(fig)


def trust():
    fig, ax = plt.subplots(figsize=(W1, 1.9))
    for vid, col in (("v0", C0), ("v2", C2)):
        for conv, ls, lab in (("01_gold_standard", "-", "kind doctor"), ("04_judgmental", "--", "judgmental doctor")):
            for f, c in turns_of(vid, "mdd_01"):
                if c["conv"] == conv and f.name.endswith("s11.jsonl"):
                    tr = [c["turns"][0]["state_before"]["trust"]] + [t["state_after"]["trust"] for t in c["turns"]]
                    ax.plot(range(len(tr)), tr, ls, color=col, label=f"{vid}, {lab}", lw=1.3)
    ax.axhline(55, color="#c0392b", lw=0.7, ls=":")
    ax.text(0.2, 56.5, "death-wish memory opens (trust 55)", fontsize=6, color="#c0392b")
    ax.set_xlabel("Turn")
    ax.set_ylabel("Trust (0-100)")
    ax.legend(frameon=False, fontsize=6, ncol=2, loc="lower right")
    fig.savefig(OUT / "fig_trust.pdf")
    plt.close(fig)


def recall_front():
    dev = [(0.045, 0.787), (0.070, 0.813), (0.127, 0.907), (0.204, 0.960), (0.344, 1.000)]  # tune_recall dev front (2026-11-14)
    fig, ax = plt.subplots(figsize=(W1, 2.1))
    ax.plot([d[0] for d in dev], [d[1] for d in dev], "o-", color="#bbbbbb", ms=3, label="hybrid, dev half (tuning front)")
    pts = {"keywords only (v0), test": (0.061, 0.351, C0), "hybrid, chosen point, test": (0.152, 0.727, C2),
           "hybrid + hand-set heads, test": (0.212, 0.779, "#d35400")}
    for lab, (x, y, col) in pts.items():
        ax.scatter([x], [y], color=col, s=22, zorder=3, label=lab)
    ax.annotate("", xy=(0.152, 0.727), xytext=(0.127, 0.907), arrowprops=dict(arrowstyle="->", color=C2, lw=0.9))
    ax.text(0.135, 0.82, "dev to test", fontsize=6, color=C2)
    ax.axhline(0.95, color="#c0392b", lw=0.7, ls=":")
    ax.text(0.005, 0.958, "gate: 95%", fontsize=6, color="#c0392b")
    ax.set_xlabel("Risk false hits (non-risk lines touching a risk fact)")
    ax.set_ylabel("Risk-fact recall")
    ax.set_xlim(0, 0.37)
    ax.set_ylim(0.3, 1.03)
    ax.legend(frameon=False, fontsize=6, loc="lower right")
    fig.savefig(OUT / "fig_recall_front.pdf")
    plt.close(fig)


def latency():
    def load(name):
        xs = []
        for f in [REPO / "tests/overnight" / f"service_{name}.log", REPO / "tests/overnight/rerun" / f"service_{name}.log"]:
            if f.exists():  # GPU-exclusive turns only: the morning re-run shared the GPU after 08:06:51
                xs += [json.loads(m.group(2))["audio_start_ms"] for m in re.finditer(r"^(\S+ \S+),\d+ INFO turn \d+ timing (\{.*\})", f.read_text(), re.M)
                       if "rerun" not in str(f) or m.group(1) < "2026-11-14 08:06:51"]
        return sorted(x for x in xs if x is not None)
    fig, ax = plt.subplots(figsize=(W1, 1.9))
    for name, col, lab in (("v0", C0, "v0"), ("v2", C2, "v2"), ("q4", "#e67e22", "Qwen3.5-4B (v2)"), ("q9", "#8e44ad", "Qwen3.5-9B (v2)")):
        xs = load(name)
        if xs:
            ax.plot(np.array(xs) / 1000, np.arange(1, len(xs) + 1) / len(xs), color=col, lw=1.3, label=f"{lab} (n={len(xs)}, p50 {xs[len(xs) // 2] / 1000:.2f} s)")
    ax.set_xlabel("Doctor stops to patient audio ready (s)")
    ax.set_ylabel("Share of turns")
    ax.legend(frameon=False, fontsize=6, loc="lower right")
    fig.savefig(OUT / "fig_latency.pdf")
    plt.close(fig)


def luminance():
    bodies = [("female_20s_a", "Ananya"), ("male_20s_a", "Arjun"), ("female_20s_b", "Amber"), ("male_30s_a", "Realistic\nMan")]
    base = [0.285, 0.435, 0.392, 0.444]
    same = [0.386, 0.604, 0.471, 0.591]
    after = [0.488, 0.525, 0.543, 0.538]
    fig, ax = plt.subplots(figsize=(W1, 1.8))
    x = np.arange(4)
    for off, vals, col, lab in ((-0.25, base, "#cccccc", "baseline (wide shot)"), (0, same, C0, "new camera, old light"), (0.25, after, C2, "after")):
        ax.bar(x + off, vals, 0.24, color=col, label=lab)
    ax.axhspan(0.45, 0.60, color="#27ae60", alpha=0.12, lw=0)
    ax.text(3.45, 0.61, "target", fontsize=6, color="#27ae60", ha="right")
    ax.set_xticks(x, [b[1] for b in bodies])
    ax.set_ylabel("Face mean luminance Y")
    ax.set_ylim(0, 0.7)
    ax.legend(frameon=False, fontsize=6, ncol=3, loc="upper center", bbox_to_anchor=(0.5, 1.2))
    fig.savefig(OUT / "fig_luminance.pdf")
    plt.close(fig)


def stills():
    d = REPO / "docs/media/v0.3"
    pairs = [(d / "baseline/female_20s_a.png", "Baseline (v0.2)"), (d / "after/female_20s_a.png", "v0.3")]
    if not all(p.exists() for p, _ in pairs):
        return
    fig, axes = plt.subplots(1, 2, figsize=(7.1, 2.05))
    for ax, (p, t) in zip(axes, pairs):
        im = Image.open(p).convert("RGB")
        im.thumbnail((960, 540))
        ax.imshow(im)
        ax.set_title(t)
        ax.axis("off")
    fig.savefig(OUT / "fig_stills.pdf", dpi=220)
    plt.close(fig)
    sheet = d / "after/sheet.jpg"
    if sheet.exists():
        im = Image.open(sheet).convert("RGB")
        im.thumbnail((1400, 800))
        fig, ax = plt.subplots(figsize=(3.45, 1.95))
        ax.imshow(im)
        ax.axis("off")
        fig.savefig(OUT / "fig_bodies.pdf", dpi=260)
        plt.close(fig)


def body_strip():
    p = REPO / "docs/media/v0.3/life/body_language_male_20s_a.jpg"
    if not p.exists():
        return
    im = Image.open(p).convert("RGB")
    W, H = im.size
    rows = ["neutral", "listen", "think", "angry", "anxious", "sad", "ashamed", "happy", "confused", "suspicious", "flat"]
    left, rh, cw = int(W * 0.064), H / len(rows), (W - int(W * 0.064)) / 8
    pick = [("neutral", 0), ("angry", 3), ("anxious", 3), ("sad", 4), ("ashamed", 3), ("happy", 3), ("confused", 3)]
    fig, axes = plt.subplots(1, len(pick), figsize=(7.1, 1.25))
    for ax, (r, col) in zip(axes, pick):
        i = rows.index(r)
        ax.imshow(im.crop((int(left + col * cw), int(i * rh), int(left + (col + 1) * cw), int((i + 1) * rh))))
        ax.set_title(r, fontsize=7)
        ax.axis("off")
    fig.savefig(OUT / "fig_body_language.pdf", dpi=220)
    plt.close(fig)


def turn_timeline():
    """One spoken turn, median stage times (ms) from the GPU-exclusive service log, v0 and v2 (Table in paper 2)."""
    stages = [("Turn-end detection", 277, 278), ("STT wait", 72, 142), ("LLM first token", 276, 410),
              ("LLM first sentence", 572, 527), ("TTS first audio", 296, 350)]
    fig, ax = plt.subplots(figsize=(7.1, 1.35))
    cols = ["#95a5a6", "#5dade2", "#e67e22", "#f5b041", "#1f6f8b"]
    for row, idx, lab in ((1, 1, "v0"), (0, 2, "v2")):
        left = 0
        for (name, *v), col in zip(stages, cols):
            w = v[idx - 1]
            ax.barh(row, w, left=left, color=col, height=0.55, label=name if row == 1 else None, edgecolor="white", lw=0.5)
            if w > 160:
                ax.text(left + w / 2, row, f"{w}", ha="center", va="center", fontsize=6, color="white")
            left += w
        ax.text(left + 25, row, f"sum {left} ms", va="center", fontsize=6)
    ax.set_yticks([1, 0], ["v0", "v2"])
    ax.set_xlabel("Milliseconds after the doctor stops speaking (medians per stage; their sum differs from the p50 of the total)")
    ax.legend(ncol=5, frameon=False, fontsize=6, bbox_to_anchor=(0.5, 1.35), loc="upper center")
    ax.set_xlim(0, 1900)
    fig.savefig(OUT / "fig_turn_timeline.pdf")
    plt.close(fig)


def recall_byfact():
    d = json.loads((REPO / "tests/overnight/rerun/recall_test.json").read_text())["risk_by_fact"]
    names = {"f_anger_home": "anger at home", "f_no_plan_no_means": "no plan or means", "f_passive_si": "death wish",
             "f_withdrawal_seizure": "withdrawal fit", "f_no_means": "no means", "f_no_plan_no_attempt": "no plan or attempt",
             "f_current_si": "current suicidal thoughts", "f_means": "means at home", "f_terrace": "the terrace night", "f_risk": "harm to self or others"}
    rows = sorted(((int(v.split("/")[0]) / int(v.split("/")[1]), k, v) for k, v in d.items()), reverse=True)
    fig, ax = plt.subplots(figsize=(W1, 2.4))
    y = np.arange(len(rows))
    ax.barh(y, [r[0] for r in rows], color=C2, height=0.6)
    for i, (frac, k, v) in enumerate(rows):
        ax.text(frac + 0.01, i, v, va="center", fontsize=6)
    ax.set_yticks(y, [f"{k.split('/')[0]}: {names.get(k.split('/')[1], k)}" for _, k, _ in rows], fontsize=6)
    ax.invert_yaxis()
    ax.axvline(0.95, color="#c0392b", lw=0.7, ls=":")
    ax.set_xlim(0, 1.12)
    ax.set_xlabel("Recall on the test half (lines found / lines asking)")
    fig.savefig(OUT / "fig_recall_byfact.pdf")
    plt.close(fig)


def debrief_weights():
    parts = [("Risk", 30), ("Observation (MSE)", 20), ("Diagnosis", 13), ("Management", 13), ("History", 12), ("Communication", 12)][::-1]
    fig, ax = plt.subplots(figsize=(W1, 1.5))
    cols = ["#c0392b" if n == "Risk" else "#1f6f8b" for n, _ in parts]
    ax.barh([n for n, _ in parts], [w for _, w in parts], color=cols)
    for k, (_, w) in enumerate(parts):
        ax.text(w + 0.6, k, str(w), va="center", fontsize=6)
    ax.set_xlim(0, 34)
    ax.set_xlabel("points (of 100)")
    fig.savefig(OUT / "fig_debrief_weights.pdf")
    plt.close(fig)


if __name__ == "__main__":
    for f in (heldout, behaviours, trust, recall_front, latency, luminance, stills, body_strip, turn_timeline, recall_byfact,
              debrief_weights):
        f()
        print("ok", f.__name__)
