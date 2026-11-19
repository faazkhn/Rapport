# Papers (IEEE journal format), sole author Faaz Khan Mohammad

| # | Title | Pages | PDF |
|---|---|---|---|
| 1 | Decide, Then Voice: A Code-Governed Digital Twin for Simulated Psychiatric Patients, with Three-Seed Held-Out Validation | 11 | `p1_brain/p1_brain.pdf` |
| 2 | An Integrated, On-Device Architecture for Patient-Specific Embodied Psychiatric Simulation | 8 | `p2_architecture/p2_architecture.pdf` |
| 3 | Recall Under Paraphrase for Trust-Locked Patient Memory: A Blind Benchmark, Hybrid Lexical-Embedding Matching and Training-Free Hand-Set Heads | 7 | `p3_recall/p3_recall.pdf` |
| 4 | Rapport: An Embodied, On-Device Psychiatric Standardised Patient Driven by a Research-Grounded Digital Twin (the Claude Docs "Rapport paper draft", updated with v0.3 results) | 9 | `p4_system/p4_system.pdf` |
| 5 | Rapport: A Code-Governed Digital Twin for an Embodied, On-Device Psychiatric Standardised Patient (papers 1--4 combined into one journal article) | 27 | `p5_combined/p5_combined.pdf` |

- **Conference copies (IEEE conference mode, 8 pages):** `p1_brain/p1_brain_conf.tex` and `p4_system/p4_system_conf.tex`, built from the journal
  sources by `venues/conf/p1_conf.py` and `p4_conf.py` (run from `papers/`, then `tectonic -X compile`). The journal sources stay the master copy.
- **Combined article:** `python3 p5_combined/build_combined.py` (from `papers/`) lifts the body of papers 1--4 into one article; the new
  introduction, discussion and conclusion are in `p5_combined/front.tex` and `back.tex`. Venues: see the end of `JOURNALS.md`.


## Journal split (2026-11-18): papers 1-4 become two Springer Nature papers
| | Paper | Journal | Source | Supplement |
|---|---|---|---|---|
| A | Decide in Code, Voice with the Model: the patient model, validated against a prompt-only baseline | Journal of Medical Systems | `paperA_jms/paperA.tex` | `paperA_jms/supplementA.tex` |
| B | Recognising Reworded Risk Questions: benchmark, small encoders, BM25, zero-shot LLM | Journal of Healthcare Informatics Research (alt. JEEHP) | `paperB_jhir/paperB.tex` | `paperB_jhir/supplementB.tex` |

- Template: Springer Nature `sn-jnl` (Version 3, Oct 2023, from a GitHub mirror; `venues/_templates/springer/`), Vancouver numbered references.
  Two XeTeX fixes for Tectonic: the first line of each paper skips `breakurl`, and `shared/sn_preamble.tex` redefines `\doi`.
- Numbers from the 2026-11-18 runs come from `analysis/new_results.py` into `gen/` (red `[pending]` until a run finishes).
- Supplements: `python3 build_supplements.py` (from `papers/`) lifts the cut sections from `p5_combined/p5_combined.tex`.
- Overnight runs: `tools/overnight/queue5.sh` (prompt-only baseline, missed-risk probe, disclosure judge, extra alcohol seeds, recall baselines),
  then `queue6.sh` (idle-GPU LLM timing, tables, rebuild) and `queue7.sh` (rater sheets). Status: `tests/overnight/papers/status.md`.
- Steps that need people: `HUMAN_STUDIES.md`.

- Build: `tectonic -X compile <paper>.tex` inside its folder (Tectonic 0.17, `IEEEtran` journal mode).
- Figures: `server/patient-service/.venv/bin/python papers/figures/make_figures.py` draws the charts from the measured results in this
  repo. Two photographs in paper 4 are read straight from `docs/media/` (LFS), so they are not duplicated here.
- Analyses (all from saved results; recall is code only, no model calls):
  - `analysis/analyses.py [--recall]`: bootstrap intervals, paired v2 − v0 differences, per-conversation table, decision-layer counts,
    effect of the safety fixes, recall by case, difficulty and probe source, timing → `analysis/results.json`, `figures/fig_trust_grid.pdf`.
  - `analysis/recall_extra.py`: rank of the correct memory, similarity distributions, kinds of miss → `fig_recall_sims.pdf`.
  - `analysis/recall_sensitivity.py`: risk cut-off sweep on both halves, the recall-only tune, the worked example → `fig_recall_example.pdf`.
  - `analysis/ablation_table.py`: feature ablations of v2 (runs: `tools/overnight/ablations.sh`, versions `v2nr`, `v2nc`, `v2nm`, `v2nh`).
- References: `shared/refs.bib`, checked with the citation-check skill; see `citecheck/REPORT.md` for what was found and fixed.
- Plain-language pass: `analysis/readability.py` measures each paper (before: `analysis/readability_before.txt`, after:
  `analysis/readability_after.txt`); `analysis/long_sentences.py` lists the sentences still over a length, and `analysis/apply_edits.py`
  applies sentence edits.
- Each paper ends with an IEEE-style statement on the use of AI tools (Acknowledgment). Review it before submission.
- No human-subject result is claimed: faculty ratings and a learner pilot are pending, as each paper says.
- Before submission: add a real affiliation (currently "Rapport project"); confirm the licence of the 3D brain model shown in the
  examiner-view figure (paper 4); check the journal's page and figure limits; have faculty review the clinical statements.
