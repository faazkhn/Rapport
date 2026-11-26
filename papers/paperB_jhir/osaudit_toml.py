"""Writes the repository's osaudit.toml: every number paper B prints, named by file, line and occurrence.

Table cells map to values.json paths by each table's structure; the text's numbers are listed in PROSE below, each keyed by a fragment
of its line. Rerun after any edit to paperB.tex, then run osaudit. Needs osaudit (https://github.com/ASSERT-KTH/osaudit) installed:
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
E = "extra"  # the results file extra.json
AB = f"{E}.dev_rank_ablation"
HX = f"{E}.head_examples"
SIZE_BGE = A("model size of bge-small-en-v1.5 (33 million parameters), from its model card")
SIZE_GEMMA = A("model size of Gemma 4 E4B (4 billion parameters)")
TEMP0 = A("temperature 0, a run setting")
Q4 = A("4-bit quantisation, a run setting")
MS = [f"{V}.baselines.deployed.test.ms_p50", f"{V}.hybrid_ms_p50_timing_run"]  # the hybrid's median matching time in two runs
WRITER = A("an instruction given to the writer (Appendix A)")
# The text's numbers, keyed by a fragment that occurs on exactly one line of paperB.tex, so edits elsewhere do not shift them.
SWEEP = [r"0.72 & 100", r"0.74 & 98.7", r"0.76 & 93.3", r"\textbf{0.78 (shipped)}", r"0.80 & 81.3", r"0.82 & 81.3\% & 5.1"]
PROSE = {
 r"\expandafter\def\csname ver@breakurl": [A("the date in the LaTeX package version string that skips breakurl")],
 r"\author*[1]{\fnm{Faaz Kha": [AFF], r"\author[1]{\fnm{Sanket": [AFF], r"\affil[1]": [AFF],
 "has 512 doctor questions over four cases": [tot("lines")],
 "checksum into a tuning half and a test half. On the test half, keyword": [f"{V}.keywords_test.risk_recall"],
 "33-million-parameter sentence encoder, run on the processor": [SIZE_BGE, f"{V}.deployed.test.risk_recall", f"{V}.deployed.test.risk_false_hit"],
 "operating characteristic curve 0.86--0.91": [M("bm25") + ".risk_auroc[0]", M("bge-base") + ".risk_auroc[0]", SIZE_GEMMA],
 "code; a checksum split into tuning and test halves": [tot("lines")],
 "The result has 512 lines over four cases": [tot("lines"), tot("none"), tot("hard")],
 "CRC-32 checksum of each line": [A("CRC-32, the name of the checksum")],
 "Depression & 176": [f"{B}.mdd_01.lines", f"{B}.mdd_01.none", f"{B}.mdd_01.hard", f"{B}.mdd_01.risk_pairs"],
 "Alcohol withdrawal & 154": [f"{B}.alc_01.lines", f"{B}.alc_01.none", f"{B}.alc_01.hard", f"{B}.alc_01.risk_pairs"],
 "Ward: wants to go home & 104": [f"{B}.ward_01.lines", f"{B}.ward_01.none", f"{B}.ward_01.hard", f"{B}.ward_01.risk_pairs"],
 "Ward: refuses tablets & 78": [f"{B}.ward_02.lines", f"{B}.ward_02.none", f"{B}.ward_02.hard", f"{B}.ward_02.risk_pairs"],
 "Total & 512": [tot("lines"), tot("none"), tot("hard"), tot("risk_pairs")],
 "anger at home): 77 pairs": [f"{V}.baselines.risk_pairs.test"],
 "all pairs, with 95\\% intervals from 1,000": [CI, A("the number of bootstrap resamples, an analysis setting in tools/recall_baselines.py")],
 "one line in four in code-mixed Hindi": [NAME],
 "A memory scores 2 for each matching phrase tag": [A("the score of a phrase tag, a setting of the keyword layer"),
                                                    A("the score of a word tag, a setting of the keyword layer")],
 r"\textbf{Sentence-model layer.} bge-small-en-v1.5": [SIZE_BGE],
 "A memory's probes are 4--12 doctor-style questions": [f"{E}.probes_per_memory.hand_written.min", f"{E}.probes_per_memory.hand_written.max"],
 "about 50 doctor questions per memory written offline": [A("rounded: generated probes per memory range 46-52, median 49 (extra.probes_per_memory.generated)")],
 "questions whose correct memory ranked first from": [f"{AB}.minilm.memory_text.top1", f"{AB}.minilm.questions_tags_text.top1",
                                                      f"{AB}.bge_small.questions_tags_text.top3"],
 r"\textbf{Match rules.} A memory is matched": [f"{S}.SIM_HIT", f"{S}.SIM_RISK"],
 "match by at least 0.02 and above 0.76": [f"{S}.SIM_NEAR", f"{S}.SIM_FLOOR", f"{S}.RISK_MARGIN", f"{S}.RISK_NEAR"],
 "The right answer (the death wish) is second": [f"{V}.worked_example_top2[0] - {V}.worked_example_top2[1]"],
 "level marks what the doctor \\emph{clearly} asked about": [f"{S}.SIM_HIT"],
 r"\textbf{Hand-set heads.} For five risk topics": [f"{HX}.ask_withdrawal_history", f"{HX}.ask_suicidal_ideation"],
 r"\qquad \text{match if } w_k^\top e(u)": [f"{E}.heads_threshold.ask_suicidal_ideation"],
 "threshold was picked from the dev curve": [f"{E}.heads_dev.risk_recall", f"{E}.heads_dev.risk_false_hit"],
 r"($k_1=1.5$, $b=0.75$)": [A("BM25 parameter k1, the standard setting", "robertson2009bm25"), A("BM25 parameter b, the standard setting", "robertson2009bm25")],
 "plus 0.05 per tag point": [A("the weight per tag point in the hybrid's score, a setting")],
 r"\textbf{operating point}: the lowest cut-off": [f"{V}.deployed.dev.risk_false_hit"],
 r"\textbf{Zero-shot language model.} The patient's own model": [NAME, Q4],
 "temperature 0. It yields one operating point": [TEMP0],
 r"\textbf{Probe quality filter.}": [f"{V}.filter.dropped_no_risk_word / {V}.filter.generated_risk_probes"],
 "All local models ran through llama.cpp": [Q4, DATE, DATE, DATE],
 "classifier's training lines (temperature 0.95)": [A("sampling temperature, a run setting"), TEMP0, NAME],
 "further test sets (temperature 0.9": [A("sampling temperature, a run setting"), NAME, TEMP0],
 "assistant (Claude Opus 5.5": [A("the version in a model name (Claude Opus 5.5)"), DATE],
 "hand-set heads added 5.2 points": [f"100 * ({V}.hands_test.risk_recall - {V}.deployed.test.risk_recall)",
                                     f"100 * ({V}.hands_test.risk_false_hit - {V}.deployed.test.risk_false_hit)", f"{V}.baselines.risk_pairs.test", CI],
 "for the hybrid's risk recall: far from a 95": [f"100 * {V}.hybrid_test.risk_ci[1]", f"{V}.hybrid_test.risk_ci[2]", TARGET],
 "the sentence model added none. Matching took": MS,
 "Keywords only & 41.3": [f"{V}.keywords_test.fact_recall", f"{V}.keywords_test.risk_recall", f"{V}.keywords_test.risk_false_hit", f"{V}.keywords_test.none_false_hit"],
 "Hybrid & 73.3": [f"{V}.hybrid_test.all", f"{V}.deployed.test.risk_recall", f"{V}.deployed.test.risk_false_hit", f"{V}.deployed.test.none_false_hit"],
 "Hybrid + hand-set heads & 74.9": [f"{V}.hands_test.fact_recall", f"{V}.hands_test.risk_recall", f"{V}.hands_test.risk_false_hit", f"{V}.hands_test.none_false_hit"],
 "Recall was lowest for the alcohol case": [f"{V}.hybrid_test.per_case.alc_01"],
 "lines the writer marked hard (57.1": [f"{V}.hybrid_test.hard", f"{V}.hybrid_test.easy", f"{V}.hybrid_test.keywords_hard", f"{V}.hybrid_test.keywords_easy"],
 "0.88--0.91 against 0.66": [M("e5-small") + ".risk_auroc[0]", M("bge-base") + ".risk_auroc[0]", M("tags") + ".risk_auroc[0]", M("bm25") + ".risk_auroc[0]"],
 "gained 0.007 AUROC": [M("bge-base") + ".risk_auroc[0] - " + M("bge-small") + ".risk_auroc[0]",
                        "100 * " + M("bge-small") + ".test.risk_recall",
                        M("bge-base") + ".test.risk_recall"],
 "recall (bge-base, 77.9": [M("bge-base") + ".test.risk_recall", M("bge-base") + ".test.risk_false_hit"],
 "memory had the highest similarity 73.3": [f"{V}.ranks.top1", f"{V}.ranks.top3", f"{V}.ranks.top5"],
 "Correct pairs have a median similarity of": [f"{V}.ranks.correct_sim_median", f'{V}.ranks["nonrisk_best_risk_over_0.78"]', f"{S}.SIM_RISK"],
 "(prevalence 0.098)": [M("hybrid") + ".prevalence"],
 "AUROC ranged from 0.69 (tags)": [M("tags") + ".all_auroc", M("bm25") + ".all_auroc", M("minilm") + ".all_auroc", M("gte-small") + ".all_auroc",
                                   f"{V}.deployed.dev.risk_false_hit"],
 "rules themselves give 72.7": [f"{V}.deployed.test.risk_recall", f"{V}.deployed.test.risk_false_hit"],
 "which the patient's own reply also needs, against 2.6--3.0": MS,
 "on the sets written by Qwen3.5-4B and Gemma 4 E2B": [NAME],
 "7.9\\% and 6.8\\% false hits": [f"{V}.writers.qwen4b.llm.test.risk_false_hit", f"{V}.writers.gemma2b.llm.test.risk_false_hit", f"{V}.deployed.test.risk_recall"],
 "(risk AUROC 0.81--0.85)": [W("qwen4b", "bge-base") + ".risk_auroc[0]", W("gemma2b", "gte-small") + ".risk_auroc[0]"],
 "dev-matched cut-off transferred badly": [W("qwen4b", "bm25") + ".test.risk_false_hit", W("gemma2b", "bm25") + ".test.risk_false_hit"],
 "16 risk pairs per writer": [f"{V}.writers.qwen4b.hinglish.risk_pairs", f"{V}.writers.qwen4b.hinglish.deployed", f"{V}.writers.gemma2b.hinglish.deployed"],
 "the zero-shot model 87.5": [f"{V}.writers.qwen4b.hinglish.llm"],
 "Of the 21 risk pairs": [f'{V}.ranks.risk_misses["matched another risk memory"] + {V}.ranks.risk_misses["matched nothing"] + {V}.ranks.risk_misses["matched a non-risk memory"]',
                          f'{V}.ranks.risk_misses["matched nothing"]', f'{V}.ranks.risk_misses["matched a non-risk memory"]', f'{V}.ranks.risk_misses["matched another risk memory"]'],
 r"\textbf{Tuning for recall alone is unsafe.}": [f"{V}.deployed.dev.risk_recall", f"{V}.deployed.test.risk_recall"],
 "risk cut-off to 0.74 raised dev recall": [SW(1) + ".cutoff", SW(1) + ".dev.risk_recall", SW(1) + ".test.risk_recall", SW(1) + ".test.risk_false_hit",
                                            f"{V}.baselines.risk_pairs.dev"],
 "(to write probes and to set cut-offs), are enough": [f"{V}.recall_only_tune.dev.risk_recall"],
 "but matched 36.9": [f"{V}.recall_only_tune.dev.risk_false_hit", f"{V}.recall_only_tune.test.risk_false_hit"],
 "reaching 95\\% on new questions": [TARGET, SW(0) + ".cutoff"],
 **{SWEEP[i]: [SW(i) + ".cutoff", SW(i) + ".dev.risk_recall", SW(i) + ".dev.risk_false_hit", SW(i) + ".test.risk_recall", SW(i) + ".test.risk_false_hit"]
    for i in range(6)},
 "Recall-only tune & 100": [f"{V}.recall_only_tune.dev.risk_recall", f"{V}.recall_only_tune.dev.risk_false_hit", f"{V}.recall_only_tune.test.risk_recall",
                            f"{V}.recall_only_tune.test.risk_false_hit"],
 r"\textbf{A classifier trained on generated labels lost.}": [f"{V}.classifier.generated_lines"],
 "plus 369 lines": [f"{V}.classifier.log_lines"],
 "The judge agreed": [f"{V}.classifier.judge_agrees"],
 "for the tester's lines)": [f"{E}.tester_judge_agrees"],
 "(micro-F1 0.32 against 0.20)": [f"{V}.classifier.micro_f1.moves_classifier", f"{V}.classifier.micro_f1.moves_lexical",
                                  f"{V}.classifier.micro_f1.intents_classifier", f"{V}.classifier.micro_f1.intents_llm_tagger"],
 "A 4-billion-parameter language model, asked directly": [SIZE_GEMMA],
 "Labels came from the writers alone": [f"{V}.baselines.risk_pairs.dev"],
 "4 per memory and 12 per risk memory": [WRITER, WRITER],
 r"\emph{suicidal thoughts (17)}": [f"{HX}.ask_suicidal_ideation"],
 r"\emph{plans and past attempts (14)}": [f"{HX}.ask_suicide_plan"],
 r"\emph{means (12)}": [f"{HX}.ask_suicide_means"],
 "License 2.0.": [A("the version of the Apache License")],
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
TEXT = (R / P).read_text().splitlines()
for key, exprs in PROSE.items():
    found = [i + 1 for i, line in enumerate(TEXT) if key in line]
    assert len(found) == 1, f"{key!r} is on {len(found)} lines of {P}, not exactly one"
    rules[(P, found[0])] = exprs

out = ['schema = "https://github.com/ASSERT-KTH/assert-research-agent/blob/main/schemas/audit-v1.json"', "",
       "# Paper B (Testing a Safety-Critical Matcher). The text and its generated tables are audited; the \\newcommand values in",
       "# gen/numbers.tex are written by papers/analysis/new_results.py from the same saved runs and are not printed numbers of the source.",
       "# papers/paperB_jhir/values.py collects the reported values from the committed results into values.json; extra.py recomputes the",
       "# dev-half and classifier figures no earlier script saved into extra.json (regenerate either: see its docstring). Each number is",
       "# named by file, line and occurrence; this file is written by papers/paperB_jhir/osaudit_toml.py.", "",
       "[paper]", f'tex = ["{P}", "{G}tab_*.tex"]', "",
       "[results]", 'files = ["papers/paperB_jhir/values.json", "papers/paperB_jhir/extra.json"]',
       'instruments = ["papers/paperB_jhir/values.py", "papers/paperB_jhir/extra.py"]', "",
       "[[results.depends]]  # extra.py imports the matcher and the benchmark code it measures",
       'file = "papers/paperB_jhir/extra.json"',
       'instruments = ["papers/paperB_jhir/extra.py", "server/patient-service/twin.py", "server/patient-service/brain.py", "tools/recall_bench.py",',
       '               "tools/recall_baselines.py", "tools/brain/hand_weights.py"]', ""]
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
