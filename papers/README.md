# Papers (IEEE journal format), sole author Faaz Khan Mohammad

| # | Title | Pages | PDF |
|---|---|---|---|
| 1 | Decide, Then Voice: A Code-Governed Digital Twin for Simulated Psychiatric Patients, with Three-Seed Held-Out Validation | 11 | `p1_brain/p1_brain.pdf` |
| 2 | An Integrated, On-Device Architecture for Patient-Specific Embodied Psychiatric Simulation | 8 | `p2_architecture/p2_architecture.pdf` |
| 3 | Recall Under Paraphrase for Trust-Locked Patient Memory: A Blind Benchmark, Hybrid Lexical-Embedding Matching and Training-Free Hand-Set Heads | 7 | `p3_recall/p3_recall.pdf` |
| 4 | Rapport: An Embodied, On-Device Psychiatric Standardised Patient Driven by a Research-Grounded Digital Twin (the Claude Docs "Rapport paper draft", updated with v0.3 results) | 9 | `p4_system/p4_system.pdf` |

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
