"""Writes the repository's osaudit.toml: every number paper B prints, named by file, line and occurrence.

Table cells map to values.json paths by each table's structure; the text's numbers are listed by line in PROSE below. Rerun after any
edit to paperB.tex (line numbers shift), then run osaudit. Needs osaudit (https://github.com/ASSERT-KTH/osaudit) installed:
  python papers/paperB_jhir/osaudit_toml.py && osaudit
"""
from pathlib import Path

from osaudit._tex import numbers as tex_numbers

R = Path(__file__).resolve().parents[2]
G = "papers/paperB_jhir/gen/"
V = "values"  # the results file values.json
M = lambda k: f'{V}.baselines.methods["{k}"]'
W = lambda w, k: f'{V}.writers.{w}.baselines.methods["{k}"]'
B = f"{V}.benchmark"
CASES = ("mdd_01", "alc_01", "ward_01", "ward_02")
tot = lambda f: " + ".join(f"{B}.{c}.{f}" for c in CASES)
SW = lambda i: f"{V}.cutoff_sweep[{i}]"
S = f"{V}.deployed.settings"
def A(reason, cite=None):
    return ("allow", reason) + ((cite,) if cite else ())
NAME = A("the version in a model name (Gemma 4), not a quantity")
DATE = A("a date, not a result")
CI = A("the confidence level chosen for the intervals, not a result")
TARGET = A("the 95% recall target the text compares against, not a result")
AFF = A("an affiliation marker")
NOTCOMMITTED = "reported from a dev-half analysis run during development whose output file is not committed"
PROSE = {
 1: [A("the date in the LaTeX package version string that skips breakurl")],
 12: [AFF], 13: [AFF], 14: [AFF],
 17: [tot("lines")],
 19: [f"{V}.keywords_test.risk_recall", A("model size of bge-small-en-v1.5 (33 million parameters), from its model card")],
 20: [f"{V}.deployed.test.risk_recall", f"{V}.deployed.test.risk_false_hit"],
 21: [M("bm25") + ".risk_auroc[0]", M("bge-base") + ".risk_auroc[0]"],
 22: [A("model size of Gemma 4 E4B (4 billion parameters)")],
 46: [tot("lines")],
 95: [tot("lines"), tot("none"), tot("hard")],
 97: [A("CRC-32, the name of the checksum")],
 108: [f"{B}.mdd_01.lines", f"{B}.mdd_01.none", f"{B}.mdd_01.hard", f"{B}.mdd_01.risk_pairs"],
 109: [f"{B}.alc_01.lines", f"{B}.alc_01.none", f"{B}.alc_01.hard", f"{B}.alc_01.risk_pairs"],
 110: [f"{B}.ward_01.lines", f"{B}.ward_01.none", f"{B}.ward_01.hard", f"{B}.ward_01.risk_pairs"],
 111: [f"{B}.ward_02.lines", f"{B}.ward_02.none", f"{B}.ward_02.hard", f"{B}.ward_02.risk_pairs"],
 113: [tot("lines"), tot("none"), tot("hard"), tot("risk_pairs")],
 119: [f"{V}.baselines.risk_pairs.test"],
 122: [CI, A("the number of bootstrap resamples, an analysis setting in tools/recall_baselines.py")],
 127: [NAME],
 155: [A("the score of a phrase tag, a setting of the keyword layer"), A("the score of a word tag, a setting of the keyword layer")],
 157: [A("model size of bge-small-en-v1.5 (33 million parameters), from its model card", "xiao2023cpack")],
 159: [A("lower end of the number of hand-written probes per memory (case files)"), A("upper end of the number of hand-written probes per memory (case files)")],
 160: [A("approximate number of generated probes requested per memory, a setting of the probe generator")],
 163: [A(NOTCOMMITTED), A(NOTCOMMITTED), A(NOTCOMMITTED)],
 165: [f"{S}.SIM_HIT", f"{S}.SIM_RISK"],
 166: [f"{S}.SIM_NEAR", f"{S}.SIM_FLOOR", f"{S}.RISK_MARGIN", f"{S}.RISK_NEAR"],
 174: [A("read from the worked example drawn in fig_recall_example.pdf (papers/figures/make_figures.py)")],
 180: [f"{S}.SIM_HIT"],
 183: [A("fewest example questions of a hand-set head (Appendix B)"), A("most example questions of a hand-set head (Appendix B)")],
 186: [A("the hand-set heads' threshold, a setting chosen on the dev half")],
 189: [A(NOTCOMMITTED + " (Supplementary Section S2)"), A(NOTCOMMITTED + " (Supplementary Section S2)")],
 192: [A("BM25 parameter k1, the standard setting", "robertson2009bm25"), A("BM25 parameter b, the standard setting", "robertson2009bm25")],
 195: [A("the weight per tag point in the hybrid's score, a setting")],
 197: [f"{V}.deployed.dev.risk_false_hit"],
 200: [NAME, A("4-bit quantisation, a run setting")],
 202: [A("temperature 0, a run setting")],
 207: [f"{V}.filter.dropped_no_risk_word / {V}.filter.generated_risk_probes"],
 212: [A("4-bit quantisation, a run setting"), DATE, DATE, DATE],
 214: [A("sampling temperature, a run setting"), A("temperature 0, a run setting"), NAME],
 215: [A("sampling temperature, a run setting"), NAME, A("temperature 0, a run setting")],
 217: [A("the version in a model name (Claude Opus 5.5)"), DATE],
 225: [f"100 * ({V}.hands_test.risk_recall - {V}.deployed.test.risk_recall)",
       f"100 * ({V}.hands_test.risk_false_hit - {V}.deployed.test.risk_false_hit)", f"{V}.baselines.risk_pairs.test", CI],
 226: [f"100 * {V}.hybrid_test.risk_ci[1]", f"{V}.hybrid_test.risk_ci[2]", TARGET],
 227: [A("lower end of the hybrid's median matching time, 2.57-3.03 ms (values.deployed.test.ms_p50; papers/analysis/results.json recall_ms.p50)"),
       A("upper end of the hybrid's median matching time, 2.57-3.03 ms (values.deployed.test.ms_p50; papers/analysis/results.json recall_ms.p50)")],
 237: [f"{V}.keywords_test.fact_recall", f"{V}.keywords_test.risk_recall", f"{V}.keywords_test.risk_false_hit", f"{V}.keywords_test.none_false_hit"],
 238: [f"{V}.hybrid_test.all", f"{V}.deployed.test.risk_recall", f"{V}.deployed.test.risk_false_hit", f"{V}.deployed.test.none_false_hit"],
 239: [f"{V}.hands_test.fact_recall", f"{V}.hands_test.risk_recall", f"{V}.hands_test.risk_false_hit", f"{V}.hands_test.none_false_hit"],
 244: [f"{V}.hybrid_test.per_case.alc_01"],
 245: [f"{V}.hybrid_test.hard", f"{V}.hybrid_test.easy", f"{V}.hybrid_test.keywords_hard", f"{V}.hybrid_test.keywords_easy"],
 250: [M("e5-small") + ".risk_auroc[0]", M("bge-base") + ".risk_auroc[0]", M("tags") + ".risk_auroc[0]", M("bm25") + ".risk_auroc[0]"],
 251: [M("bge-base") + ".risk_auroc[0] - " + M("bge-small") + ".risk_auroc[0]",
       A("lower end of the encoders' matched-point risk recall, bge-small's 66.2% (values.baselines.methods[\"bge-small\"].test.risk_recall)"),
       M("bge-base") + ".test.risk_recall"],
 252: [M("bge-base") + ".test.risk_recall", M("bge-base") + ".test.risk_false_hit"],
 253: [f"{V}.ranks.top1", f"{V}.ranks.top3", f"{V}.ranks.top5"],
 254: [f"{V}.ranks.correct_sim_median", f'{V}.ranks["nonrisk_best_risk_over_0.78"]', f"{S}.SIM_RISK"],
 262: [M("hybrid") + ".prevalence"],
 263: [M("tags") + ".all_auroc", M("bm25") + ".all_auroc", M("minilm") + ".all_auroc", M("gte-small") + ".all_auroc", f"{V}.deployed.dev.risk_false_hit"],
 264: [f"{V}.deployed.test.risk_recall", f"{V}.deployed.test.risk_false_hit"],
 277: [A("lower end of the hybrid's median matching time, 2.57-3.03 ms (values.deployed.test.ms_p50; papers/analysis/results.json recall_ms.p50)"),
       A("upper end of the hybrid's median matching time, 2.57-3.03 ms (values.deployed.test.ms_p50; papers/analysis/results.json recall_ms.p50)")],
 305: [NAME],
 306: [f"{V}.writers.qwen4b.llm.test.risk_false_hit", f"{V}.writers.gemma2b.llm.test.risk_false_hit", f"{V}.deployed.test.risk_recall"],
 309: [W("qwen4b", "bge-base") + ".risk_auroc[0]", W("gemma2b", "gte-small") + ".risk_auroc[0]"],
 310: [W("qwen4b", "bm25") + ".test.risk_false_hit", W("gemma2b", "bm25") + ".test.risk_false_hit"],
 311: [f"{V}.writers.qwen4b.hinglish.risk_pairs", f"{V}.writers.qwen4b.hinglish.deployed", f"{V}.writers.gemma2b.hinglish.deployed"],
 312: [f"{V}.writers.qwen4b.hinglish.llm"],
 332: [f'{V}.ranks.risk_misses["matched another risk memory"] + {V}.ranks.risk_misses["matched nothing"] + {V}.ranks.risk_misses["matched a non-risk memory"]',
       f'{V}.ranks.risk_misses["matched nothing"]', f'{V}.ranks.risk_misses["matched a non-risk memory"]', f'{V}.ranks.risk_misses["matched another risk memory"]'],
 356: [f"{V}.deployed.dev.risk_recall", f"{V}.deployed.test.risk_recall"],
 357: [A("dev risk recall of an earlier setting; " + NOTCOMMITTED), f"{V}.deployed.test.risk_recall", f"{V}.baselines.risk_pairs.dev"],
 358: [f"{V}.recall_only_tune.dev.risk_recall"],
 359: [f"{V}.recall_only_tune.dev.risk_false_hit", f"{V}.recall_only_tune.test.risk_false_hit"],
 360: [A("turns with an unasked death-wish mention in the held-out run of the recall-only setting; that run's transcripts are not committed"),
       A("turns in the 12 held-out conversations (docs/GATES.md)")],
 362: [TARGET, SW(0) + ".cutoff"],
 **{374 + i: [SW(i) + ".cutoff", SW(i) + ".dev.risk_recall", SW(i) + ".dev.risk_false_hit", SW(i) + ".test.risk_recall", SW(i) + ".test.risk_false_hit"]
    for i in range(6)},
 381: [f"{V}.recall_only_tune.dev.risk_recall", f"{V}.recall_only_tune.dev.risk_false_hit", f"{V}.recall_only_tune.test.risk_recall",
       f"{V}.recall_only_tune.test.risk_false_hit"],
 386: [f"{V}.classifier.generated_lines"],
 387: [f"{V}.classifier.log_lines"],
 388: [f"{V}.classifier.judge_agrees"],
 389: [A("judge agreement on the simulated tester's lines; " + NOTCOMMITTED + " (Supplementary Section S3)")],
 390: [f"{V}.classifier.micro_f1.moves_classifier", f"{V}.classifier.micro_f1.moves_lexical", f"{V}.classifier.micro_f1.intents_classifier",
       f"{V}.classifier.micro_f1.intents_llm_tagger"],
 403: [A("model size of Gemma 4 E4B (4 billion parameters)")],
 415: [f"{V}.baselines.risk_pairs.dev"],
 431: [A("an instruction given to the writer (Appendix A)"), A("an instruction given to the writer (Appendix A)")],
 439: [A("the number of example questions of this head, listed in the code")],
 440: [A("the number of example questions of this head, listed in the code")],
 441: [A("the number of example questions of this head, listed in the code")],
 460: [A("the version of the Apache License")],
}

def m(k): return f'values.baselines.methods["{k}"]'
def w(n): return f"values.writers.{n}"
def tri(p): return [f"{p}[0]", f"{p}[1]", f"{p}[2]"]
rules = {}  # (file, line) -> list of exprs, in the order the numbers appear on the line
BL = ["tags", "bm25", "minilm", "e5-small", "gte-small", "bge-small", "bge-base", "hybrid"]
for i, k in enumerate(BL):
    rules[(G + "tab_baselines.tex", 5 + i)] = tri(m(k) + ".risk_auroc") + tri(m(k) + ".risk_auprc") + [m(k) + ".test.risk_recall", m(k) + ".test.risk_false_hit"]
NAME = ("allow", "the version in a model name (Gemma 4 E4B, Gemma 4 E2B), not a quantity")
CI = ("allow", "the confidence level chosen for the intervals, not a result")
rules[(G + "tab_baselines.tex", 3)] = [CI, CI]
rules[(G + "tab_baselines.tex", 14)] = [NAME, "values.llm.test.risk_recall", "values.llm.test.risk_false_hit"]
rules[(G + "tab_baselines.tex", 15)] = ["values.llm.cascade_test.risk_recall", "values.llm.cascade_test.risk_false_hit"]
for i in range(9):
    s = f"values.llm.cascade_sweep_test[{i}]"
    rules[(G + "tab_cascade.tex", 5 + i)] = [s + ".floor", s + ".risk_recall", s + ".risk_false_hit", s + ".share_sent_to_llm"]
for i, k in enumerate(BL[1:]):
    a, b = m(k), m(k + "+filter")
    rules[(G + "tab_filter.tex", 5 + i)] = [a + ".risk_auroc[0]", b + ".risk_auroc[0]", a + ".test.risk_recall", b + ".test.risk_recall",
                                           a + ".test.risk_false_hit", b + ".test.risk_false_hit"]
for ln, half in ((13, "dev"), (14, "test")):
    d, f = f"values.baselines.deployed.{half}", f"values.baselines.deployed_filtered.{half}"
    rules[(G + "tab_filter.tex", ln)] = [d + ".risk_recall", f + ".risk_recall", d + ".risk_false_hit", f + ".risk_false_hit"]
for i, n in enumerate(("qwen4b", "gemma2b")):
    h = w(n) + ".hinglish"
    rules[(G + "tab_hinglish.tex", 5 + i)] = [NAME] * i + [h + ".lines", h + ".risk_pairs", h + ".deployed", h + ".llm"]
for i, k in enumerate(["tags", "bm25", "bge-small", "bge-base", "gte-small", "hybrid"]):
    rules[(G + "tab_writers.tex", 5 + i)] = [x for n in ("qwen4b", "gemma2b") for x in
        (f'{w(n)}.baselines.methods["{k}"].risk_auroc[0]', f'{w(n)}.baselines.methods["{k}"].test.risk_recall', f'{w(n)}.baselines.methods["{k}"].test.risk_false_hit')]
rules[(G + "tab_writers.tex", 12)] = [x for n in ("qwen4b", "gemma2b") for x in (f"{w(n)}.baselines.deployed.test.risk_recall", f"{w(n)}.baselines.deployed.test.risk_false_hit")]
rules[(G + "tab_writers.tex", 3)] = [NAME]
rules[(G + "tab_writers.tex", 13)] = [NAME] + [x for n in ("qwen4b", "gemma2b") for x in (f"{w(n)}.llm.test.risk_recall", f"{w(n)}.llm.test.risk_false_hit")]

P = "papers/paperB_jhir/paperB.tex"
for ln, exprs in PROSE.items():
    rules[(P, ln)] = exprs

out = ['schema = "https://github.com/ASSERT-KTH/assert-research-agent/blob/main/schemas/audit-v1.json"', "",
       "# Paper B (Recognising Reworded Risk Questions). The text and its generated tables are audited; the \\newcommand values in",
       "# gen/numbers.tex are written by papers/analysis/new_results.py from the same saved runs and are not printed numbers of the source.",
       "# papers/paperB_jhir/values.py collects every reported value from the committed results into values.json (regenerate: see its",
       "# docstring). Each number is named by file, line and occurrence.", "",
       "[paper]", f'tex = ["{P}", "{G}tab_*.tex"]', "",
       "[results]", 'files = ["papers/paperB_jhir/values.json"]', 'instruments = ["papers/paperB_jhir/values.py"]', ""]
def q(s): return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'
for f in [P] + sorted({k[0] for k in rules if k[0] != P}):
    nums = list(tex_numbers(f, (R / f).read_text()))
    by_line = {}
    for n in nums:
        by_line.setdefault(n.line, []).append(n)
    for ln, ns in sorted(by_line.items()):
        exprs = rules.get((f, ln))
        seen = {}
        if exprs is None:
            continue
        ns2 = ns
        assert len(ns2) == len(exprs), (f, ln, [n.text for n in ns2], exprs)
        for n, e in zip(ns2, exprs):
            seen[n.key] = seen.get(n.key, 0) + 1
            if isinstance(e, tuple):
                out += ["[[numbers.allow]]", f"value = {q(n.text)}", f"reason = {q(e[1])}"] + ([f"cite = {q(e[2])}"] if len(e) > 2 else []) + \
                       [f"file = {q(f)}", f"line = {ln}", f"occurrence = {seen[n.key]}", ""]
                continue
            out += ["[[numbers.derive]]", f"value = {q(n.text)}", f"expr = {q(e)}", f"file = {q(f)}", f"line = {ln}", f"occurrence = {seen[n.key]}", ""]
(R / "osaudit.toml").write_text("\n".join(out))
