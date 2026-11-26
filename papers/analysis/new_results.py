"""Tables and numbers for papers A and B from the 2026-11-18 runs (tools/overnight/queue5.sh). Missing results print as a red [pending]
in the papers, so both papers build before, during and after the queue.
Writes papers/paperA_jms/gen/*.tex, papers/paperB/gen/*.tex, papers/analysis/new_results.json and fig_pr_curves.pdf.
Usage: server/patient-service/.venv/bin/python papers/analysis/new_results.py
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from analyses import REPO, boot_ci, convs, per_conv_metrics  # noqa: E402
import metrics  # noqa: E402  (tools/learning, on the path via analyses)

A, B = REPO / "papers/paperA_jms/gen", REPO / "papers/paperB/gen"
OV = REPO / "tests/overnight"
P = r"\pending"
ARMS = [("v0", "Earlier Twin (v0)"), ("v2", "Twin (v2)"), ("p0", "Prompt-only")]


def wrap(spec, head, rows, width=r"\linewidth", env="tabularx"):
    """A whole table body (TeX cannot \\input rows inside a tabular)."""
    return (rf"\begin{{{env}}}{{{width}}}{{{spec}}}" + "\n\\toprule\n" + head + r"\\" + "\n\\midrule\n" + "\n".join(rows)
            + f"\n\\bottomrule\n\\end{{{env}}}\n")


def f3(x):
    return P if x is None else f"{x:.3f}"


def ci(t):
    return P if not t else f"{t[0]:.3f} [{t[1]:.3f}, {t[2]:.3f}]"


def pct(x, d=1):
    return P if x is None else f"{100 * x:.{d}f}\\%"


# ---------- paper A ----------

def arm_stats(vid, case):
    cs = convs(vid, case)
    if not cs:
        return None
    comp = [x for x in (metrics.compute([c])["composite"] for c in cs) if x is not None]
    pooled = metrics.compute(cs)
    pcm = [per_conv_metrics(c) for c in cs]
    seeds = sorted({c["seed"] for c in cs})
    judged = all("disclosed" in t.get("judge", {}) for c in cs for t in c["turns"])
    return {"runs": len(cs), "seeds": seeds, "composite": boot_ci(comp), "fidelity": pooled["fidelity"],
            "resistance_ok": pooled["resistance_ok"], "top2": boot_ci([m["top2"] for m in pcm]), "words": boot_ci([m["words"] for m in pcm]),
            "invented": pooled["invented"], "jailbreak": pooled["jailbreak_fails"], "portrayal": pooled["portrayal_fails"],
            "si_fails": pooled["si_fidelity_fails"], "fallbacks": pooled["fallbacks"], "turns": pooled["turns"],
            "judged_leaks": pooled["judged_locked_leaks"] if judged else None, "banned_rate": pooled["banned_rate"]}


def paired(a, b, case):
    x = {(c["conv"], c["seed"]): c for c in convs(a, case)}
    y = {(c["conv"], c["seed"]): c for c in convs(b, case)}
    keys = sorted(set(x) & set(y))
    if not keys:
        return None
    return boot_ci([(metrics.compute([x[k]])["composite"] or 0) - (metrics.compute([y[k]])["composite"] or 0) for k in keys]) + (len(keys),)


def baseline_table(res):
    rows = []
    for case, name in (("mdd_01", "Depression (12 scripts)"), ("alc_01", "Alcohol withdrawal (2 scripts)")):
        s = {v: arm_stats(v, case) for v, _ in ARMS}
        res[f"A.{case}"] = s
        g = lambda v, k, fmt=str: P if s[v] is None or s[v][k] is None else fmt(s[v][k])  # noqa: E731
        rows.append(rf"\multicolumn{{4}}{{@{{}}l}}{{\emph{{{name}}}}}\\")
        rows.append("Runs (seeds) & " + " & ".join(P if s[v] is None else f"{s[v]['runs']} ({len(s[v]['seeds'])})" for v, _ in ARMS) + r"\\")
        rows.append(r"Composite, per conversation [95\% CI] & " + " & ".join(g(v, "composite", ci) for v, _ in ARMS) + r"\\")
        rows.append("Fidelity (pooled) & " + " & ".join(g(v, "fidelity", f3) for v, _ in ARMS) + r"\\")
        rows.append("Resistance appropriate (judge, pooled) & " + " & ".join(g(v, "resistance_ok", f3) for v, _ in ARMS) + r"\\")
        rows.append(r"Banned clinical word said (share of turns) & " + " & ".join(g(v, "banned_rate", pct) for v, _ in ARMS) + r"\\")
        rows.append("Locked memory disclosed (disclosure judge, turns) & " + " & ".join(g(v, "judged_leaks") for v, _ in ARMS) + r"\\")
        rows.append("Jailbreak failures & " + " & ".join(g(v, "jailbreak") for v, _ in ARMS) + r"\\")
        rows.append("Portrayal failures & " + " & ".join(g(v, "portrayal") for v, _ in ARMS) + r"\\")
        rows.append("Death wish not disclosed when due & " + " & ".join(g(v, "si_fails") for v, _ in ARMS) + r"\\")
        rows.append("Made-up-fact flags (judge, not hand-checked) & " + " & ".join(g(v, "invented") for v, _ in ARMS) + r"\\")
        rows.append("Turns (fallback replies) & " + " & ".join(P if s[v] is None else f"{s[v]['turns']} ({s[v]['fallbacks']})" for v, _ in ARMS) + r"\\")
        d2, d0 = paired("v2", "p0", case), paired("v2", "v0", case)
        res[f"A.diff.{case}"] = {"v2_minus_p0": d2, "v2_minus_v0": d0}
        fmtd = lambda d: P if d is None else f"${d[0]:+.3f}$ [${d[1]:+.3f}$, ${d[2]:+.3f}$], {d[3]} pairs"  # noqa: E731
        rows.append(r"Paired difference in composite, v2 $-$ v0 & \multicolumn{3}{l}{" + fmtd(d0) + r"}\\")
        rows.append(r"Paired difference in composite, v2 $-$ prompt-only & \multicolumn{3}{l}{" + fmtd(d2) + r"}\\")
        rows.append(r"\midrule")
    rows.pop()
    (A / "tab_baseline.tex").write_text(wrap("@{}Yccc@{}", "Measure & v0 & v2 & Prompt-only", rows))


def riskprobe_table(res):
    p = OV / "riskprobe/summary.json"
    s = json.loads(p.read_text()) if p.exists() else {}
    res["A.riskprobe"] = s
    rows, short = [], {"v0": "v0", "v2": "v2", "p0": "Prompt-only"}
    for v, name in ARMS:
        x = s.get(v, {}).get("pooled")
        if not x:
            rows.append(f"{short[v]} & " + " & ".join([P] * 4) + r"\\")
            continue
        per = [r.get("missed_judged") for r in s[v]["per_seed"] if r.get("missed_judged") is not None]
        rng = f" ({100 * min(per):.0f}--{100 * max(per):.0f})" if per else ""
        rows.append(f"{short[v]} & {pct(x.get('missed_judged'))}{rng} & {pct(x['missed_self'])} & "
                    f"{pct(x.get('missed_judged_when_recalled'))} ({x['n_when_recalled']}) & "
                    f"{pct(x.get('missed_judged_when_not_recalled'))} ({x['n_when_not_recalled']})" + r"\\")
    (A / "tab_riskprobe.tex").write_text(wrap("@{}lYYYY@{}", "Arm & Missed (judge; range over seeds) & Missed (own report) & "
                                              "Missed when recall matched (n) & Missed when recall did not match (n)", rows))
    rows = []
    cases = {"mdd_01": "Depression", "alc_01": "Alcohol withdrawal", "ward_01": "Ward: wants to go home", "ward_02": "Ward: refuses tablets"}
    for c, name in cases.items():
        rows.append(name + " & " + " & ".join(pct(s.get(v, {}).get("by_case", {}).get(c, {}).get("missed_judged")) for v, _ in ARMS) + r"\\")
    (A / "tab_riskprobe_case.tex").write_text(wrap("@{}Yccc@{}", "Case & v0 & v2 & Prompt-only", rows))


# ---------- paper B ----------
NAMES = {"tags": "Keyword tags (v0)", "bm25": "BM25, probes", "minilm": "MiniLM-L6 (22M)", "e5-small": "e5-small-v2 (33M)",
         "gte-small": "gte-small (33M)", "bge-small": "bge-small (33M)", "bge-base": "bge-base (109M)", "hybrid": "Hybrid, matched cut-off"}


def recall_tables(res):
    p, q = OV / "recall_baselines.json", OV / "recall_llm.json"
    r = json.loads(p.read_text()) if p.exists() else {"methods": {}}
    llm = json.loads(q.read_text()) if q.exists() else {}
    res["B.baselines"] = {k: {kk: vv for kk, vv in v.items() if kk != "pr_curve"} for k, v in r["methods"].items()}
    res["B.llm"] = llm
    tri = lambda t: P if not t else f"{t[0]:.3f} ({t[1]:.2f}--{t[2]:.2f})"  # noqa: E731
    rows = []
    for k, name in NAMES.items():
        m = r["methods"].get(k)
        if not m:
            rows.append(name + " & " + " & ".join([P] * 4) + r"\\")
            continue
        rows.append(f"{name} & {tri(m['risk']['auroc'])} & {tri(m['risk']['auprc'])} & "
                    f"{pct(m['test']['risk_recall'])} & {pct(m['test']['risk_false_hit'])}" + r"\\")
    rows.append(r"\midrule")
    t = llm.get("test", {})
    rows.append(r"Gemma 4 E4B, zero-shot & -- & -- & " + f"{pct(t.get('risk_recall'))} & {pct(t.get('risk_false_hit'))}" + r"\\")
    c = llm.get("cascade", {}).get("test", {})
    rows.append(r"Cascade (hybrid, Gemma) & -- & -- & " + f"{pct(c.get('risk_recall'))} & {pct(c.get('risk_false_hit'))}" + r"\\")
    (B / "tab_baselines.tex").write_text(wrap(r"@{\extracolsep{\fill}}lcccc@{}", r"Method & \begin{tabular}{@{}c@{}}Risk AUROC\\(95\% CI)\end{tabular} & "
                                              r"\begin{tabular}{@{}c@{}}Risk AUPRC\\(95\% CI)\end{tabular} & Recall & False hits", rows, r"\textwidth", "tabular*"))

    rows = []
    for k in ("bm25", "minilm", "e5-small", "gte-small", "bge-small", "bge-base", "hybrid"):
        a, b = r["methods"].get(k), r["methods"].get(k + "+filter")
        if a and b:
            rows.append(f"{NAMES[k]} & {a['risk']['auroc'][0]:.3f} & {b['risk']['auroc'][0]:.3f} & {pct(a['test']['risk_recall'])} & "
                        f"{pct(b['test']['risk_recall'])} & {pct(a['test']['risk_false_hit'])} & {pct(b['test']['risk_false_hit'])}" + r"\\")
    d, f = r.get("deployed_hybrid"), r.get("deployed_hybrid_filtered")
    if d and f:
        rows.append(r"\midrule")
        rows.append(f"Deployed match rules (dev half) & -- & -- & {pct(d['dev']['risk_recall'])} & {pct(f['dev']['risk_recall'])} & "
                    f"{pct(d['dev']['risk_false_hit'])} & {pct(f['dev']['risk_false_hit'])}" + r"\\")
        rows.append(f"Deployed match rules (test half) & -- & -- & {pct(d['test']['risk_recall'])} & {pct(f['test']['risk_recall'])} & "
                    f"{pct(d['test']['risk_false_hit'])} & {pct(f['test']['risk_false_hit'])}" + r"\\")
    (B / "tab_filter.tex").write_text(wrap("@{}Ycccccc@{}", r"Method & \multicolumn{2}{c}{Risk AUROC} & \multicolumn{2}{c}{Risk recall} & "
                                           r"\multicolumn{2}{c}{Risk false hits}\\ & all & filtered & all & filtered & all & filtered",
                                           rows or [r"\multicolumn{7}{c}{\pending}\\"], r"\textwidth"))
    res["B.filter"] = r.get("filter")

    pick = llm.get("cascade", {}).get("floor")
    bold = lambda x, t: rf"\textbf{{{t}}}" if x["floor"] == pick else t  # noqa: E731  (the floor chosen on the dev half)
    rows = [" & ".join(bold(x, t) for t in (f"{x['floor']:.2f}", pct(x['risk_recall']), pct(x['risk_false_hit']), pct(x['share_sent_to_llm'], 0)))
            + r"\\" for x in llm.get("cascade", {}).get("sweep", {}).get("test", [])]
    (B / "tab_cascade.tex").write_text(wrap("@{}Yccc@{}", r"Screen floor & Risk recall & Risk false hits & Lines sent to the LLM",
                                            rows or [r"\multicolumn{4}{c}{\pending}\\"]))
    if r["methods"]:
        pr_figure(r["methods"], llm)


def pr_figure(methods, llm):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(5.2, 3.6))
    for k, style in (("tags", ":"), ("bm25", "--"), ("minilm", "-"), ("e5-small", "-"), ("gte-small", "-"), ("bge-base", "-"), ("hybrid", "-")):
        m = methods.get(k)
        if m and "pr_curve" in m:
            ax.plot(m["pr_curve"]["recall"], m["pr_curve"]["precision"], style, lw=2.2 if k == "hybrid" else 1.1,
                    label="Hybrid (deployed)" if k == "hybrid" else NAMES[k].split(" (")[0])
    if llm.get("test"):
        t = llm["test"]
        ax.plot([t["risk_recall"]], [precision_of(llm)], "k*", ms=11, label="Gemma zero-shot (one point)")
    ax.set_xlabel("Risk recall (test half)")
    ax.set_ylabel("Precision")
    ax.set_xlim(0, 1.02)
    ax.set_ylim(0, 1.02)
    ax.grid(alpha=0.3)
    ax.legend(fontsize=7, loc="lower left")
    fig.tight_layout()
    fig.savefig(REPO / "papers/figures/fig_pr_curves.pdf")


def precision_of(llm):
    """Precision of the LLM's risk answers over (line, risk memory) pairs, from its saved per-line answers."""
    sys.path.insert(0, str(REPO / "tools"))
    import brain
    import recall_bench
    p = OV / "recall_llm_lines.jsonl"
    if not p.exists():
        return float("nan")
    cases = {c: brain.load_case(c) for c in ("mdd_01", "alc_01", "ward_01", "ward_02")}
    exp = {(r["case"], r["line"]): set(r["expect"]) for r in recall_bench.rows("test")}
    tp = fp = 0
    for x in map(json.loads, p.read_text().splitlines()):
        if x["split"] != "test":
            continue
        risk = {f["id"] for f in cases[x["case"]]["facts"] if f.get("kind") == "risk"}
        for f in set(x["ids"]) & risk:
            tp += f in exp[(x["case"], x["line"])]
            fp += f not in exp[(x["case"], x["line"])]
    return tp / max(1, tp + fp)


WRITERS = (("qwen4b", "Qwen3.5-4B"), ("gemma2b", "Gemma 4 E2B"))


def hinglish(name):
    """Risk recall on the writer's code-mixed lines: deployed rules and the zero-shot model."""
    sys.path.insert(0, str(REPO / "tools"))
    import brain
    import twin
    p, q = REPO / f"tests/recall/writer_{name}.jsonl", OV / f"recall_llm_lines_writer_{name}.jsonl"
    if not p.exists():
        return None
    cases = {c: brain.load_case(c) for c in ("mdd_01", "alc_01", "ward_01", "ward_02")}
    risk = {c: {f["id"] for f in cs["facts"] if f.get("kind") == "risk"} for c, cs in cases.items()}
    rows = [r for r in map(json.loads, p.read_text().splitlines()) if r.get("hinglish")]
    llm = {(x["case"], x["line"]): set(x["ids"]) for x in map(json.loads, q.read_text().splitlines()) if x["split"] == "test"} if q.exists() else {}
    pos = [(r, f) for r in rows for f in r["expect"] if f in risk[r["case"]]]
    dep = sum(f in (lambda h: set(h["open"]) | set(h["locked_hit"]))(twin.recall(cases[r["case"]], 100, r["line"])) for r, f in pos)
    got = sum(f in llm.get((r["case"], r["line"]), set()) for r, f in pos)
    return {"lines": len(rows), "risk_pairs": len(pos), "deployed": dep / max(1, len(pos)), "llm": got / max(1, len(pos)) if llm else None}


def writer_table(res):
    data = {}
    for name, _ in WRITERS:
        b, l = OV / f"recall_baselines_writer_{name}.json", OV / f"recall_llm_writer_{name}.json"
        data[name] = (json.loads(b.read_text()) if b.exists() else None, json.loads(l.read_text()) if l.exists() else None)
        res[f"B.writer.{name}"] = {"baselines": {k: {kk: vv for kk, vv in v.items() if kk != "pr_curve"} for k, v in (data[name][0] or {}).get("methods", {}).items()},
                                   "deployed": (data[name][0] or {}).get("deployed_hybrid", {}).get("test"), "llm": data[name][1], "hinglish": hinglish(name)}
    cell = lambda m, w: (P + " & " + P + " & " + P) if not m else f"{m['risk']['auroc'][0]:.3f} & {pct(m['test']['risk_recall'])} & {pct(m['test']['risk_false_hit'])}"  # noqa: E731
    rows = []
    for k in ("tags", "bm25", "bge-small", "bge-base", "gte-small", "hybrid"):
        rows.append(NAMES[k] + " & " + " & ".join(cell((data[n][0] or {}).get("methods", {}).get(k), n) for n, _ in WRITERS) + r"\\")
    rows.append(r"\midrule")
    dep = lambda n: (data[n][0] or {}).get("deployed_hybrid", {}).get("test")  # noqa: E731
    rows.append("Deployed match rules & " + " & ".join(f"-- & {pct(dep(n)['risk_recall'])} & {pct(dep(n)['risk_false_hit'])}" if dep(n) else f"-- & {P} & {P}"
                                                       for n, _ in WRITERS) + r"\\")
    llmc = lambda n: (data[n][1] or {}).get("test")  # noqa: E731
    rows.append("Gemma 4 E4B, zero-shot & " + " & ".join(f"-- & {pct(llmc(n)['risk_recall'])} & {pct(llmc(n)['risk_false_hit'])}" if llmc(n) else f"-- & {P} & {P}"
                                                         for n, _ in WRITERS) + r"\\")
    head = (r"& \multicolumn{3}{c}{Written by " + WRITERS[0][1] + r"} & \multicolumn{3}{c}{Written by " + WRITERS[1][1] + r"}\\ Method & "
            + " & ".join(["AUROC & Recall & FH"] * 2))
    (B / "tab_writers.tex").write_text(wrap(r"@{\extracolsep{\fill}}lcccccc@{}", head, rows, r"\textwidth", "tabular*"))
    hrows = []
    for n, label in WRITERS:
        h = res[f"B.writer.{n}"]["hinglish"]
        hrows.append(f"{label} & " + (f"{h['lines']} & {h['risk_pairs']} & {pct(h['deployed'])} & {pct(h['llm'])}" if h else " & ".join([P] * 4)) + r"\\")
    (B / "tab_hinglish.tex").write_text(wrap("@{}Ycccc@{}", "Writer & Hinglish lines & Risk pairs & Deployed rules & Gemma zero-shot", hrows))


def numbers(res):
    """A few \\newcommand values used in the running text."""
    d = {f"{k}{v}": P for v in ("v0", "v2", "p0") for k in ("Comp", "CompCI", "Leaks", "Jail", "Port", "SIfail", "Turns", "RPmiss", "RPn",
                                                         "RPmissRec", "RPmissNoRec")}
    d |= dict.fromkeys(("WQwenDep", "WQwenLLM", "WGemmaDep", "WGemmaLLM"), P)
    for n, m in (("qwen4b", "Qwen"), ("gemma2b", "Gemma")):
        w = res.get(f"B.writer.{n}", {})
        if w.get("deployed"):
            d[f"W{m}Dep"] = pct(w["deployed"]["risk_recall"])
        if (w.get("llm") or {}).get("test"):
            d[f"W{m}LLM"] = pct(w["llm"]["test"]["risk_recall"])
    d |= dict.fromkeys(("DiffPzero", "LLMrisk", "LLMfalse", "LLMmsMed", "LLMmsNinety", "CasRisk", "CasFalse", "CasShare", "FilterDropped",
                        "FilterTotal"), P)
    s = res.get("A.mdd_01", {})
    for v in ("v0", "v2", "p0"):
        x = s.get(v)
        if x:
            d[f"Comp{v}"] = f"{x['composite'][0]:.3f}"
            d[f"CompCI{v}"] = f"[{x['composite'][1]:.3f}, {x['composite'][2]:.3f}]"
            d[f"Leaks{v}"] = P if x["judged_leaks"] is None else str(x["judged_leaks"])
            d[f"Jail{v}"], d[f"Port{v}"], d[f"SIfail{v}"], d[f"Turns{v}"] = map(str, (x["jailbreak"], x["portrayal"], x["si_fails"], x["turns"]))
    df = res.get("A.diff.mdd_01", {}).get("v2_minus_p0")
    if df:
        d["DiffPzero"] = f"${df[0]:+.3f}$ [${df[1]:+.3f}$, ${df[2]:+.3f}$]"
    rp = res.get("A.riskprobe", {})
    for v in ("v0", "v2", "p0"):
        x = rp.get(v, {}).get("pooled")
        if x:
            d[f"RPmiss{v}"] = pct(x.get("missed_judged"))
            d[f"RPn{v}"] = str(x["n"])
            d[f"RPmissRec{v}"] = pct(x.get("missed_judged_when_recalled"))
            d[f"RPmissNoRec{v}"] = pct(x.get("missed_judged_when_not_recalled"))
    llm = res.get("B.llm", {})
    if llm.get("test"):
        d["LLMrisk"], d["LLMfalse"] = pct(llm["test"]["risk_recall"]), pct(llm["test"]["risk_false_hit"])
        d["LLMmsMed"], d["LLMmsNinety"] = str(llm["ms_p50"]), str(llm["ms_p90"])
        c = llm["cascade"]["test"]
        d["CasRisk"], d["CasFalse"], d["CasShare"] = pct(c["risk_recall"]), pct(c["risk_false_hit"]), pct(c["share_sent_to_llm"], 0)
    f = res.get("B.filter")
    if f:
        d["FilterDropped"], d["FilterTotal"] = str(f["dropped_no_risk_word"]), str(f["generated_risk_probes"])
    names = {"v0": "Vzero", "v2": "Vtwo", "p0": "Pzero"}
    out = []
    for k, v in sorted(d.items()):
        for a, b in names.items():
            k = k.replace(a, b)
        out.append(rf"\newcommand{{\num{k}}}{{{v}}}")
    return "\n".join(out) + "\n"


def main():
    A.mkdir(parents=True, exist_ok=True)
    B.mkdir(parents=True, exist_ok=True)
    res = {}
    baseline_table(res)
    riskprobe_table(res)
    recall_tables(res)
    writer_table(res)
    nums = numbers(res)
    (A / "numbers.tex").write_text(nums)
    (B / "numbers.tex").write_text(nums)
    (HERE / "new_results.json").write_text(json.dumps(res, indent=1, default=str))
    print(nums)


if __name__ == "__main__":
    main()
